"""
scoring.py
==========
Combines a SeverityResult (severity.py) with optional road/context data
into a final AHP-weighted priority_score in [0, 100].

Pure Python, no pydantic/FastAPI dependency (see severity.py docstring
for the rationale). `service.py` is the pydantic-facing adapter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from . import ahp, config
from .severity import BBoxGeometry, SeverityResult


class InvalidContextError(ValueError):
    """Raised when supplied (non-missing) context values are invalid."""


@dataclass(frozen=True)
class ContextData:
    """Plain-Python mirror of schemas.RoadContext. All fields optional."""

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[str] = None
    road_type: Optional[str] = None
    traffic_criticality: Optional[float] = None
    recurrence_count: Optional[int] = None
    location_criticality: Optional[float] = None


@dataclass(frozen=True)
class CriterionBreakdown:
    raw_value: Optional[float]
    normalized_value: float
    weight: float
    contribution: float
    is_fallback: bool


@dataclass(frozen=True)
class PriorityBreakdown:
    severity: CriterionBreakdown
    size: CriterionBreakdown
    traffic_criticality: CriterionBreakdown
    recurrence: CriterionBreakdown
    location_criticality: CriterionBreakdown


@dataclass(frozen=True)
class PriorityResult:
    score: float
    breakdown: PriorityBreakdown
    ahp_criteria: list[str]
    ahp_weights: dict[str, float]
    consistency_ratio: float
    is_consistent: bool


def _validate_context(ctx: ContextData) -> None:
    def _check_finite(name: str, value: Optional[float]) -> None:
        if value is None:
            return
        if isinstance(value, float) and (value != value or value in (math.inf, -math.inf)):
            raise InvalidContextError(f"{name} must be a finite number")

    _check_finite("traffic_criticality", ctx.traffic_criticality)
    _check_finite("location_criticality", ctx.location_criticality)

    if ctx.traffic_criticality is not None and not (0.0 <= ctx.traffic_criticality <= 1.0):
        raise InvalidContextError("traffic_criticality must be in [0, 1]")
    if ctx.location_criticality is not None and not (0.0 <= ctx.location_criticality <= 1.0):
        raise InvalidContextError("location_criticality must be in [0, 1]")
    if ctx.recurrence_count is not None and ctx.recurrence_count < 0:
        raise InvalidContextError("recurrence_count must not be negative")


def _severity_criterion(severity: SeverityResult) -> CriterionBreakdown:
    normalized = severity.score / 100.0
    return CriterionBreakdown(
        raw_value=severity.score,
        normalized_value=round(normalized, 4),
        weight=0.0,   # filled in by caller with AHP weight
        contribution=0.0,
        is_fallback=False,
    )


def _size_criterion(geometry: BBoxGeometry) -> CriterionBreakdown:
    if geometry.area_ratio is None:
        normalized = config.FALLBACK_SIZE_SCORE
        return CriterionBreakdown(
            raw_value=None, normalized_value=round(normalized, 4),
            weight=0.0, contribution=0.0, is_fallback=True,
        )
    normalized = min(1.0, geometry.area_ratio / config.SIZE_SATURATION_RATIO)
    return CriterionBreakdown(
        raw_value=round(geometry.area_ratio, 6),
        normalized_value=round(normalized, 4),
        weight=0.0, contribution=0.0, is_fallback=False,
    )


def _traffic_criterion(ctx: ContextData) -> CriterionBreakdown:
    if ctx.traffic_criticality is not None:
        return CriterionBreakdown(
            raw_value=ctx.traffic_criticality,
            normalized_value=round(ctx.traffic_criticality, 4),
            weight=0.0, contribution=0.0, is_fallback=False,
        )
    if ctx.road_type is not None:
        mapped = config.ROAD_TYPE_CRITICALITY.get(ctx.road_type.strip().lower())
        if mapped is not None:
            return CriterionBreakdown(
                raw_value=mapped, normalized_value=round(mapped, 4),
                weight=0.0, contribution=0.0, is_fallback=False,
            )
        # road_type provided but not recognized -> documented fallback,
        # flagged so callers/logs can surface the unmapped value.
    fallback = config.TRAFFIC_CRITICALITY_FALLBACK
    return CriterionBreakdown(
        raw_value=None, normalized_value=round(fallback, 4),
        weight=0.0, contribution=0.0, is_fallback=True,
    )


def _recurrence_criterion(ctx: ContextData) -> CriterionBreakdown:
    if ctx.recurrence_count is None:
        fallback = config.RECURRENCE_FALLBACK_NORMALIZED
        return CriterionBreakdown(
            raw_value=None, normalized_value=round(fallback, 4),
            weight=0.0, contribution=0.0, is_fallback=True,
        )
    normalized = min(1.0, ctx.recurrence_count / config.RECURRENCE_SATURATION_COUNT)
    return CriterionBreakdown(
        raw_value=float(ctx.recurrence_count),
        normalized_value=round(normalized, 4),
        weight=0.0, contribution=0.0, is_fallback=False,
    )


def _location_criterion(ctx: ContextData) -> CriterionBreakdown:
    if ctx.location_criticality is None:
        fallback = config.LOCATION_CRITICALITY_FALLBACK
        return CriterionBreakdown(
            raw_value=None, normalized_value=round(fallback, 4),
            weight=0.0, contribution=0.0, is_fallback=True,
        )
    return CriterionBreakdown(
        raw_value=ctx.location_criticality,
        normalized_value=round(ctx.location_criticality, 4),
        weight=0.0, contribution=0.0, is_fallback=False,
    )


def calculate_priority(
    severity: SeverityResult,
    geometry: BBoxGeometry,
    context: ContextData,
) -> PriorityResult:
    """Compute the AHP-weighted priority score for one detection.

    `severity` and `geometry` come from severity.estimate_severity() /
    severity.compute_bbox_geometry() for the SAME detection, so severity
    and size criteria are consistent with the severity breakdown already
    shown to the caller.
    """
    _validate_context(context)

    ahp_result = ahp.DEFAULT_AHP_RESULT
    weights = ahp_result.weights

    criteria_map = {
        "severity": _severity_criterion(severity),
        "size": _size_criterion(geometry),
        "traffic_criticality": _traffic_criterion(context),
        "recurrence": _recurrence_criterion(context),
        "location_criticality": _location_criterion(context),
    }

    total = 0.0
    finalized: dict[str, CriterionBreakdown] = {}
    for name, breakdown in criteria_map.items():
        w = weights[name]
        contribution = w * breakdown.normalized_value
        total += contribution
        finalized[name] = CriterionBreakdown(
            raw_value=breakdown.raw_value,
            normalized_value=breakdown.normalized_value,
            weight=round(w, 6),
            contribution=round(contribution, 6),
            is_fallback=breakdown.is_fallback,
        )

    score = round(min(100.0, max(0.0, total * 100.0)), 2)

    return PriorityResult(
        score=score,
        breakdown=PriorityBreakdown(**finalized),
        ahp_criteria=ahp_result.criteria,
        ahp_weights=weights,
        consistency_ratio=ahp_result.consistency_ratio,
        is_consistent=ahp_result.is_consistent,
    )
