"""Pydantic schemas for API request/response validation"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class DefectType(str, Enum):
    POTHOLE = "pothole"
    CRACK = "crack"
    MANHOLE = "manhole"
    DEBRIS = "debris"
    HAWKER = "hawker"
    FALLEN_TREE = "fallen_tree"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DefectStatus(str, Enum):
    DETECTED = "detected"
    VERIFIED = "verified"
    SCHEDULED = "scheduled"
    REPAIRED = "repaired"
    VALIDATED = "validated"
    REJECTED = "rejected"


# ============ OBSERVATION SCHEMAS ============

class ObservationCreate(BaseModel):
    """Schema for uploading observation evidence"""
    defect_type: DefectType
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    detection_confidence: float = Field(..., ge=0, le=1)
    impact_magnitude: Optional[float] = None
    device_id: str
    gps_accuracy: Optional[float] = None
    heading: Optional[float] = None
    timestamp: datetime
    image_urls: List[str] = []
    video_url: Optional[str] = None


class ObservationResponse(BaseModel):
    """Schema for observation response"""
    id: uuid.UUID
    defect_id: uuid.UUID
    detection_confidence: float
    latitude: float
    longitude: float
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ============ DEFECT SCHEMAS ============

class DefectCreate(BaseModel):
    """Schema for creating defect"""
    defect_type: DefectType
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    severity: SeverityLevel


class DefectUpdate(BaseModel):
    """Schema for updating defect"""
    severity: Optional[SeverityLevel] = None
    status: Optional[DefectStatus] = None
    notes: Optional[str] = None


class DefectResponse(BaseModel):
    """Schema for defect response"""
    id: uuid.UUID
    defect_type: DefectType
    status: DefectStatus
    severity: SeverityLevel
    priority_score: float
    recurrence_count: int
    evidence_score: float
    latitude: float
    longitude: float
    created_at: datetime
    updated_at: datetime
    observation_count: int = 0
    
    class Config:
        from_attributes = True


class DefectListResponse(BaseModel):
    """Schema for paginated defect list"""
    total: int
    page: int
    page_size: int
    defects: List[DefectResponse]


# ============ VERIFICATION SCHEMAS ============

class DefectVerificationRequest(BaseModel):
    """Schema for officer verification"""
    verified: bool
    severity: Optional[SeverityLevel] = None
    notes: Optional[str] = None


class DefectVerificationResponse(BaseModel):
    """Schema for verification response"""
    defect_id: uuid.UUID
    verified: bool
    verified_by: uuid.UUID
    verified_at: datetime
    severity: SeverityLevel
    status: DefectStatus


# ============ REPAIR SCHEMAS ============

class RepairScheduleRequest(BaseModel):
    """Schema for scheduling repair"""
    assigned_crew: Optional[str] = None
    scheduled_date: datetime
    estimated_cost: Optional[float] = None
    notes: Optional[str] = None


class RepairResponse(BaseModel):
    """Schema for repair response"""
    id: uuid.UUID
    defect_id: uuid.UUID
    status: str
    assigned_crew: Optional[str]
    scheduled_date: Optional[datetime]
    completion_date: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ OFFICER SCHEMAS ============

class OfficerCreate(BaseModel):
    """Schema for officer registration"""
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None


class OfficerResponse(BaseModel):
    """Schema for officer response"""
    id: uuid.UUID
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    
    class Config:
        from_attributes = True


# ============ STATS SCHEMAS ============

class DashboardStats(BaseModel):
    """Schema for dashboard statistics"""
    total_defects: int
    defects_by_severity: dict  # {"low": 5, "medium": 10, ...}
    defects_by_status: dict    # {"detected": 10, "verified": 5, ...}
    pending_verification: int
    pending_repair: int
    completed_repairs: int
    average_priority_score: float
