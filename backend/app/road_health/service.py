"""
service.py
==========
Database-facing layer for Road Health: reads canonical `road_segments` +
`defects` rows and builds the API payloads.

Health is ALWAYS computed on read from the current rows -- no score is ever
stored. That is deliberate: a stored score can go stale the moment a defect's
status, severity, or segment changes, and there is no cache here that could
disagree with the database. The aggregation is a single indexed query plus
arithmetic over a handful of rows per segment, so recomputation is cheap.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Defect, RoadSegment
from . import scoring
from .assignment import SegmentGeometry, find_nearest_segment
from .geo import InvalidGeometryError, parse_linestring
from .scoring import DefectLoad, HealthResult


def _segment_label(segment: RoadSegment) -> str:
    """Stored label, or a readable fallback derived from the row."""
    if segment.segment_label:
        return segment.segment_label

    return f"{segment.road_name} - {segment.segment_id}"


def _geometry_payload(segment: RoadSegment) -> dict:
    """Validate stored geometry and return it as a GeoJSON geometry object."""
    coordinates = parse_linestring(segment.geometry)

    return {"type": "LineString", "coordinates": coordinates}


def load_segment_defects(db: Session, segment: RoadSegment) -> list[Defect]:
    """Every defect currently assigned to this segment, ordered by id."""
    return (
        db.query(Defect)
        .filter(Defect.road_segment_id == segment.id)
        .order_by(Defect.id)
        .all()
    )


def evaluate(defects: list[Defect], length_km: float) -> HealthResult:
    """Score a segment from its ORM defect rows."""
    return scoring.evaluate_segment(
        [DefectLoad(status=d.defect_status, severity=d.defect_severity) for d in defects],
        length_km,
    )


def _status_breakdown(defects: list[Defect]) -> dict[str, int]:
    """
    Status-level split of the active defects on a segment
    (reported/confirmed/in_progress). `scoring.evaluate_segment` only
    reports the aggregate `active_issues` count -- this is computed
    separately, straight from the raw statuses, so it never has to touch
    the health-scoring formula itself.

    `reported_issues + confirmed_issues + in_progress_issues == active_issues`.
    """
    counts = {"reported": 0, "confirmed": 0, "in_progress": 0}

    for defect in defects:
        status = scoring.normalize_status(defect.defect_status)
        if status in counts:
            counts[status] += 1

    return counts


def _properties(segment: RoadSegment, health: HealthResult, status_counts: dict[str, int]) -> dict:
    """
    GeoJSON `properties` for one segment.

    Emits snake_case (the specified GeoJSON contract) and camelCase (what the
    existing officer frontend's RoadSegmentHealth type reads) side by side --
    see road_health/schemas.py for why.
    """
    label = _segment_label(segment)
    length_km = round(float(segment.length_km), 2)

    return {
        # snake_case contract
        "segment_id": segment.segment_id,
        "road_name": segment.road_name,
        "segment_label": label,
        "length_km": length_km,
        "health_score": health.health_score,
        "health_status": health.health_status,
        "health_color": health.health_color,
        "total_issues": health.total_issues,
        "active_issues": health.active_issues,
        "resolved_issues": health.resolved_issues,
        "rejected_issues": health.rejected_issues,
        "critical_issues": health.critical_issues,
        "medium_issues": health.medium_issues,
        "low_issues": health.low_issues,
        "reported_issues": status_counts["reported"],
        "confirmed_issues": status_counts["confirmed"],
        "in_progress_issues": status_counts["in_progress"],
        "geometry_source": segment.geometry_source,
        # camelCase mirror for the existing frontend contract
        "segmentId": segment.segment_id,
        "roadName": segment.road_name,
        "segmentLabel": label,
        "lengthKm": length_km,
        "healthScore": health.health_score,
        "healthStatus": health.health_status,
        "totalIssues": health.total_issues,
        "activeIssues": health.active_issues,
        "resolvedIssues": health.resolved_issues,
        "criticalCount": health.critical_issues,
        "mediumCount": health.medium_issues,
        "lowCount": health.low_issues,
        "reportedIssues": status_counts["reported"],
        "confirmedIssues": status_counts["confirmed"],
        "inProgressIssues": status_counts["in_progress"],
    }


def build_feature(db: Session, segment: RoadSegment) -> dict:
    """One GeoJSON Feature for a segment, with freshly computed health."""
    defects = load_segment_defects(db, segment)
    health = evaluate(defects, segment.length_km)

    return {
        "type": "Feature",
        "geometry": _geometry_payload(segment),
        "properties": _properties(segment, health, _status_breakdown(defects)),
    }


def build_feature_collection(db: Session) -> dict:
    """
    `GET /road-health/segments` payload.

    Segments whose stored geometry is unusable are skipped rather than failing
    the whole collection -- one bad import must not blank the officer's map.
    """
    segments = db.query(RoadSegment).order_by(RoadSegment.segment_id).all()

    features = []

    for segment in segments:
        try:
            features.append(build_feature(db, segment))
        except InvalidGeometryError:
            continue

    return {"type": "FeatureCollection", "features": features}


def _defect_payload(defect: Defect) -> dict:
    """One defect on the segment detail response, in both key conventions."""
    is_active = scoring.is_active(defect.defect_status)

    return {
        "defect_id": defect.id,
        "defect_type": defect.defect_type,
        "defect_status": defect.defect_status,
        "defect_severity": defect.defect_severity,
        "latitude": defect.latitude,
        "longitude": defect.longitude,
        "is_active": is_active,
        "is_test_data": bool(defect.is_test_data),
        "defectId": defect.id,
        "defectType": defect.defect_type,
        "defectStatus": defect.defect_status,
        "defectSeverity": defect.defect_severity,
        "isActive": is_active,
    }


def get_segment(db: Session, segment_id: str) -> RoadSegment | None:
    """Look a segment up by its public `segment_id` (e.g. 'SEG-001')."""
    return (
        db.query(RoadSegment)
        .filter(RoadSegment.segment_id == segment_id)
        .first()
    )


def build_segment_detail(db: Session, segment: RoadSegment) -> dict:
    """`GET /road-health/segments/{segment_id}` payload."""
    defects = load_segment_defects(db, segment)
    health = evaluate(defects, segment.length_km)

    detail = dict(_properties(segment, health, _status_breakdown(defects)))
    detail["geometry"] = _geometry_payload(segment)
    detail["active_issue_load"] = health.active_load
    detail["load_density_per_km"] = health.load_density
    detail["defects"] = [_defect_payload(defect) for defect in defects]

    return detail


# ---------------------------------------------------------------------------
# Defect -> segment assignment
# ---------------------------------------------------------------------------
def segment_candidates(db: Session) -> list[SegmentGeometry]:
    """All segments as snapping candidates, in deterministic order."""
    segments = db.query(RoadSegment).order_by(RoadSegment.segment_id).all()

    return [
        SegmentGeometry(id=s.id, segment_id=s.segment_id, geometry=s.geometry)
        for s in segments
    ]


def assign_defect_to_segment(db: Session, defect: Defect) -> int | None:
    """
    Set `defect.road_segment_id` to the nearest segment within the snapping
    tolerance, or leave it unassigned. Does not commit.

    Returns the assigned segment primary key, or `None` when the defect is not
    close enough to any known road.
    """
    result = find_nearest_segment(
        defect.latitude,
        defect.longitude,
        segment_candidates(db),
    )

    defect.road_segment_id = result.segment_pk

    return result.segment_pk
