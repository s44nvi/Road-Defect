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
from .geo import InvalidGeometryError
from .schemas import SegmentDetail, SegmentFeatureCollection

router = APIRouter(prefix="/road-health", tags=["road-health"])


@router.get("/segments", response_model=SegmentFeatureCollection)
def list_segment_health(
    geometry_source: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    Road health for every segment, as a GeoJSON FeatureCollection the officer
    frontend can draw directly.

        GET /road-health/segments
        GET /road-health/segments?geometry_source=mcgm_demo_csv_v1

    `geometry_source` is optional; omitted, this returns every segment
    regardless of provenance (dev/OSM/MCGM), unchanged from before. Pass it
    to scope the response to one provenance -- e.g. the demo frontend can
    request just the 10 real MCGM roads without a second endpoint and
    without any segment being hidden/deleted from the underlying data.
    """
    return service.build_feature_collection(db, geometry_source=geometry_source)


@router.get("/segments/{segment_id}", response_model=SegmentDetail)
def get_segment_health(segment_id: str, db: Session = Depends(get_db)) -> dict:
    """Road health detail for one segment, including its defects."""
    segment = service.get_segment(db, segment_id)

    if segment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Road segment '{segment_id}' not found",
        )

    try:
        return service.build_segment_detail(db, segment)
    except InvalidGeometryError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Road segment '{segment_id}' has unusable geometry: {exc}",
        ) from exc
