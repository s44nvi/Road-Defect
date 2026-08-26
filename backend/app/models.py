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

    # Human-friendly label for this segment, e.g.
    # "Western Express Highway - Segment 1". Nullable so existing rows and
    # third-party importers are unaffected; the API falls back to deriving it
    # from road_name + segment_id when it is not set.
    segment_label = Column(String(255), nullable=True)

    # Provenance of `geometry` -- 'dev_approximate_v1' for the bundled
    # development corridors, 'osm_overpass' for real imported OSM ways. Kept on
    # the row so approximate geometry can never be mistaken for surveyed data.
    # See road_health/data/README.md.
    geometry_source = Column(String(100), nullable=True)

    defects = relationship("Defect", back_populates="road_segment")


class Defect(Base):
    __tablename__ = "defects"

    id = Column(Integer, primary_key=True, index=True)
    defect_type = Column(String, nullable=False)
    defect_status = Column(String, nullable=False, default="reported")
    defect_severity = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Marks rows created by backend/scripts/seed_road_health_dev_data.py so
    # development/test data stays distinguishable from real citizen reports.
    # Real reports created through POST /reports are always False.
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
