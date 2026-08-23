"""
schemas.py
==========
Pydantic v2 models defining the exact API contract between:

    YOLO detection output --> Road Intelligence module --> FastAPI --> PostgreSQL

These models are the boundary of the module. Everything inside
`severity.py` / `ahp.py` / `scoring.py` works with plain dataclasses
(see `scoring.py`) so that the core scoring logic has zero dependency on
pydantic/FastAPI and can be unit tested in isolation. `service.py`
converts between the two.

Requires: pydantic>=2.0 (standard for a FastAPI project). Not required
by severity.py / ahp.py / scoring.py themselves.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# INPUT: raw YOLO detection
# ---------------------------------------------------------------------------
class DetectionInput(BaseModel):
    """
    One YOLO detection for a single road defect.

    `bbox` is expected as [x_min, y_min, x_max, y_max] in pixel
    coordinates (standard YOLO/`xyxy` post-processing output). If the
    real pipeline emits normalized [0,1] coordinates or [x, y, w, h]
    instead, adapt `severity.compute_bbox_geometry` accordingly — the
    rest of the module is agnostic to that choice as long as
    `bbox_area_ratio` ends up in [0, 1].
    """

    class_id: int = Field(..., description="YOLO integer class id")
    class_name: str = Field(..., min_length=1, description="YOLO class label, e.g. 'pothole'")
    confidence: float = Field(..., description="YOLO detection confidence")
    bbox: list[float] = Field(..., description="[x_min, y_min, x_max, y_max] in pixels")
    image_width: Optional[int] = Field(default=None, gt=0, description="Source image width in px")
    image_height: Optional[int] = Field(default=None, gt=0, description="Source image height in px")

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if v != v:  # NaN check (NaN != NaN)
            raise ValueError("confidence must not be NaN")
        if v in (float("inf"), float("-inf")):
            raise ValueError("confidence must not be infinite")
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {v}")
        return v

    @field_validator("bbox")
    @classmethod
    def bbox_is_valid(cls, v: list[float]) -> list[float]:
        if len(v) != 4:
            raise ValueError("bbox must have exactly 4 values: [x_min, y_min, x_max, y_max]")
        for coord in v:
            if coord != coord or coord in (float("inf"), float("-inf")):
                raise ValueError("bbox coordinates must be finite numbers")
        x_min, y_min, x_max, y_max = v
        if x_min < 0 or y_min < 0:
            raise ValueError("bbox coordinates must not be negative")
        if x_max <= x_min or y_max <= y_min:
            raise ValueError("bbox must have positive width and height (x_max>x_min, y_max>y_min)")
        return v

    @model_validator(mode="after")
    def bbox_within_image(self) -> "DetectionInput":
        if self.image_width is not None and self.bbox[2] > self.image_width:
            raise ValueError("bbox x_max exceeds image_width")
        if self.image_height is not None and self.bbox[3] > self.image_height:
            raise ValueError("bbox y_max exceeds image_height")
        return self


# ---------------------------------------------------------------------------
# INPUT: optional road/context data
# ---------------------------------------------------------------------------
class RoadContext(BaseModel):
    """
    Optional contextual information used only by the AHP priority stage.
    ALL fields are optional — see config.py for the documented fallback
    used whenever a field is missing.
    """

    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    timestamp: Optional[datetime] = Field(default=None, description="Detection capture time (UTC)")

    road_type: Optional[str] = Field(
        default=None,
        description="One of: local, collector, arterial, highway (see config.ROAD_TYPE_CRITICALITY). "
                    "Used only if traffic_criticality is not provided directly.",
    )
    traffic_criticality: Optional[float] = Field(
        default=None, ge=0, le=1,
        description="Pre-normalized [0,1] road-importance score. Takes precedence over road_type.",
    )
    recurrence_count: Optional[int] = Field(
        default=None, ge=0,
        description="Number of prior/co-located defect detections in this road segment/cluster.",
    )
    location_criticality: Optional[float] = Field(
        default=None, ge=0, le=1,
        description="Pre-normalized [0,1] proximity-to-critical-infrastructure score "
                    "(schools/hospitals/junctions/transit). Must be computed upstream by the "
                    "backend/GIS layer — this module has no infrastructure data of its own.",
    )

    @field_validator("road_type")
    @classmethod
    def road_type_known(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip().lower()


# ---------------------------------------------------------------------------
# UNIFIED REQUEST
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    detection: DetectionInput
    context: RoadContext = Field(default_factory=RoadContext)


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------
class WeightedContribution(BaseModel):
    defect_type: float
    confidence: float
    size: float
    dimension: float


class SeverityBreakdown(BaseModel):
    defect_type_score: float
    confidence_score: float
    size_score: float
    dimension_score: float
    weighted_contributions: WeightedContribution
    data_flags: dict[str, bool] = Field(
        default_factory=dict,
        description="e.g. {'size_estimated': true} when image dimensions were missing "
                    "and a fallback value was used instead of a real measurement.",
    )


class SeverityResult(BaseModel):
    score: float = Field(..., ge=0, le=100)
    category: str
    breakdown: SeverityBreakdown


class CriterionBreakdown(BaseModel):
    raw_value: Optional[float] = None
    normalized_value: float
    weight: float
    contribution: float
    is_fallback: bool = Field(
        default=False, description="True if this criterion used a documented fallback "
                                    "because the source data was not provided."
    )


class AhpInfo(BaseModel):
    criteria: list[str]
    weights: dict[str, float]
    consistency_ratio: float
    is_consistent: bool


class PriorityBreakdown(BaseModel):
    severity: CriterionBreakdown
    size: CriterionBreakdown
    traffic_criticality: CriterionBreakdown
    recurrence: CriterionBreakdown
    location_criticality: CriterionBreakdown


class PriorityResult(BaseModel):
    score: float = Field(..., ge=0, le=100)
    breakdown: PriorityBreakdown
    ahp: AhpInfo


class AnalyzeResponse(BaseModel):
    severity: SeverityResult
    priority: PriorityResult
