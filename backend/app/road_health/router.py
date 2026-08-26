"""
router.py
=========
FastAPI routes for Road Health.

    GET /road-health/segments               -> GeoJSON FeatureCollection
    GET /road-health/segments/{segment_id}  -> one segment + its defects

Both recompute health from canonical data on every request, so the response
always reflects the current state of the defects table.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_db
from . import service
from .schemas import SegmentDetail, SegmentFeatureCollection

router = APIRouter(prefix="/road-health", tags=["road-health"])


@router.get("/segments", response_model=SegmentFeatureCollection)
def list_segment_health(db: Session = Depends(get_db)) -> dict:
    """
    Road health for every segment, as a GeoJSON FeatureCollection the officer
    frontend can draw directly.
    """
    return service.build_feature_collection(db)


@router.get("/segments/{segment_id}", response_model=SegmentDetail)
def get_segment_health(segment_id: str, db: Session = Depends(get_db)) -> dict:
    """Road health detail for one segment, including its defects."""
    segment = service.get_segment(db, segment_id)

    if segment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Road segment '{segment_id}' not found",
        )

    return service.build_segment_detail(db, segment)
