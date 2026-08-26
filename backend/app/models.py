from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    false,
)
from sqlalchemy.orm import relationship

from .database import Base


class RoadSegment(Base):
    __tablename__ = "road_segments"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(String(50), unique=True, nullable=False, index=True)
    road_name = Column(String(255), nullable=False)
    geometry = Column(JSON, nullable=False)
    length_km = Column(Float, nullable=False)

    # Human-friendly label for this segment.
    segment_label = Column(String(255), nullable=True)

    # Provenance of the stored geometry.
    geometry_source = Column(String(100), nullable=True)

    # MCGM source metadata.
    mcgm_id = Column(String(50), nullable=True, index=True)
    ward = Column(String(50), nullable=True)
    work_status = Column(String(100), nullable=True)
    source_length_m = Column(Float, nullable=True)

    # Road defects are the ONLY contextual layer currently used
    # by Road Health scoring.
    defects = relationship(
        "Defect",
        back_populates="road_segment",
    )

    # MCGM infrastructure/context layer.
    # These do NOT participate in Road Health scoring.
    manholes = relationship(
        "Manhole",
        back_populates="road_segment",
    )

    # MCGM roadside/encroachment context layer.
    # These do NOT participate in Road Health scoring.
    encroachments = relationship(
        "Encroachment",
        back_populates="road_segment",
    )


class Defect(Base):
    __tablename__ = "defects"

    id = Column(Integer, primary_key=True, index=True)
    defect_type = Column(String, nullable=False)
    defect_status = Column(String, nullable=False, default="reported")
    defect_severity = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Priority score from Road Intelligence/AHP.
    defect_priority = Column(Float, nullable=True)

    # Uploaded source image.
    image_path = Column(String, nullable=True)

    # AI detection metadata, populated by the analyze/submit pipeline
    # (POST /reports/analyze + POST /reports/submit). Nullable: not every
    # Defect is created from an AI-analyzed image (e.g. POST /reports,
    # legacy seed data), so these stay optional rather than backfilled.
    ai_confidence = Column(Float, nullable=True)
    ai_bbox = Column(JSON, nullable=True)
    ai_severity_score = Column(Float, nullable=True)
    ai_model_source = Column(String, nullable=True)

    # Development/test data marker.
    is_test_data = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    road_segment_id = Column(
        Integer,
        ForeignKey("road_segments.id"),
        nullable=True,
        index=True,
    )

    road_segment = relationship(
        "RoadSegment",
        back_populates="defects",
    )

    citizen_id = Column(
        Integer,
        ForeignKey("citizens.id"),
        nullable=True,
        index=True,
    )

    citizen = relationship(
        "Citizen",
        back_populates="defects",
    )

    status_history = relationship(
        "DefectStatusHistory",
        back_populates="defect",
        cascade="all, delete-orphan",
        order_by="DefectStatusHistory.changed_at",
    )


class Manhole(Base):
    """
    Real MCGM manhole infrastructure/context data.

    Manholes are NOT defects and do NOT participate in Road Health scoring.
    They are associated with a road segment only for contextual display.
    """

    __tablename__ = "manholes"

    id = Column(Integer, primary_key=True, index=True)

    # MCGM source object_id.
    object_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    road_name = Column(String(255), nullable=True)
    ward = Column(String(50), nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    status = Column(String(100), nullable=True)
    condition = Column(String(100), nullable=True)

    survey_date = Column(DateTime, nullable=True)
    created_date = Column(DateTime, nullable=True)
    last_edited_date = Column(DateTime, nullable=True)

    remarks = Column(String(1000), nullable=True)
    road_norm = Column(String(255), nullable=True)

    # Optional association to an imported MCGM road segment.
    # Context only — NEVER used in Road Health scoring.
    road_segment_id = Column(
        Integer,
        ForeignKey("road_segments.id"),
        nullable=True,
        index=True,
    )

    road_segment = relationship(
        "RoadSegment",
        back_populates="manholes",
    )


class Encroachment(Base):
    """
    Real MCGM encroachment complaint/context data.

    Encroachments are NOT defects and do NOT participate in Road Health
    scoring. They are also NOT hawker detections.
    """

    __tablename__ = "encroachments"

    id = Column(Integer, primary_key=True, index=True)

    # MCGM/source complaint identifier where available.
    object_id = Column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )

    road_name = Column(String(255), nullable=True)
    ward = Column(String(50), nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    status = Column(String(100), nullable=True)
    complaint_type = Column(String(255), nullable=True)
    description = Column(String(2000), nullable=True)

    created_date = Column(DateTime, nullable=True)
    last_edited_date = Column(DateTime, nullable=True)

    # Optional association to an imported MCGM road segment.
    # Context only — NEVER used in Road Health scoring.
    road_segment_id = Column(
        Integer,
        ForeignKey("road_segments.id"),
        nullable=True,
        index=True,
    )

    road_segment = relationship(
        "RoadSegment",
        back_populates="encroachments",
    )


class DefectStatusHistory(Base):
    __tablename__ = "defect_status_history"

    id = Column(Integer, primary_key=True, index=True)

    defect_id = Column(
        Integer,
        ForeignKey("defects.id"),
        nullable=False,
        index=True,
    )

    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    changed_by = Column(String, nullable=True)

    changed_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    note = Column(String, nullable=True)

    defect = relationship(
        "Defect",
        back_populates="status_history",
    )


class Officer(Base):
    """
    Municipal officer identity.
    """

    __tablename__ = "officers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)

    password_hash = Column(String, nullable=False)

    department = Column(String, nullable=True)

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )


class Citizen(Base):
    """
    Citizen identity.
    """

    __tablename__ = "citizens"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)

    password_hash = Column(String, nullable=False)

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    defects = relationship(
        "Defect",
        back_populates="citizen",
    )