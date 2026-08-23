"""
severity.py
===========
Deterministic, explainable severity scoring for a single YOLO road-defect
detection.

Design note: this module intentionally has NO dependency on pydantic or
FastAPI. It works with a plain `DetectionData` dataclass so the scoring
logic can be unit tested in complete isolation and reused outside a web
context (batch jobs, notebooks, etc). `service.py` is the adapter that
converts pydantic <-> these dataclasses.

severity_score is always in [0, 100]. Higher = more severe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from . import config


class InvalidDetectionError(ValueError):
    """Raised when detection input values are structurally invalid
    (NaN, infinite, negative, zero-area, out of range, etc.)."""


@dataclass(frozen=True)
class DetectionData:
    """Plain-Python mirror of schemas.DetectionInput."""

    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x_min, y_min, x_max, y_max
    image_width: Optional[int] = None
    image_height: Optional[int] = None


@dataclass(frozen=True)
class BBoxGeometry:
    width: float
    height: float
    area: float
    aspect_ratio: float
    area_ratio: Optional[float]        # None if image dims unavailable
    width_frac: Optional[float]        # bbox width / image width
    height_frac: Optional[float]       # bbox height / image height


@dataclass(frozen=True)
class SeverityBreakdown:
    defect_type_score: float
    confidence_score: float
    size_score: float
    dimension_score: float
    weighted_contributions: dict[str, float]
    data_flags: dict[str, bool]


@dataclass(frozen=True)
class SeverityResult:
    score: float
    category: str
    breakdown: SeverityBreakdown


def _validate_detection(d: DetectionData) -> None:
    """Structural validation. Raises InvalidDetectionError on failure.

    NOTE: schemas.DetectionInput (pydantic) already enforces most of this
    at the API boundary. This function re-validates so `severity.py`
    stays safe to call directly (e.g. from tests, batch scripts) without
    going through pydantic.
    """
    conf = d.confidence
    if conf != conf or conf in (math.inf, -math.inf):
        raise InvalidDetectionError("confidence must be a finite number")
    if not (0.0 <= conf <= 1.0):
        raise InvalidDetectionError(f"confidence must be in [0, 1], got {conf}")

    if len(d.bbox) != 4:
        raise InvalidDetectionError("bbox must have exactly 4 values")
    for v in d.bbox:
        if v != v or v in (math.inf, -math.inf):
            raise InvalidDetectionError("bbox coordinates must be finite numbers")

    x_min, y_min, x_max, y_max = d.bbox
    if x_min < 0 or y_min < 0:
        raise InvalidDetectionError("bbox coordinates must not be negative")
    if x_max <= x_min or y_max <= y_min:
        raise InvalidDetectionError("bbox must have positive width and height")

    if d.image_width is not None and d.image_width <= 0:
        raise InvalidDetectionError("image_width must be positive if provided")
    if d.image_height is not None and d.image_height <= 0:
        raise InvalidDetectionError("image_height must be positive if provided")
    if d.image_width is not None and x_max > d.image_width:
        raise InvalidDetectionError("bbox x_max exceeds image_width")
    if d.image_height is not None and y_max > d.image_height:
        raise InvalidDetectionError("bbox y_max exceeds image_height")


def compute_bbox_geometry(d: DetectionData) -> BBoxGeometry:
    """Derive width/height/area/aspect_ratio and, where possible,
    frame-relative ratios from the bounding box.

    LIMITATION (documented per task spec): bbox area is a 2D pixel-space
    measurement of the detection box, NOT the physical surface area of
    the defect. A pothole's actual damaged area is generally smaller than
    (and a different shape than) its bounding box, and pixel area is also
    a function of camera distance/angle, not true physical size. This
    module treats bbox-derived size as a proxy signal for severity, not a
    physical measurement.
    """
    x_min, y_min, x_max, y_max = d.bbox
    width = x_max - x_min
    height = y_max - y_min
    area = width * height
    aspect_ratio = width / height if height > 0 else 0.0

    area_ratio: Optional[float] = None
    width_frac: Optional[float] = None
    height_frac: Optional[float] = None
    if d.image_width and d.image_height:
        image_area = d.image_width * d.image_height
        area_ratio = area / image_area if image_area > 0 else None
        width_frac = width / d.image_width
        height_frac = height / d.image_height

    return BBoxGeometry(
        width=width,
        height=height,
        area=area,
        aspect_ratio=aspect_ratio,
        area_ratio=area_ratio,
        width_frac=width_frac,
        height_frac=height_frac,
    )


def _defect_type_score(class_name: str) -> float:
    """Baseline severity in [0, 1] for this defect class (config-driven)."""
    return config.DEFECT_TYPE_BASE_SEVERITY.get(
        class_name.strip().lower(), config.UNKNOWN_DEFECT_TYPE_SEVERITY
    )


def _confidence_score(confidence: float) -> float:
    """Confidence is already a natural [0,1] evidence-strength signal."""
    return confidence


def _size_score(geometry: BBoxGeometry) -> tuple[float, bool]:
    """Returns (score, was_estimated_via_fallback)."""
    if geometry.area_ratio is None:
        return config.FALLBACK_SIZE_SCORE, True
    score = min(1.0, geometry.area_ratio / config.SIZE_SATURATION_RATIO)
    return max(0.0, score), False


def _dimension_score(geometry: BBoxGeometry) -> tuple[float, bool]:
    """Frame-extent score: how far the defect stretches across the frame
    in its longer dimension (captures elongated cracks that area alone
    under-represents). Returns (score, was_estimated_via_fallback)."""
    if geometry.width_frac is None or geometry.height_frac is None:
        return config.FALLBACK_DIMENSION_SCORE, True
    extent = max(geometry.width_frac, geometry.height_frac)
    score = min(1.0, extent / config.DIMENSION_SATURATION_RATIO)
    return max(0.0, score), False


def _category_for_score(score: float) -> str:
    for low, high, label in config.SEVERITY_CATEGORY_THRESHOLDS:
        if low <= score <= high:
            return label
    # Should be unreachable given thresholds cover [0,100], but fail safe:
    return config.SEVERITY_CATEGORY_THRESHOLDS[-1][2]


def estimate_severity(detection: DetectionData) -> SeverityResult:
    """Compute the full, explainable severity result for one detection.

    Raises InvalidDetectionError for structurally invalid input.
    """
    _validate_detection(detection)

    geometry = compute_bbox_geometry(detection)

    defect_type_score = _defect_type_score(detection.class_name)
    confidence_score = _confidence_score(detection.confidence)
    size_score, size_estimated = _size_score(geometry)
    dimension_score, dimension_estimated = _dimension_score(geometry)

    w = config.SEVERITY_WEIGHTS
    contributions = {
        "defect_type": w["defect_type"] * defect_type_score,
        "confidence": w["confidence"] * confidence_score,
        "size": w["size"] * size_score,
        "dimension": w["dimension"] * dimension_score,
    }

    raw_score = sum(contributions.values())  # in [0, 1] by construction
    score = round(min(100.0, max(0.0, raw_score * 100.0)), 2)
    category = _category_for_score(score)

    data_flags = {
        "size_estimated": size_estimated,
        "dimension_estimated": dimension_estimated,
        "defect_type_unmapped": detection.class_name.strip().lower()
        not in config.DEFECT_TYPE_BASE_SEVERITY,
    }

    breakdown = SeverityBreakdown(
        defect_type_score=round(defect_type_score, 4),
        confidence_score=round(confidence_score, 4),
        size_score=round(size_score, 4),
        dimension_score=round(dimension_score, 4),
        weighted_contributions={k: round(v, 4) for k, v in contributions.items()},
        data_flags=data_flags,
    )

    return SeverityResult(score=score, category=category, breakdown=breakdown)
