from pydantic import BaseModel, ConfigDict, Field

from .road_health.config import ALL_STATUSES


class ReportCreate(BaseModel):
    defect_type: str
    defect_severity: str
    latitude: float
    longitude: float


class DefectResponse(BaseModel):
    defect_id: int
    defect_type: str
    defect_status: str
    defect_severity: str
    latitude: float
    longitude: float


class DefectStatusUpdate(BaseModel):
    """
    Body of the pre-existing `PATCH /defects/{defect_id}` endpoint.

    Unchanged shape, so existing Confirm/Reject callers keep working. The two
    optional fields are additive: officers using the newer workflow endpoint
    can also attribute and annotate a change here.
    """

    defect_status: str
    note: str | None = None
    changed_by: str | None = None


class DefectStatusChangeRequest(BaseModel):
    """
    Body of `PATCH /defects/{defect_id}/status`.

        {"status": "confirmed", "note": "Verified by municipal officer"}

    `changed_by` is optional because this project has no authentication layer;
    see `defect_workflow` for the documented limitation.
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
        description="Officer identifier, if the caller can supply one.",
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
