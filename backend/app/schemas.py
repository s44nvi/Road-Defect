from pydantic import BaseModel


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
    defect_status: str