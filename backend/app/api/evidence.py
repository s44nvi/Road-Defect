"""Evidence upload endpoint"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from geoalchemy2.functions import ST_Distance, ST_GeomFromText, ST_DWithin
from datetime import datetime, timedelta
import uuid

from app.db import get_db
from app.models.defect import Defect, Observation, DefectStatus, DefectType, SeverityLevel
from app.schemas.defect import ObservationCreate, ObservationResponse, DefectResponse

router = APIRouter(prefix="/evidence", tags=["Evidence"])

# Constants for defect consolidation
DISTANCE_THRESHOLD_METERS = 50  # Merge observations within 50 meters
TIME_WINDOW_HOURS = 24  # Merge observations within 24 hours


@router.post("/", response_model=ObservationResponse)
async def upload_evidence(
    observation: ObservationCreate,
    db: Session = Depends(get_db)
):
    """
    Upload evidence observation from vehicle.
    
    Automatically consolidates nearby observations into a single defect.
    """
    try:
        # Create WKT point
        point_wkt = f"POINT({observation.longitude} {observation.latitude})"
        
        # Find nearby defects of same type within time window
        time_window = datetime.utcnow() - timedelta(hours=TIME_WINDOW_HOURS)
        
        nearby_defect = db.query(Defect).filter(
            Defect.defect_type == observation.defect_type,
            Defect.created_at >= time_window,
            ST_DWithin(
                Defect.location,
                ST_GeomFromText(point_wkt, 4326),
                DISTANCE_THRESHOLD_METERS
            )
        ).first()
        
        # Use existing defect or create new
        if nearby_defect:
            defect = nearby_defect
            defect.recurrence_count += 1
            # Update priority based on new observation
            defect.evidence_score = min(1.0, defect.evidence_score + 0.1)
        else:
            # Create new defect
            defect = Defect(
                location=f"SRID=4326;{point_wkt}",
                defect_type=observation.defect_type,
                status=DefectStatus.DETECTED,
                severity=SeverityLevel.MEDIUM,
                priority_score=observation.detection_confidence * 0.7,
                evidence_score=observation.detection_confidence,
                recurrence_count=1
            )
            db.add(defect)
            db.flush()
        
        # Create observation record
        new_observation = Observation(
            defect_id=defect.id,
            location=f"SRID=4326;{point_wkt}",
            detection_confidence=observation.detection_confidence,
            impact_magnitude=observation.impact_magnitude,
            image_urls=observation.image_urls,
            video_url=observation.video_url,
            device_id=observation.device_id,
            gps_accuracy=observation.gps_accuracy,
            heading=observation.heading,
            timestamp=observation.timestamp
        )
        
        db.add(new_observation)
        db.commit()
        db.refresh(new_observation)
        
        return ObservationResponse(
            id=new_observation.id,
            defect_id=new_observation.defect_id,
            detection_confidence=new_observation.detection_confidence,
            latitude=observation.latitude,
            longitude=observation.longitude,
            timestamp=new_observation.timestamp
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process evidence: {str(e)}"
        )


@router.post("/bulk", response_model=dict)
async def upload_bulk_evidence(
    observations: list[ObservationCreate],
    db: Session = Depends(get_db)
):
    """
    Bulk upload multiple observations in one request.
    """
    results = []
    for obs in observations:
        try:
            result = await upload_evidence(obs, db)
            results.append({"status": "success", "observation_id": str(result.id)})
        except Exception as e:
            results.append({"status": "error", "error": str(e)})
    
    return {
        "total": len(observations),
        "successful": len([r for r in results if r["status"] == "success"]),
        "failed": len([r for r in results if r["status"] == "error"]),
        "results": results
    }
