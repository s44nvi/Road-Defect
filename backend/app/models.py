from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
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

    defects = relationship("Defect", back_populates="road_segment")


class Defect(Base):
    __tablename__ = "defects"

    id = Column(Integer, primary_key=True, index=True)
    defect_type = Column(String, nullable=False)
    defect_status = Column(String, nullable=False, default="reported")
    defect_severity = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    road_segment_id = Column(
        Integer,
        ForeignKey("road_segments.id"),
        nullable=True,
        index=True,
    )

    road_segment = relationship("RoadSegment", back_populates="defects")

    status_history = relationship(
        "DefectStatusHistory",
        back_populates="defect",
        cascade="all, delete-orphan",
        order_by="DefectStatusHistory.changed_at",
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

    defect = relationship("Defect", back_populates="status_history")
