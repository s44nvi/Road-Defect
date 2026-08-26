from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .road_health.config import ALL_STATUSES

ALLOWED_SEVERITIES = ("low", "medium", "high", "critical")


class ReportCreate(BaseModel):
    defect_type: str
    defect_severity: str
    latitude: float
    longitude: float


class DefectResponse(BaseModel):
    """
    Unchanged since before the pothole image pipeline -- this is also the
    response shape of the legacy `PATCH /defects/{defect_id}` endpoint, which
    must keep its exact original key set. `POST /reports` and `GET /defects`
    use `DefectResponseWithPriority` below instead.
    """

    defect_id: int
    defect_type: str
    defect_status: str
    defect_severity: str
    latitude: float
    longitude: float


class DefectResponseWithPriority(DefectResponse):
    """
    `DefectResponse` plus the AHP priority score, for the two routes that
    need to expose it: `POST /reports` and `GET /defects`.

    Additive/optional: JSON-only reports created through POST /reports have
    no detection to score and always return null here; only defects created
    through POST /reports/image populate it. See models.Defect.defect_priority.
    """

    defect_priority: float | None = None


class DefectStatusUpdate(BaseModel):
    """
    Body of the pre-existing `PATCH /defects/{defect_id}` endpoint.

    Unchanged shape, so existing Confirm/Reject callers keep working.
    `changed_by` is accepted for backwards compatibility but its value is
    ignored -- the route now derives the acting officer from the
    authenticated bearer token (`Depends(get_current_officer)`), never from
    a client-supplied field. Trusting a client-supplied identity here would
    let one officer impersonate another.
    """

    defect_status: str
    note: str | None = None
    changed_by: str | None = None


class DefectStatusChangeRequest(BaseModel):
    """
    Body of `PATCH /defects/{defect_id}/status`.

        {"status": "confirmed", "note": "Verified by municipal officer"}

    Requires `Authorization: Bearer <officer access token>`
    (`Depends(get_current_officer)` on the route). `changed_by` is accepted
    for backwards compatibility but its value is ignored -- the acting
    officer is always the authenticated principal, never a client-supplied
    field, so one officer cannot impersonate another.
    """

    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(
        description=f"One of: {', '.join(ALL_STATUSES)}",
        examples=["confirmed"],
    )
    note: str | None = Field(
        default=None,
        examples=["Verified by municipal officer"],
    )
    changed_by: str | None = Field(
        default=None,
        alias="changedBy",
        description="Ignored. Retained only for backwards compatibility; "
                     "the acting officer is derived from the auth token.",
    )


class DefectSeverityUpdate(BaseModel):
    """
    Body of `PATCH /defects/{defect_id}/severity`.

        {"defect_severity": "critical"}

    Requires `Authorization: Bearer <officer access token>`
    (`Depends(get_current_officer)` on the route).
    """

    defect_severity: str = Field(
        description=f"One of: {', '.join(ALLOWED_SEVERITIES)}",
        examples=["critical"],
    )

    @field_validator("defect_severity")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_SEVERITIES:
            raise ValueError(
                f"defect_severity must be one of: {', '.join(ALLOWED_SEVERITIES)}"
            )
        return normalized


class PublicIssueResponse(BaseModel):
    """
    `GET /community/issues` response: one publicly-visible defect.

    Deliberately a distinct, narrower schema from `DefectDetailResponse`
    (the officer view) -- only confirmed/in_progress/resolved defects are
    ever serialized into this shape, and only the fields Saanvi's community
    map needs are exposed (no `image_path`, no `is_test_data`, etc).

    `observation_count` reflects the current data model, where each citizen
    report is its own `Defect` row with no deduplication/merging of repeat
    reports for the same real-world issue -- it is always 1 today. Once a
    dedup/merge mechanism exists this is the field to start incrementing.
    """

    model_config = ConfigDict(populate_by_name=True)

    defect_id: int
    defect_type: str
    defect_status: str
    defect_severity: str
    latitude: float
    longitude: float
    road_segment_id: str | None = None
    observation_count: int

    # camelCase mirror, consistent with the rest of the API
    defectId: int
    defectType: str
    defectStatus: str
    defectSeverity: str
    roadSegmentId: str | None = None
    observationCount: int


class ReporterPublic(BaseModel):
    """
    The citizen who submitted a defect, as the officer view is allowed to
    see them.

    An explicit allowlist, not the `Citizen` ORM row -- same convention as
    `auth.schemas.CitizenPublic` (which this mirrors): `password_hash` is
    never a field here, so there is no field to accidentally serialize.
    `full_name` is the one guaranteed field; `email` is included because
    `CitizenPublic` already exposes it in the citizen's own login response,
    so it is not new sensitive surface, just the same allowlist reused for
    the officer's view of the same citizen.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int
    full_name: str
    email: str


class DefectDetailResponse(BaseModel):
    """
    `DefectResponse` plus the road-health fields the officer view needs.

    A superset of `DefectResponse`, so it is safe wherever that was returned.
    """

    model_config = ConfigDict(populate_by_name=True)

    defect_id: int
    defect_type: str
    defect_status: str
    defect_severity: str
    latitude: float
    longitude: float
    road_segment_id: str | None = None
    is_test_data: bool = False
    # None for legacy/anonymous defects (created through the unauthenticated
    # `POST /reports`, or predating citizen association) -- never fabricated.
    reporter: ReporterPublic | None = None

    # camelCase mirror for the officer frontend
    defectId: int
    defectType: str
    defectStatus: str
    defectSeverity: str
    roadSegmentId: str | None = None

    # AI detection metadata (populated for defects created through the
    # analyze/submit or /reports/image pipelines; None for JSON-only or
    # legacy reports -- never fabricated).
    ai_confidence: float | None = None
    ai_bbox: list[float] | None = None
    ai_severity_score: float | None = None
    defect_priority: float | None = None
    image_path: str | None = None
    image_url: str | None = None
    # Timeline: when the "reported" status entry was written, converted to
    # IST for display (see timezone_utils.to_ist). None only for defects
    # with no status history at all (should not happen in practice, since
    # every creation path calls record_initial_status).
    reported_at: datetime | None = None

    aiConfidence: float | None = None
    aiBbox: list[float] | None = None
    aiSeverityScore: float | None = None
    defectPriority: float | None = None
    imagePath: str | None = None
    imageUrl: str | None = None
    reportedAt: datetime | None = None


class ImageReportResponse(DefectDetailResponse):
    """
    Response of `POST /reports/image`.

    A superset of `DefectDetailResponse` (itself a superset of
    `DefectResponse`). `defect_priority`/`image_path` etc. now live directly
    on `DefectDetailResponse` (added for the officer detail view), so this
    subclass exists only for backwards-compat naming/import stability.
    """


class AnalyzeImageResponse(BaseModel):
    """
    Response of `POST /reports/analyze`.

    Pure AI analysis -- no `Defect` row is created by this endpoint. Returns
    the real detected category (never a fabricated default) and a reference
    token the citizen's final `POST /reports/submit` call uses to reuse the
    already-persisted image without re-uploading it.

    `category`/`confidence`/`bbox` are all `None` together when nothing was
    confidently detected -- an explicit "no detection" result, not a guess.
    """

    model_config = ConfigDict(populate_by_name=True)

    image_token: str
    category: str | None = None
    confidence: float | None = None
    bbox: list[float] | None = None
    ai_severity: str | None = None
    ai_severity_score: float | None = None
    model_source: str | None = None

    imageToken: str
    aiSeverity: str | None = None
    aiSeverityScore: float | None = None
    modelSource: str | None = None


class SubmitReportRequest(BaseModel):
    """
    Body of `POST /reports/submit`.

    `image_token` must reference an image already persisted by a prior
    `POST /reports/analyze` call. `defect_type`/`defect_severity` are the
    citizen's final chosen category/severity (which may differ from the AI
    suggestion returned by `/analyze` -- the citizen has the final say).
    """

    model_config = ConfigDict(populate_by_name=True)

    image_token: str = Field(alias="imageToken")
    latitude: float
    longitude: float
    defect_type: str = Field(alias="defectType")
    defect_severity: str = Field(alias="defectSeverity")

    @field_validator("defect_severity")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_SEVERITIES:
            raise ValueError(
                f"defect_severity must be one of: {', '.join(ALLOWED_SEVERITIES)}"
            )
        return normalized


class NearbyIncidentResponse(BaseModel):
    """
    One item of `GET /reports/nearby`.

    A read-only search result -- distinct from `DefectDetailResponse` (the
    officer detail view) because it deliberately never carries reporter PII
    and adds `distance_km` (computed for this search, not stored) plus the
    best-effort `nearest_road`/`road_segment_id` from the defect's existing
    snapped segment (see `road_health_service.assign_defect_to_segment`,
    already run at creation time -- this endpoint does not compute or
    fabricate any new road geometry).
    """

    model_config = ConfigDict(populate_by_name=True)

    defect_id: int
    defect_type: str
    defect_severity: str
    defect_priority: float | None = None
    latitude: float
    longitude: float
    distance_km: float
    defect_status: str
    reported_at: datetime | None = None
    image_url: str | None = None
    road_segment_id: str | None = None
    nearest_road: str | None = None

    # camelCase mirror, consistent with the rest of the API
    defectId: int
    defectType: str
    defectSeverity: str
    defectPriority: float | None = None
    distanceKm: float
    defectStatus: str
    reportedAt: datetime | None = None
    imageUrl: str | None = None
    roadSegmentId: str | None = None
    nearestRoad: str | None = None


class HawkerDetectionItem(BaseModel):
    """
    One hawker detection from `POST /ml/hawkers/detect`, and the `Defect`
    row persisted from it.

    Reuses the same field set/naming convention as `ImageReportResponse`
    (`defect_severity`/`defect_priority`/`image_path` etc.) plus the raw
    detection fields (`class_name`/`confidence`/`bbox`) the frontend needs
    to draw the detection box, since one hawker image can produce several
    of these (unlike the single-defect pothole pipeline).
    """

    model_config = ConfigDict(populate_by_name=True)

    defect_id: int
    class_name: str
    confidence: float
    bbox: list[float]
    defect_severity: str
    severity_score: float
    defect_priority: float
    latitude: float
    longitude: float
    road_segment_id: str | None = None
    image_path: str

    # camelCase mirror, consistent with the rest of the API
    defectId: int
    className: str
    defectSeverity: str
    severityScore: float
    defectPriority: float
    roadSegmentId: str | None = None
    imagePath: str


class HawkerDetectionResponse(BaseModel):
    """`POST /ml/hawkers/detect` response: every hawker Defect created from the uploaded image."""

    model_config = ConfigDict(populate_by_name=True)

    filename: str | None = None
    detections: list[HawkerDetectionItem]
