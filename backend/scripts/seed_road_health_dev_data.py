"""
seed_road_health_dev_data.py
============================
Seeds DEVELOPMENT/TEST road-health data: Mumbai road segments plus defects
placed on them, spanning all three health bands (green / orange / red).

    python -m backend.scripts.seed_road_health_dev_data
    python -m backend.scripts.seed_road_health_dev_data --reset
    python -m backend.scripts.seed_road_health_dev_data --assign-existing

Safety guarantees -- this script is designed to be safe to run against a
database that holds real citizen reports:

  * It NEVER deletes, updates, or duplicates a defect it did not create.
    Every row it inserts is stamped `defects.is_test_data = True`, and
    `--reset` deletes only rows carrying that flag.
  * Segments are upserted by `segment_id`, so re-running it does not create
    duplicates.
  * `--assign-existing` only fills in `road_segment_id` on real defects (it
    touches no other column), and only where a segment is within the snapping
    tolerance.

Geometry provenance: the segments come from
`backend/app/road_health/data/mumbai_corridors.geojson`, which is APPROXIMATE
HAND-AUTHORED DEVELOPMENT GEOMETRY -- not surveyed and not OpenStreetMap data.
See `backend/app/road_health/data/README.md`, and use
`backend/scripts/import_osm_segments.py` to replace it with real OSM roads.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.defect_workflow import record_status_history
from backend.app.models import Defect, RoadSegment
from backend.app.road_health import service as road_health_service
from backend.app.road_health.config import (
    GEOMETRY_SOURCE_DEV,
    STATUS_ASSIGNED,
    STATUS_CONFIRMED,
    STATUS_REJECTED,
    STATUS_REPAIR_IN_PROGRESS,
    STATUS_REPORTED,
    STATUS_RESOLVED,
    STATUS_UNDER_REVIEW,
    TARGET_SEGMENT_LENGTH_KM,
)
from backend.app.road_health.geo import (
    linestring,
    linestring_length_km,
    point_at_chainage,
    split_into_segments,
)

CORRIDOR_FILE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "road_health"
    / "data"
    / "mumbai_corridors.geojson"
)

# Defect mix per health band, as (severity, status) pairs. Only ACTIVE statuses
# contribute to the health penalty, so the resolved/rejected entries exist
# precisely to prove they do not drag a score down.
#
# With score = 10 / (1 + active_load / length_km):
#   green  -> a handful of low-severity actives on a ~10 km segment
#   orange -> a mixed load around 1.0 weighted units per km
#   red    -> a heavy critical load, well past 1.5 units per km
DEFECT_PLANS: dict[str, list[tuple[str, str]]] = {
    "green": [
        ("low", STATUS_REPORTED),
        ("low", STATUS_UNDER_REVIEW),
        ("low", STATUS_CONFIRMED),
        ("critical", STATUS_RESOLVED),
        ("critical", STATUS_RESOLVED),
        ("medium", STATUS_RESOLVED),
        ("medium", STATUS_REJECTED),
    ],
    "orange": [
        ("critical", STATUS_REPORTED),
        ("critical", STATUS_ASSIGNED),
        ("medium", STATUS_UNDER_REVIEW),
        ("medium", STATUS_REPAIR_IN_PROGRESS),
        ("low", STATUS_REPORTED),
        ("medium", STATUS_RESOLVED),
        ("low", STATUS_RESOLVED),
        ("low", STATUS_REJECTED),
    ],
    "red": [
        ("critical", STATUS_REPORTED),
        ("critical", STATUS_REPORTED),
        ("critical", STATUS_REPORTED),
        ("critical", STATUS_UNDER_REVIEW),
        ("critical", STATUS_UNDER_REVIEW),
        ("critical", STATUS_CONFIRMED),
        ("critical", STATUS_CONFIRMED),
        ("critical", STATUS_REPAIR_IN_PROGRESS),
        ("medium", STATUS_REPORTED),
        ("medium", STATUS_CONFIRMED),
        ("medium", STATUS_REPAIR_IN_PROGRESS),
        ("low", STATUS_REPORTED),
        ("critical", STATUS_RESOLVED),
        ("medium", STATUS_RESOLVED),
    ],
}

# Which band each seeded segment should land in, cycled over the segments
# produced from the corridor file so the officer map shows all three colours.
BAND_ROTATION: list[str] = ["orange", "green", "red", "orange", "green", "red"]

DEFECT_TYPES: list[str] = [
    "pothole",
    "alligator_crack",
    "rutting",
    "longitudinal_crack",
    "surface_damage",
]

# Deterministic lateral offsets (degrees, ~5-30 m) applied when placing seeded
# defects, so they sit beside the centreline like real GPS reports rather than
# exactly on it. Fixed values, not random, so seeding is reproducible.
LATERAL_OFFSETS: list[float] = [0.00005, -0.00012, 0.00020, -0.00007, 0.00028, -0.00019]


def load_corridors() -> list[dict]:
    """Read the corridor FeatureCollection from disk."""
    with CORRIDOR_FILE.open() as handle:
        collection = json.load(handle)

    return collection["features"]


def upsert_segments(db: Session) -> list[RoadSegment]:
    """
    Create (or refresh) the road segments derived from the corridor file.

    Segmentation follows each corridor's own geometry via cumulative chainage
    -- no circles, no synthetic shapes.
    """
    segments: list[RoadSegment] = []
    counter = 0

    for feature in load_corridors():
        road_name = feature["properties"]["road_name"]
        coordinates = feature["geometry"]["coordinates"]

        pieces = split_into_segments(coordinates, TARGET_SEGMENT_LENGTH_KM)

        for index, piece in enumerate(pieces, start=1):
            counter += 1

            segment_id = f"SEG-{counter:03d}"
            label = f"{road_name} - Segment {index}"

            segment = (
                db.query(RoadSegment)
                .filter(RoadSegment.segment_id == segment_id)
                .first()
            )

            if segment is None:
                segment = RoadSegment(segment_id=segment_id)
                db.add(segment)

            segment.road_name = road_name
            segment.segment_label = label
            segment.geometry = linestring(piece)
            segment.length_km = round(linestring_length_km(piece), 3)
            segment.geometry_source = GEOMETRY_SOURCE_DEV

            segments.append(segment)

    db.flush()

    return segments


def seed_defects(db: Session, segments: list[RoadSegment]) -> int:
    """Place development defects along each segment. Returns rows created."""
    created = 0

    for position, segment in enumerate(segments):
        band = BAND_ROTATION[position % len(BAND_ROTATION)]
        plan = DEFECT_PLANS[band]

        coordinates = segment.geometry["coordinates"]
        length_km = linestring_length_km(coordinates)

        for index, (severity, status) in enumerate(plan):
            # Spread defects evenly between 10% and 90% of the segment so none
            # lands exactly on a boundary shared with the neighbouring segment.
            fraction = 0.1 + 0.8 * (index / max(1, len(plan) - 1))
            lon, lat = point_at_chainage(coordinates, length_km * fraction)

            offset = LATERAL_OFFSETS[index % len(LATERAL_OFFSETS)]

            defect = Defect(
                defect_type=DEFECT_TYPES[index % len(DEFECT_TYPES)],
                defect_status=status,
                defect_severity=severity,
                latitude=round(lat + offset, 7),
                longitude=round(lon + offset, 7),
                road_segment_id=segment.id,
                is_test_data=True,
            )

            db.add(defect)
            db.flush()

            record_status_history(
                db,
                defect,
                old_status=None,
                new_status=STATUS_REPORTED,
                changed_by="seed_script",
                note="Seeded development defect",
            )

            if status != STATUS_REPORTED:
                record_status_history(
                    db,
                    defect,
                    old_status=STATUS_REPORTED,
                    new_status=status,
                    changed_by="seed_script",
                    note=f"Seeded development defect in '{status}' state",
                )

            created += 1

    return created


def delete_test_defects(db: Session) -> int:
    """
    Delete ONLY seeded defects (`is_test_data = True`) and their history.

    Real citizen reports are never touched.
    """
    test_defects = db.query(Defect).filter(Defect.is_test_data.is_(True)).all()

    for defect in test_defects:
        # Status history rows go with the defect via the cascade on the
        # relationship, so the timeline never outlives its defect.
        db.delete(defect)

    return len(test_defects)


def assign_existing_defects(db: Session) -> tuple[int, int]:
    """
    Snap real (non-seeded) defects onto segments.

    Only `road_segment_id` is written. Returns (assigned, unassigned).
    """
    defects = (
        db.query(Defect)
        .filter(Defect.is_test_data.is_(False))
        .order_by(Defect.id)
        .all()
    )

    assigned = 0

    for defect in defects:
        if road_health_service.assign_defect_to_segment(db, defect) is not None:
            assigned += 1

    return assigned, len(defects) - assigned


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete previously seeded test defects (is_test_data=True) first. "
             "Real citizen reports are never deleted.",
    )
    parser.add_argument(
        "--assign-existing",
        action="store_true",
        help="Also snap existing real defects onto segments (fills "
             "road_segment_id only).",
    )
    args = parser.parse_args()

    db = SessionLocal()

    try:
        real_defects_before = (
            db.query(Defect).filter(Defect.is_test_data.is_(False)).count()
        )

        removed = delete_test_defects(db) if args.reset else 0

        segments = upsert_segments(db)
        created = seed_defects(db, segments)

        assigned = unassigned = 0

        if args.assign_existing:
            assigned, unassigned = assign_existing_defects(db)

        real_defects_after = (
            db.query(Defect).filter(Defect.is_test_data.is_(False)).count()
        )

        if real_defects_after != real_defects_before:
            db.rollback()
            raise SystemExit(
                "ABORTED: real defect count changed "
                f"({real_defects_before} -> {real_defects_after}). Rolled back."
            )

        db.commit()

        print(f"Segments upserted        : {len(segments)}")
        print(f"Test defects removed     : {removed}")
        print(f"Test defects created     : {created}")
        print(f"Real defects (untouched) : {real_defects_after}")

        if args.assign_existing:
            print(f"Real defects assigned    : {assigned}")
            print(f"Real defects unassigned  : {unassigned} (no segment within tolerance)")

        print()
        print("Geometry source: dev_approximate_v1 (approximate hand-authored")
        print("development geometry -- NOT surveyed or OpenStreetMap data).")

    finally:
        db.close()


if __name__ == "__main__":
    main()
