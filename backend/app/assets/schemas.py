"""
schemas.py
==========
Response models for the MCGM infrastructure/context layer (manholes,
encroachments).

Deliberately separate from `road_health/schemas.py`: these are NOT Road
Health objects, carry no health/severity/priority fields, and nothing here
is ever read by `road_health/scoring.py`. See `app/assets/router.py` for
the "why a separate module" rationale.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ManholeResponse(BaseModel):
    """One real MCGM manhole (context/infrastructure, not a defect)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    object_id: str
    road_name: str | None = None
    ward: str | None = None
    latitude: float
    longitude: float
    status: str | None = None
    condition: str | None = None
    survey_date: datetime | None = None
    created_date: datetime | None = None
    last_edited_date: datetime | None = None
    remarks: str | None = None
    road_norm: str | None = None
    # The MCGM RoadSegment's public `segment_id` (e.g. "MCGM-2353"), not the
    # internal numeric FK -- None when this manhole could not be confidently
    # associated with an imported road (see the importer's 50m threshold).
    segment_id: str | None = None


class EncroachmentResponse(BaseModel):
    """One real MCGM encroachment complaint (context, not a defect or a hawker detection)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    object_id: str | None = None
    road_name: str | None = None
    ward: str | None = None
    latitude: float
    longitude: float
    status: str | None = None
    complaint_type: str | None = None
    description: str | None = None
    created_date: datetime | None = None
    last_edited_date: datetime | None = None
    segment_id: str | None = None


class SegmentAssetsResponse(BaseModel):
    """
    `GET /road-health/segments/{segment_id}/assets` response: the MCGM
    context layer for one road segment.

    Counts here are informational only -- never fed into Road Health
    scoring (see road_health/scoring.py, which only ever reads Defect rows).
    """

    segment_id: str
    manhole_count: int
    encroachment_count: int
    manholes: list[ManholeResponse]
    encroachments: list[EncroachmentResponse]
