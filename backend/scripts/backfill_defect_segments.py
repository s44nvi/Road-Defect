"""
backfill_defect_segments.py
===========================
Assigns existing defects to their canonical road segment.

    python -m backend.scripts.backfill_defect_segments --dry-run
    python -m backend.scripts.backfill_defect_segments
    python -m backend.scripts.backfill_defect_segments --reassign-all

Mapping logic (identical to the one `POST /reports` uses, so a backfilled
defect and a freshly reported one at the same coordinates always land on the
same segment):

  1. Measure the perpendicular distance from the defect to every segment's
     polyline, clamped to the polyline's ends.
  2. Nearest segment wins; ties break on ascending `segment_id`.
  3. If the nearest segment is farther than `MAX_SNAP_DISTANCE_KM` (150 m by
     default), the defect is LEFT UNASSIGNED rather than forced onto a road it
     is not on.

The script writes exactly one column -- `defects.road_segment_id`. It never
inserts, deletes, or duplicates a defect, and never touches any other field.
By default it only fills in defects that are currently unassigned; pass
`--reassign-all` after importing new geometry to re-snap everything.
"""

from __future__ import annotations

import argparse

from backend.app.database import SessionLocal
from backend.app.models import Defect
from backend.app.road_health.assignment import find_nearest_segment
from backend.app.road_health.config import MAX_SNAP_DISTANCE_KM
from backend.app.road_health.service import segment_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing anything.",
    )
    parser.add_argument(
        "--reassign-all",
        action="store_true",
        help="Re-snap every defect, not just the unassigned ones.",
    )
    parser.add_argument(
        "--max-distance-km",
        type=float,
        default=MAX_SNAP_DISTANCE_KM,
        help=f"Snapping tolerance in km (default {MAX_SNAP_DISTANCE_KM}).",
    )
    args = parser.parse_args()

    db = SessionLocal()

    try:
        segments = segment_candidates(db)

        if not segments:
            raise SystemExit(
                "No road segments found. Run "
                "`python -m backend.scripts.seed_road_health_dev_data` or "
                "`python -m backend.scripts.import_osm_segments` first."
            )

        query = db.query(Defect).order_by(Defect.id)

        if not args.reassign_all:
            query = query.filter(Defect.road_segment_id.is_(None))

        defects = query.all()

        changed = 0
        unassigned = 0

        for defect in defects:
            result = find_nearest_segment(
                defect.latitude,
                defect.longitude,
                segments,
                max_distance_km=args.max_distance_km,
            )

            if result.segment_pk is None:
                unassigned += 1
                print(
                    f"defect {defect.id}: no segment within "
                    f"{args.max_distance_km} km -> left unassigned"
                )
                continue

            if defect.road_segment_id != result.segment_pk:
                print(
                    f"defect {defect.id}: -> {result.segment_id} "
                    f"({result.distance_km:.4f} km away)"
                )
                defect.road_segment_id = result.segment_pk
                changed += 1

        if args.dry_run:
            db.rollback()
            print(f"\nDRY RUN -- nothing written. Would change {changed} defect(s).")
        else:
            db.commit()
            print(f"\nUpdated {changed} defect(s).")

        print(f"Examined {len(defects)} defect(s); {unassigned} left unassigned.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
