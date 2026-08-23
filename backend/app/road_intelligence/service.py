"""
service.py
==========
The ONLY module the FastAPI backend needs to import.

    from road_intelligence.service import analyze
    from road_intelligence.schemas import AnalyzeRequest

    result = analyze(request)   # request: AnalyzeRequest, result: AnalyzeResponse

`analyze()` takes/returns pydantic models (the API contract) and
internally delegates to the pure-Python core (severity.py / ahp.py /
scoring.py). This keeps the scoring math decoupled from pydantic/FastAPI
so it stays unit-testable and reusable outside a request/response cycle.
"""

from __future__ import annotations

from . import scoring, severity
from .schemas import (
    AhpInfo,
    AnalyzeRequest,
    AnalyzeResponse,
    CriterionBreakdown as CriterionBreakdownSchema,
    PriorityBreakdown as PriorityBreakdownSchema,
    PriorityResult as PriorityResultSchema,
    SeverityBreakdown as SeverityBreakdownSchema,
    SeverityResult as SeverityResultSchema,
    WeightedContribution,
)


def _to_detection_data(detection) -> severity.DetectionData:
    return severity.DetectionData(
        class_id=detection.class_id,
        class_name=detection.class_name,
        confidence=detection.confidence,
        bbox=tuple(detection.bbox),  # type: ignore[arg-type]
        image_width=detection.image_width,
        image_height=detection.image_height,
    )


def _to_context_data(context) -> scoring.ContextData:
    return scoring.ContextData(
        latitude=context.latitude,
        longitude=context.longitude,
        timestamp=str(context.timestamp) if context.timestamp else None,
        road_type=context.road_type,
        traffic_criticality=context.traffic_criticality,
        recurrence_count=context.recurrence_count,
        location_criticality=context.location_criticality,
    )


def _severity_to_schema(result: severity.SeverityResult) -> SeverityResultSchema:
    b = result.breakdown
    return SeverityResultSchema(
        score=result.score,
        category=result.category,
        breakdown=SeverityBreakdownSchema(
            defect_type_score=b.defect_type_score,
            confidence_score=b.confidence_score,
            size_score=b.size_score,
            dimension_score=b.dimension_score,
            weighted_contributions=WeightedContribution(**b.weighted_contributions),
            data_flags=b.data_flags,
        ),
    )


def _priority_to_schema(result: scoring.PriorityResult) -> PriorityResultSchema:
    b = result.breakdown

    def _cb(c: scoring.CriterionBreakdown) -> CriterionBreakdownSchema:
        return CriterionBreakdownSchema(
            raw_value=c.raw_value,
            normalized_value=c.normalized_value,
            weight=c.weight,
            contribution=c.contribution,
            is_fallback=c.is_fallback,
        )

    return PriorityResultSchema(
        score=result.score,
        breakdown=PriorityBreakdownSchema(
            severity=_cb(b.severity),
            size=_cb(b.size),
            traffic_criticality=_cb(b.traffic_criticality),
            recurrence=_cb(b.recurrence),
            location_criticality=_cb(b.location_criticality),
        ),
        ahp=AhpInfo(
            criteria=result.ahp_criteria,
            weights=result.ahp_weights,
            consistency_ratio=result.consistency_ratio,
            is_consistent=result.is_consistent,
        ),
    )


def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Main entry point for the FastAPI route.

    Example (FastAPI route):

        @router.post("/road-intelligence/analyze", response_model=AnalyzeResponse)
        def analyze_defect(request: AnalyzeRequest) -> AnalyzeResponse:
            return road_intelligence_service.analyze(request)

    Raises:
        severity.InvalidDetectionError: structurally invalid detection input
            not already rejected by pydantic validation.
        scoring.InvalidContextError: structurally invalid (but present)
            context values.
    These should be caught by the FastAPI route/exception handler and
    translated into an HTTP 422, e.g.:

        @router.post("/road-intelligence/analyze")
        def analyze_defect(request: AnalyzeRequest):
            try:
                return road_intelligence_service.analyze(request)
            except (severity.InvalidDetectionError, scoring.InvalidContextError) as exc:
                raise HTTPException(status_code=422, detail=str(exc))
    """
    detection_data = _to_detection_data(request.detection)
    context_data = _to_context_data(request.context)

    severity_result = severity.estimate_severity(detection_data)
    geometry = severity.compute_bbox_geometry(detection_data)
    priority_result = scoring.calculate_priority(severity_result, geometry, context_data)

    return AnalyzeResponse(
        severity=_severity_to_schema(severity_result),
        priority=_priority_to_schema(priority_result),
    )
