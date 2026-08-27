"""Defect endpoints - query and manage defects"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
import uuid

from app.db import get_db
from app.models.defect import Defect, DefectStatus, SeverityLevel
from app.schemas.defect import DefectResponse, DefectListResponse, DefectUpdate

router = APIRouter(prefix="/defects", tags=["Defects"])
static_router = APIRouter(prefix="/defects", tags=["Defects"])


@router.get("/", response_model=DefectListResponse)
async def list_defects(
    status: str = Query(None, description="Filter by status"),
    severity: str = Query(None, description="Filter by severity"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of defects.
    
    Can filter by status and severity.
    Sorted by priority score (highest first).
    """
    try:
        query = db.query(Defect)
        
        # Apply filters
        if status:
            query = query.filter(Defect.status == status)
        if severity:
            query = query.filter(Defect.severity == severity)
        
        # Count total
        total = query.count()
        
        # Sort by priority and paginate
        skip = (page - 1) * page_size
        defects = query.order_by(desc(Defect.priority_score)).offset(skip).limit(page_size).all()
        
        # Convert to response objects
        defect_responses = [
            DefectResponse(
                id=d.id,
                defect_type=d.defect_type,
                status=d.status,
                severity=d.severity,
                priority_score=d.priority_score,
                recurrence_count=d.recurrence_count,
                evidence_score=d.evidence_score,
                latitude=d.location.y if d.location else 0,
                longitude=d.location.x if d.location else 0,
                created_at=d.created_at,
                updated_at=d.updated_at,
                observation_count=len(d.observations)
            )
            for d in defects
        ]
        
        return DefectListResponse(
            total=total,
            page=page,
            page_size=page_size,
            defects=defect_responses
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch defects: {str(e)}"
        )


@router.get("/{defect_id}", response_model=DefectResponse)
async def get_defect(
    defect_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed view of a specific defect"""
    try:
        defect = db.query(Defect).filter(Defect.id == uuid.UUID(defect_id)).first()
        
        if not defect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defect not found"
            )
        
        return DefectResponse(
            id=defect.id,
            defect_type=defect.defect_type,
            status=defect.status,
            severity=defect.severity,
            priority_score=defect.priority_score,
            recurrence_count=defect.recurrence_count,
            evidence_score=defect.evidence_score,
            latitude=defect.location.y if defect.location else 0,
            longitude=defect.location.x if defect.location else 0,
            created_at=defect.created_at,
            updated_at=defect.updated_at,
            observation_count=len(defect.observations)
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid defect ID"
        )


@router.patch("/{defect_id}", response_model=DefectResponse)
async def update_defect(
    defect_id: str,
    update: DefectUpdate,
    db: Session = Depends(get_db)
):
    """Update defect details"""
    try:
        defect = db.query(Defect).filter(Defect.id == uuid.UUID(defect_id)).first()
        
        if not defect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defect not found"
            )
        
        # Update fields if provided
        if update.severity:
            defect.severity = update.severity
        if update.status:
            defect.status = update.status
        
        db.commit()
        db.refresh(defect)
        
        return DefectResponse(
            id=defect.id,
            defect_type=defect.defect_type,
            status=defect.status,
            severity=defect.severity,
            priority_score=defect.priority_score,
            recurrence_count=defect.recurrence_count,
            evidence_score=defect.evidence_score,
            latitude=defect.location.y if defect.location else 0,
            longitude=defect.location.x if defect.location else 0,
            created_at=defect.created_at,
            updated_at=defect.updated_at,
            observation_count=len(defect.observations)
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid defect ID"
        )


@static_router.get("/pending/verification", response_model=DefectListResponse)
async def get_pending_verification(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get defects pending officer verification"""
    return await list_defects(status="detected", page=page, page_size=page_size, db=db)


@static_router.get("/stats/summary", response_model=dict)
async def get_summary_stats(db: Session = Depends(get_db)):
    """Get dashboard summary statistics"""
    try:
        defects = db.query(Defect).all()
        
        return {
            "total_defects": len(defects),
            "defects_by_status": {
                "detected": len([d for d in defects if d.status == DefectStatus.DETECTED]),
                "verified": len([d for d in defects if d.status == DefectStatus.VERIFIED]),
                "scheduled": len([d for d in defects if d.status == DefectStatus.SCHEDULED]),
                "repaired": len([d for d in defects if d.status == DefectStatus.REPAIRED]),
            },
            "defects_by_severity": {
                "low": len([d for d in defects if d.severity == SeverityLevel.LOW]),
                "medium": len([d for d in defects if d.severity == SeverityLevel.MEDIUM]),
                "high": len([d for d in defects if d.severity == SeverityLevel.HIGH]),
                "critical": len([d for d in defects if d.severity == SeverityLevel.CRITICAL]),
            },
            "pending_verification": len([d for d in defects if d.status == DefectStatus.DETECTED]),
            "pending_repair": len([d for d in defects if d.status == DefectStatus.VERIFIED]),
            "completed_repairs": len([d for d in defects if d.status == DefectStatus.REPAIRED]),
            "average_priority_score": sum(d.priority_score for d in defects) / len(defects) if defects else 0
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch statistics: {str(e)}"
        )
