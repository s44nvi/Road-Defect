"""
schemas.py
==========
Pydantic response models for the Road Health API.

Two serialization conventions are emitted side by side, deliberately:

  * snake_case (`segment_id`, `health_score`, `critical_issues`, ...) -- the
    GeoJSON property contract specified for this feature.
  * camelCase (`segmentId`, `healthScore`, `criticalCount`, ...) -- the shape
    the existing officer frontend's `RoadSegmentHealth` / `RoadSegmentSummary`
    types consume.

The officer frontend is not part of this repository, so its exact type
definitions could not be inspected. Emitting both keys in the same
`properties` object satisfies either contract without the frontend changing a
line; extra keys are inert to a TypeScript consumer. If the frontend types
turn out to differ, adjust `SegmentProperties` here -- nothing else depends on
the wire names.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LineStringGeometry(BaseModel):
    """GeoJSON LineString, ready for the frontend to draw."""

    type: str = Field(default="LineString", examples=["LineString"])
    coordinates: list[list[float]] = Field(
        description="[[longitude, latitude], ...] in WGS84 degrees",
    )


class SegmentProperties(BaseModel):
    """
    GeoJSON `properties` for one road segment.

    Counting conventions:
        total_issues    == active_issues + resolved_issues + rejected_issues
        critical_issues + medium_issues + low_issues == active_issues
    """

    model_config = ConfigDict(populate_by_name=True)

    # --- snake_case contract -------------------------------------------------
    segment_id: str
    road_name: str
    segment_label: str
    length_km: float
    health_score: float
    health_status: str
    health_color: str
    total_issues: int
    active_issues: int
    resolved_issues: int
    rejected_issues: int
    critical_issues: int
    medium_issues: int
    low_issues: int
    # Status-level split of active_issues (reported + confirmed + in_progress
    # == active_issues). Additive: active_issues itself is unchanged.
    reported_issues: int
    confirmed_issues: int
    in_progress_issues: int
    geometry_source: str | None = None

    # --- camelCase mirror for the existing officer frontend ------------------
    segmentId: str
    roadName: str
    segmentLabel: str
    lengthKm: float
    healthScore: float
    healthStatus: str
    totalIssues: int
    activeIssues: int
    resolvedIssues: int
    criticalCount: int
    mediumCount: int
    lowCount: int
    reportedIssues: int
    confirmedIssues: int
    inProgressIssues: int


class SegmentFeature(BaseModel):
    """One GeoJSON Feature: road geometry plus its health properties."""

    type: str = Field(default="Feature", examples=["Feature"])
    geometry: LineStringGeometry
    properties: SegmentProperties


class SegmentFeatureCollection(BaseModel):
    """`GET /road-health/segments` response: a GeoJSON FeatureCollection."""

    type: str = Field(default="FeatureCollection", examples=["FeatureCollection"])
    features: list[SegmentFeature]


class SegmentDefect(BaseModel):
    """A defect as exposed on the segment detail response."""

    model_config = ConfigDict(populate_by_name=True)

    defect_id: int
    defect_type: str
    defect_status: str
    defect_severity: str
    latitude: float
    longitude: float
    is_active: bool
    is_test_data: bool

    # camelCase mirror
    defectId: int
    defectType: str
    defectStatus: str
    defectSeverity: str
    isActive: bool


class SegmentDetail(BaseModel):
    """`GET /road-health/segments/{segment_id}` response."""

    model_config = ConfigDict(populate_by_name=True)

    segment_id: str
    road_name: str
    segment_label: str
    geometry: LineStringGeometry
    length_km: float
    geometry_source: str | None
    health_score: float
    health_status: str
    health_color: str
    total_issues: int
    active_issues: int
    resolved_issues: int
    rejected_issues: int
    critical_issues: int
    medium_issues: int
    low_issues: int
    reported_issues: int
    confirmed_issues: int
    in_progress_issues: int
    active_issue_load: float
    load_density_per_km: float
    defects: list[SegmentDefect]

    # camelCase mirror of the frontend's RoadSegmentHealth contract
    segmentId: str
    roadName: str
    segmentLabel: str
    lengthKm: float
    healthScore: float
    healthStatus: str
    totalIssues: int
    activeIssues: int
    resolvedIssues: int
    criticalCount: int
    mediumCount: int
    lowCount: int
    reportedIssues: int
    confirmedIssues: int
    inProgressIssues: int


class StatusHistoryEntry(BaseModel):
    """One row of a defect's status timeline."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    defect_id: int
    old_status: str | None
    new_status: str
    changed_by: str | None
    changed_at: datetime
    note: str | None

    # camelCase mirror
    defectId: int
    oldStatus: str | None
    newStatus: str
    changedBy: str | None
    changedAt: datetime
