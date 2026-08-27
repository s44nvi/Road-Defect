"""Officer verification endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.db import get_db
from app.models.defect import Defect, DefectStatus
from app.schemas.defect import DefectVerificationRequest, DefectVerificationResponse, DefectResponse

router = APIRouter(prefix="/verify", tags=["Verification"])

# TODO: Add authentication dependency for officer_id
# from app.api.auth import get_current_user


@router.post("/{defect_id}", response_model=DefectVerificationResponse)
async def verify_defect(
    defect_id: str,
    request: DefectVerificationRequest,
    officer_id: str = "temp-officer-id",  # TODO: from authentication
    db: Session = Depends(get_db)
):
    """
    Officer verification endpoint.
    
    Officer confirms, rejects, or modifies defect severity.
    Only verified defects can be scheduled for repair.
    """
    try:
        defect = db.query(Defect).filter(Defect.id == uuid.UUID(defect_id)).first()
        
        if not defect:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Defect not found"
            )
        
        if defect.status != DefectStatus.DETECTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Can only verify defects in DETECTED status, current: {defect.status}"
            )
        
        if request.verified:
            # Approve defect
            defect.status = DefectStatus.VERIFIED
            defect.verified_at = datetime.utcnow()
            defect.verified_by = uuid.UUID(officer_id)
            
            # Update severity if provided
            if request.severity:
                defect.severity = request.severity
                
        else:
            # Reject defect
            defect.status = DefectStatus.REJECTED
            defect.verified_at = datetime.utcnow()
            defect.verified_by = uuid.UUID(officer_id)
        
        db.commit()
        db.refresh(defect)
        
        return DefectVerificationResponse(
            defect_id=defect.id,
            verified=request.verified,
            verified_by=defect.verified_by,
            verified_at=defect.verified_at,
            severity=defect.severity,
            status=defect.status
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID format: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification failed: {str(e)}"
        )


@router.get("/pending", response_model=dict)
async def get_pending_verification(
    db: Session = Depends(get_db)
):
    """Get all defects pending verification"""
    try:
        defects = db.query(Defect).filter(
            Defect.status == DefectStatus.DETECTED
        ).all()
        
        return {
            "total": len(defects),
            "defects": [
                {
                    "id": str(d.id),
                    "type": d.defect_type,
                    "severity": d.severity,
                    "priority_score": d.priority_score,
                    "recurrence_count": d.recurrence_count,
                    "observations": len(d.observations),
                    "created_at": d.created_at
                }
                for d in defects
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending verifications: {str(e)}"
        )
