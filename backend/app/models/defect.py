"""Database models for Road Defect Detection System"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from geoalchemy2 import Geometry
import uuid
import enum

from app.db import Base


class DefectStatus(str, enum.Enum):
    """Defect lifecycle states"""
    DETECTED = "detected"
    VERIFIED = "verified"
    SCHEDULED = "scheduled"
    REPAIRED = "repaired"
    VALIDATED = "validated"
    REJECTED = "rejected"


class DefectType(str, enum.Enum):
    """Types of road defects"""
    POTHOLE = "pothole"
    CRACK = "crack"
    MANHOLE = "manhole"
    DEBRIS = "debris"
    HAWKER = "hawker"
    FALLEN_TREE = "fallen_tree"


class SeverityLevel(str, enum.Enum):
    """Severity classification"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Defect(Base):
    """Persistent road defect entity"""
    __tablename__ = "defects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location = Column(Geometry("POINT", srid=4326), nullable=False, index=True)
    defect_type = Column(Enum(DefectType), nullable=False)
    status = Column(Enum(DefectStatus), default=DefectStatus.DETECTED, index=True)
    
    # Severity and priority
    severity = Column(Enum(SeverityLevel), nullable=False)
    priority_score = Column(Float, default=0.0, index=True)
    
    # Scores
    evidence_score = Column(Float, default=0.0)
    recurrence_count = Column(Integer, default=1)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("officers.id"), nullable=True)
    
    # Relationships
    observations = relationship("Observation", back_populates="defect", cascade="all, delete-orphan")
    repairs = relationship("Repair", back_populates="defect")
    
    def __repr__(self):
        return f"<Defect {self.id} {self.defect_type} {self.status}>"


class Observation(Base):
    """Individual evidence observation from a vehicle"""
    __tablename__ = "observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    defect_id = Column(UUID(as_uuid=True), ForeignKey("defects.id"), nullable=False, index=True)
    
    # Evidence
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    detection_confidence = Column(Float, nullable=False)
    impact_magnitude = Column(Float, nullable=True)
    
    # Media
    image_urls = Column(ARRAY(String), default=[])
    video_url = Column(String, nullable=True)
    
    # Device data
    device_id = Column(String, nullable=False, index=True)
    gps_accuracy = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, nullable=False, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    defect = relationship("Defect", back_populates="observations")
    
    def __repr__(self):
        return f"<Observation {self.id} {self.detection_confidence}>"


class Officer(Base):
    """Municipal officer account"""
    __tablename__ = "officers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Auth
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Role
    role = Column(String(50), default="officer")  # officer, admin, supervisor
    
    # Metadata
    full_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    assigned_area = Column(Geometry("POLYGON", srid=4326), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Officer {self.username}>"


class Repair(Base):
    """Repair work order for a defect"""
    __tablename__ = "repairs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    defect_id = Column(UUID(as_uuid=True), ForeignKey("defects.id"), nullable=False, index=True)
    
    # Status
    status = Column(String(50), default="scheduled")  # scheduled, in_progress, completed, failed
    
    # Assignment
    assigned_crew = Column(String(255), nullable=True)
    estimated_cost = Column(Float, nullable=True)
    
    # Timeline
    scheduled_date = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    
    # Post-repair
    before_image_urls = Column(ARRAY(String), default=[])
    after_image_urls = Column(ARRAY(String), default=[])
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    defect = relationship("Defect", back_populates="repairs")
    
    def __repr__(self):
        return f"<Repair {self.id} {self.status}>"
