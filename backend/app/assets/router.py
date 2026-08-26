"""
router.py
=========
Read-only FastAPI routes for the MCGM infrastructure/context layer:

    GET /assets/manholes[?segment_id=MCGM-2353]
    GET /assets/encroachments[?segment_id=MCGM-2353]
    GET /road-health/segments/{segment_id}/assets

This module is deliberately kept SEPARATE from `road_health/`. Manholes and
encroachments are context/infrastructure, not defects, and must never feed
Road Health scoring (`road_health/scoring.py` only ever reads `Defect`
rows -- nothing in this file is imported by it, and nothing here writes to
`Defect`, `defect_status`, `defect_severity`, or `defect_priority`).

    Road
      -> MCGM Assets
           -> Manholes: X
           -> Encroachments: Y

`segment_id` query/path parameters are the public MCGM segment id (e.g.
"MCGM-2353"), matching the existing `GET /road-health/segments/{segment_id}`
convention, not the internal numeric `RoadSegment.id`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models import Encroachment, Manhole, RoadSegment
from .schemas import EncroachmentResponse, ManholeResponse, SegmentAssetsResponse

router = APIRouter(tags=["assets"])


def _resolve_segment_pk(db: Session, segment_id: str | None) -> int | None:
    """Public segment_id -> internal RoadSegment.id, or 404 if given but unknown."""
    if segment_id is None:
        return None

    segment = db.query(RoadSegment).filter(RoadSegment.segment_id == segment_id).first()

    if segment is None:
        raise HTTPException(status_code=404, detail=f"Road segment '{segment_id}' not found")

    return segment.id


def _manhole_response(manhole: Manhole) -> ManholeResponse:
    return ManholeResponse(
        id=manhole.id,
        object_id=manhole.object_id,
        road_name=manhole.road_name,
        ward=manhole.ward,
        latitude=manhole.latitude,
        longitude=manhole.longitude,
        status=manhole.status,
        condition=manhole.condition,
        survey_date=manhole.survey_date,
        created_date=manhole.created_date,
        last_edited_date=manhole.last_edited_date,
        remarks=manhole.remarks,
        road_norm=manhole.road_norm,
        segment_id=manhole.road_segment.segment_id if manhole.road_segment else None,
    )


def _encroachment_response(encroachment: Encroachment) -> EncroachmentResponse:
    return EncroachmentResponse(
        id=encroachment.id,
        object_id=encroachment.object_id,
        road_name=encroachment.road_name,
        ward=encroachment.ward,
        latitude=encroachment.latitude,
        longitude=encroachment.longitude,
        status=encroachment.status,
        complaint_type=encroachment.complaint_type,
        description=encroachment.description,
        created_date=encroachment.created_date,
        last_edited_date=encroachment.last_edited_date,
        segment_id=encroachment.road_segment.segment_id if encroachment.road_segment else None,
    )


@router.get("/assets/manholes", response_model=list[ManholeResponse])
def list_manholes(segment_id: str | None = None, db: Session = Depends(get_db)):
    """All imported MCGM manholes, optionally filtered to one road segment."""
    segment_pk = _resolve_segment_pk(db, segment_id)

    query = db.query(Manhole)
    if segment_pk is not None:
        query = query.filter(Manhole.road_segment_id == segment_pk)

    return [_manhole_response(m) for m in query.order_by(Manhole.id).all()]


@router.get("/assets/encroachments", response_model=list[EncroachmentResponse])
def list_encroachments(segment_id: str | None = None, db: Session = Depends(get_db)):
    """All imported MCGM encroachment complaints, optionally filtered to one road segment."""
    segment_pk = _resolve_segment_pk(db, segment_id)

    query = db.query(Encroachment)
    if segment_pk is not None:
        query = query.filter(Encroachment.road_segment_id == segment_pk)

    return [_encroachment_response(e) for e in query.order_by(Encroachment.id).all()]


@router.get("/road-health/segments/{segment_id}/assets", response_model=SegmentAssetsResponse)
def get_segment_assets(segment_id: str, db: Session = Depends(get_db)):
    """
    The MCGM context layer for one road segment: its manholes and
    encroachments, plus their counts. Purely informational -- these counts
    are never read by Road Health scoring.
    """
    segment = db.query(RoadSegment).filter(RoadSegment.segment_id == segment_id).first()

    if segment is None:
        raise HTTPException(status_code=404, detail=f"Road segment '{segment_id}' not found")

    manholes = (
        db.query(Manhole).filter(Manhole.road_segment_id == segment.id).order_by(Manhole.id).all()
    )
    encroachments = (
        db.query(Encroachment)
        .filter(Encroachment.road_segment_id == segment.id)
        .order_by(Encroachment.id)
        .all()
    )

    return SegmentAssetsResponse(
        segment_id=segment.segment_id,
        manhole_count=len(manholes),
        encroachment_count=len(encroachments),
        manholes=[_manhole_response(m) for m in manholes],
        encroachments=[_encroachment_response(e) for e in encroachments],
    )
