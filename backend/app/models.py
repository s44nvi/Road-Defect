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
    # development corridors, 'osm_overpass' for real imported OSM ways,
    # 'mcgm_demo_csv_v1' for the real MCGM demo road CSV. Kept on the row so
    # approximate geometry can never be mistaken for surveyed/municipal data.
    # See road_health/data/README.md.
    geometry_source = Column(String(100), nullable=True)

    # --- MCGM source metadata (nullable: only populated for segments
    # imported from the MCGM demo CSV by
    # backend/scripts/import_demo_roads.py; dev/OSM segments leave these
    # NULL) ------------------------------------------------------------
    # The MCGM record's own `id` column -- the stable external key the
    # importer upserts on, distinct from our own `segment_id` naming scheme.
    mcgm_id = Column(String(50), nullable=True, index=True)
    ward = Column(String(50), nullable=True)
    # MCGM's own road-work status string (e.g. "Work In Progress"). This is
    # municipal work-order status, NOT `Defect.defect_status` -- it never
    # feeds Road Health scoring (see road_health/config.py).
    work_status = Column(String(100), nullable=True)
    # The CSV's own `length_of_road_m`, preserved as source metadata. Kept
    # separate from `length_km` (which Road Health scoring uses, and which
    # is always derived from the actual geometry -- see
    # backend/scripts/import_demo_roads.py for why the two numbers can
    # legitimately disagree for this dataset).
    source_length_m = Column(Float, nullable=True)

    defects = relationship("Defect", back_populates="road_segment")


class Defect(Base):
    __tablename__ = "defects"

    id = Column(Integer, primary_key=True, index=True)
    defect_type = Column(String, nullable=False)
    defect_status = Column(String, nullable=False, default="reported")
    defect_severity = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Priority score (0-100) from the existing Road Intelligence/AHP service.
    # Nullable: only populated for defects created through the image pipeline
    # (`POST /reports/image`), which is the only path that runs AHP scoring.
    # Reports created through the pre-existing JSON `POST /reports` have no
    # detection to score and leave this NULL.
    defect_priority = Column(Float, nullable=True)

    # Path to the uploaded source image used for inference, if any. Nullable
    # for the same reason as defect_priority -- only the image pipeline sets it.
    image_path = Column(String, nullable=True)

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

    # Citizen who submitted this report.
    #
    # Nullable because existing defects and development/seed defects may not
    # belong to a citizen. New authenticated citizen reports will populate it.
    citizen_id = Column(
        Integer,
        ForeignKey("citizens.id"),
        nullable=True,
        index=True,
    )

    citizen = relationship("Citizen", back_populates="defects")

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


class Officer(Base):
    """
    A municipal officer identity, distinct from and never interchangeable
    with a Citizen row. See `app/auth/` -- officer login verifies
    `password_hash` and issues a JWT whose `principal_type` claim is
    "officer", which is what `get_current_officer` checks. There is no path
    by which a Citizen row can satisfy officer authentication.
    """

    __tablename__ = "officers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)

    # Never store or return the plaintext password -- only its bcrypt hash.
    # See app/auth/security.py. Never exposed through an API response schema.
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
    A citizen identity, distinct from and never interchangeable with an
    Officer row.

    Citizen report submission can now be associated with the authenticated
    citizen through Defect.citizen_id. This relationship is what allows the
    backend to provide a proper user-scoped "My Reports" endpoint instead of
    making the frontend fetch all defects and filter them.
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

    defects = relationship("Defect", back_populates="citizen")