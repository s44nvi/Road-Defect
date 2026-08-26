from pydantic import BaseModel, ConfigDict, Field

from .road_health.config import ALL_STATUSES


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

    # camelCase mirror for the officer frontend
    defectId: int
    defectType: str
    defectStatus: str
    defectSeverity: str
    roadSegmentId: str | None = None


class ImageReportResponse(DefectDetailResponse):
    """
    Response of `POST /reports/image`.

    A superset of `DefectDetailResponse` (itself a superset of
    `DefectResponse`), adding the fields that only exist for defects created
    through the image/detector pipeline: the AHP priority score and the
    stored source image path.
    """

    defect_priority: float | None = None
    image_path: str | None = None

    defectPriority: float | None = None
    imagePath: str | None = None
