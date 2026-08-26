"""
import_demo_roads.py
=====================
Imports the curated MCGM demo road CSV (demo_roads.csv) as canonical
`RoadSegment` rows, using the existing Road Health architecture --
no second/parallel geometry system.

    python -m backend.scripts.import_demo_roads
    python -m backend.scripts.import_demo_roads --csv /path/to/demo_roads.csv
    python -m backend.scripts.import_demo_roads --dry-run

Each CSV row becomes ONE `RoadSegment`, upserted by `segment_id =
f"MCGM-{row['id']}"` (the MCGM record's own `id`, the stable external key)
-- so running this script twice never creates duplicate rows; it just
updates the same 10 segments in place. This is the same
query-then-create-or-update pattern `import_osm_segments.py` uses.

GEOMETRY -- WHY LineString AND MultiLineString ARE BOTH KEPT AS-IS
--------------------------------------------------------------------
7 of the 10 roads are plain WKT LINESTRINGs. 3 are MULTILINESTRING:

    18th Road           2 parts, endpoints ~5.7 m apart
    15thRoad            2 parts, endpoints ~5.1 m apart
    13th Road,Khar(W)   2 parts, endpoints ~773.6 m apart

13th Road's two parts are genuinely disconnected -- not a digitization
artifact, an actual gap of most of the road's length. Joining them with a
synthetic connecting line would fabricate geometry MCGM never supplied.

18th Road and 15thRoad *could* plausibly be treated as one line with a tiny
digitization gap. This importer does NOT do that either: it stores every
MULTILINESTRING road's parts exactly as supplied, uniformly, with no
distance-threshold judgment call about which gaps are "close enough" to
bridge. `road_health.geo.parse_geometry_parts` /
`road_health.service._geometry_payload` already support this uniformly --
a segment with one part round-trips as GeoJSON LineString, a segment with
several parts round-trips as GeoJSON MultiLineString, and nothing in
Road Health scoring/assignment special-cases either shape.

LENGTH -- WHY length_km AND source_length_m CAN LEGITIMATELY DIFFER
----------------------------------------------------------------------
`length_km` (used by Road Health scoring) is always computed from the
ACTUAL supplied geometry (`geo.total_length_km`, which sums each part's own
haversine length -- never a distance across a genuine gap). The CSV's own
`length_of_road_m` is preserved separately as `source_length_m`; the two
numbers disagree for several of these roads (e.g. 15thRoad: geometry
~0.60 km vs CSV 0.70 km) and neither value is silently discarded or forced
to match the other.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from backend.app.database import SessionLocal
from backend.app.models import RoadSegment
from backend.app.road_health import geo
from backend.app.road_health.config import GEOMETRY_SOURCE_MCGM_DEMO

DEFAULT_CSV = Path.home() / "Downloads" / "demo_roads.csv"


def parse_wkt(wkt: str) -> list[geo.Coordinates]:
    """
    Parse a WKT LINESTRING or MULTILINESTRING into a list of parts.

    Returns one part for LINESTRING, two-or-more for MULTILINESTRING.
    Parts are returned in their original WKT order, untouched -- this
    function never merges/reorders/bridges parts (see module docstring).
    """
    wkt = str(wkt).strip()

    if wkt.startswith("LINESTRING"):
        body = wkt[wkt.index("(") + 1 : wkt.rindex(")")]
        raw_parts = [body]
    elif wkt.startswith("MULTILINESTRING"):
        body = wkt[wkt.index("(") + 1 : wkt.rindex(")")]
        raw_parts = re.split(r"\)\s*,\s*\(", body)
    else:
        raise ValueError(f"Unsupported geometry: {wkt[:50]}")

    parts: list[geo.Coordinates] = []

    for raw_part in raw_parts:
        raw_part = raw_part.strip("() ")
        coordinates: geo.Coordinates = []

        for pair in raw_part.split(","):
            lon, lat = map(float, pair.strip().split())
            coordinates.append([lon, lat])

        if len(coordinates) < 2:
            raise ValueError(f"Part has fewer than 2 points: {raw_part!r}")

        parts.append(coordinates)

    return parts


def _clean_str(value: object) -> str | None:
    """CSV blanks/NaN -> None; everything else -> stripped string."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def import_row(db, row: pd.Series) -> RoadSegment:
    """Upsert one CSV row as a RoadSegment. Does not commit."""
    mcgm_id = str(row["id"]).strip()
    segment_id = f"MCGM-{mcgm_id}"

    parts = parse_wkt(row["geometry_wkt"])
    geometry = geo.linestring(parts[0]) if len(parts) == 1 else geo.multi_linestring(parts)
    length_km = round(geo.total_length_km(parts), 3)

    road_name = str(row["road_name"]).strip()
    ward = _clean_str(row.get("ward"))
    work_status = _clean_str(row.get("status"))
    source_length_m = float(row["length_of_road_m"]) if pd.notna(row.get("length_of_road_m")) else None

    segment = db.query(RoadSegment).filter(RoadSegment.segment_id == segment_id).first()

    if segment is None:
        segment = RoadSegment(segment_id=segment_id)
        db.add(segment)

    segment.road_name = road_name
    segment.segment_label = f"{road_name} ({ward})" if ward else road_name
    segment.geometry = geometry
    segment.length_km = length_km
    segment.geometry_source = GEOMETRY_SOURCE_MCGM_DEMO
    segment.mcgm_id = mcgm_id
    segment.ward = ward
    segment.work_status = work_status
    segment.source_length_m = source_length_m

    return segment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print what would be imported; write nothing.",
    )

    args = parser.parse_args()

    print(f"CSV: {args.csv}")

    df = pd.read_csv(args.csv)

    print(f"Loaded {len(df)} road(s).")
    print()

    db = SessionLocal()

    try:
        for _, row in df.iterrows():
            parts = parse_wkt(row["geometry_wkt"])
            shape = "LineString" if len(parts) == 1 else f"MultiLineString({len(parts)} parts)"
            length_km = round(geo.total_length_km(parts), 3)

            segment = import_row(db, row)

            print(
                f"{segment.segment_id:10} {row['road_name']!r:25} "
                f"{shape:24} length={length_km:.3f} km "
                f"ward={segment.ward!r:6} status={segment.work_status!r}"
            )

        if args.dry_run:
            db.rollback()
            print("\nDRY RUN -- nothing written.")
        else:
            db.commit()
            print(f"\nImported/updated {len(df)} MCGM demo road segment(s).")

    finally:
        db.close()


if __name__ == "__main__":
    main()
