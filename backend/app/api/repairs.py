"""Repair scheduling endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.defect import Defect, DefectStatus, Repair
from app.schemas.defect import RepairResponse, RepairScheduleRequest

router = APIRouter(prefix="/defects", tags=["Repairs"])


@router.post("/{defect_id}/repair", response_model=RepairResponse, status_code=status.HTTP_201_CREATED)
async def schedule_repair(
    defect_id: str,
    request: RepairScheduleRequest,
    db: Session = Depends(get_db),
):
    """Schedule a repair for a verified defect."""
    try:
        defect_uuid = uuid.UUID(defect_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid defect ID")

    defect = db.query(Defect).filter(Defect.id == defect_uuid).first()
    if not defect:
        raise HTTPException(status_code=404, detail="Defect not found")
    if defect.status != DefectStatus.VERIFIED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only schedule verified defects, current: {defect.status.value}",
        )

    repair = Repair(
        defect_id=defect.id,
        assigned_crew=request.assigned_crew,
        estimated_cost=request.estimated_cost,
        scheduled_date=request.scheduled_date,
        notes=request.notes,
        status="scheduled",
    )
    defect.status = DefectStatus.SCHEDULED
    db.add(repair)
    db.commit()
    db.refresh(repair)
    return repair
