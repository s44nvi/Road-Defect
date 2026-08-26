from __future__ import annotations

import math
import sys

import pandas as pd
from sqlalchemy.orm import Session

sys.path.insert(0, "backend")

from app.database import SessionLocal
from app.models import Manhole, RoadSegment


CSV_PATH = "/Users/akshaykumar/Downloads/demo_manholes.csv"


def distance_m(lat1, lon1, lat2, lon2):
    """
    Approximate point-to-point distance in metres using an
    equirectangular projection.
    """
    r = 6371000.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    dlat = lat2_rad - lat1_rad
    dlon = math.radians(lon2 - lon1)

    x = dlon * math.cos((lat1_rad + lat2_rad) / 2)
    y = dlat

    return r * math.sqrt(x * x + y * y)


def point_to_segment_distance_m(
    lat,
    lon,
    lat1,
    lon1,
    lat2,
    lon2,
):
    """
    Approximate distance from a point to a line segment in metres.

    This is important because measuring only against geometry vertices
    can incorrectly classify points near the middle of a road segment
    as being more than 50m away.
    """
    r = 6371000.0

    lat_ref = math.radians((lat1 + lat2 + lat) / 3.0)

    def project(lat_value, lon_value):
        x = (
            math.radians(lon_value)
            * r
            * math.cos(lat_ref)
        )
        y = math.radians(lat_value) * r
        return x, y

    px, py = project(lat, lon)
    ax, ay = project(lat1, lon1)
    bx, by = project(lat2, lon2)

    dx = bx - ax
    dy = by - ay

    # Degenerate segment: both endpoints are the same.
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    # Projection parameter onto the segment.
    t = (
        (px - ax) * dx + (py - ay) * dy
    ) / (dx * dx + dy * dy)

    # Clamp projection to the actual segment.
    t = max(0.0, min(1.0, t))

    closest_x = ax + t * dx
    closest_y = ay + t * dy

    return math.hypot(
        px - closest_x,
        py - closest_y,
    )


def geometry_parts(geometry):
    """
    Extract LineString/MultiLineString parts.

    Returns:
        [
            [[lon, lat], [lon, lat], ...],
            ...
        ]
    """
    if not geometry:
        return []

    if isinstance(geometry, dict):
        coordinates = geometry.get(
            "coordinates",
            geometry,
        )
    else:
        coordinates = geometry

    if not coordinates:
        return []

    # LineString:
    # [[lon, lat], [lon, lat], ...]
    if (
        isinstance(coordinates, list)
        and coordinates
        and isinstance(coordinates[0], list)
        and len(coordinates[0]) >= 2
        and isinstance(coordinates[0][0], (int, float))
    ):
        return [coordinates]

    # MultiLineString:
    # [
    #   [[lon, lat], ...],
    #   [[lon, lat], ...]
    # ]
    parts = []

    for part in coordinates:
        if not isinstance(part, list):
            continue

        points = []

        for point in part:
            if (
                isinstance(point, list)
                and len(point) >= 2
                and isinstance(point[0], (int, float))
                and isinstance(point[1], (int, float))
            ):
                points.append(point)

        if points:
            parts.append(points)

    return parts


def nearest_distance_m(lat, lon, geometry):
    """
    Find the true nearest distance from the manhole point to the
    stored road geometry.

    Handles both LineString and MultiLineString geometries.
    """
    parts = geometry_parts(geometry)

    if not parts:
        return float("inf")

    best = float("inf")

    for points in parts:
        if len(points) == 1:
            d = distance_m(
                lat,
                lon,
                points[0][1],
                points[0][0],
            )

            best = min(best, d)
            continue

        for a, b in zip(points, points[1:]):
            d = point_to_segment_distance_m(
                lat,
                lon,
                a[1],
                a[0],
                b[1],
                b[0],
            )

            best = min(best, d)

    return best


def parse_date(value):
    """
    Convert an MCGM CSV date into a timezone-naive datetime suitable
    for the existing SQLAlchemy DateTime columns.
    """
    if pd.isna(value) or not value:
        return None

    try:
        return (
            pd.to_datetime(value, utc=True)
            .to_pydatetime()
            .replace(tzinfo=None)
        )
    except Exception:
        return None


def main():
    df = pd.read_csv(CSV_PATH)

    print(f"CSV MANHOLES: {len(df)}")

    db: Session = SessionLocal()

    try:
        # IMPORTANT:
        # Only use the 10 real MCGM demo road segments.
        # Do not associate manholes with the older development/OSM roads.
        segments = (
            db.query(RoadSegment)
            .filter(
                RoadSegment.geometry_source
                == "mcgm_demo_csv_v1"
            )
            .all()
        )

        if len(segments) != 10:
            raise RuntimeError(
                "Expected 10 MCGM demo road segments, "
                f"found {len(segments)}"
            )

        print(f"MCGM ROAD SEGMENTS: {len(segments)}")

        imported = 0
        updated = 0
        unmatched = 0

        for _, row in df.iterrows():
            object_id = str(row["object_id"])

            existing = (
                db.query(Manhole)
                .filter(
                    Manhole.object_id == object_id
                )
                .first()
            )

            candidates = []

            for segment in segments:
                d = nearest_distance_m(
                    float(row["latitude"]),
                    float(row["longitude"]),
                    segment.geometry,
                )

                candidates.append(
                    (d, segment)
                )

            candidates.sort(
                key=lambda item: item[0]
            )

            best_distance, best_segment = candidates[0]

            # 50m is only an association threshold.
            # Manholes themselves remain contextual data and do not
            # participate in Road Health scoring.
            if best_distance > 50:
                unmatched += 1
                segment_id = None
            else:
                segment_id = best_segment.id

            values = {
                "object_id": object_id,
                "road_name": (
                    None
                    if pd.isna(row.get("road_name"))
                    else str(row["road_name"])
                ),
                "ward": (
                    None
                    if pd.isna(row.get("ward"))
                    else str(row["ward"])
                ),
                "latitude": float(
                    row["latitude"]
                ),
                "longitude": float(
                    row["longitude"]
                ),
                "status": (
                    None
                    if pd.isna(row.get("status"))
                    else str(row["status"])
                ),
                "condition": (
                    None
                    if pd.isna(row.get("condition"))
                    else str(row["condition"])
                ),
                "survey_date": parse_date(
                    row.get("survey_date")
                ),
                "created_date": parse_date(
                    row.get("created_date")
                ),
                "last_edited_date": parse_date(
                    row.get("last_edited_date")
                ),
                "remarks": (
                    None
                    if pd.isna(row.get("remarks"))
                    else str(row["remarks"])
                ),
                "road_norm": (
                    None
                    if pd.isna(row.get("road_norm"))
                    else str(row["road_norm"])
                ),
                "road_segment_id": segment_id,
            }

            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)

                updated += 1

            else:
                db.add(
                    Manhole(**values)
                )

                imported += 1

        db.commit()

        total = (
            db.query(Manhole).count()
        )

        associated = (
            db.query(Manhole)
            .filter(
                Manhole.road_segment_id.isnot(None)
            )
            .count()
        )

        print()
        print("IMPORT COMPLETE")
        print(f"NEW: {imported}")
        print(f"UPDATED: {updated}")
        print(f"TOTAL IN DB: {total}")
        print(
            f"ASSOCIATED TO ROAD: {associated}"
        )
        print(
            f"UNMATCHED (>50m): {unmatched}"
        )

        print()
        print("MANHOLES BY MCGM ROAD:")

        for segment in sorted(
            segments,
            key=lambda s: s.segment_id,
        ):
            count = (
                db.query(Manhole)
                .filter(
                    Manhole.road_segment_id
                    == segment.id
                )
                .count()
            )

            print(
                f"{segment.segment_id} | "
                f"{segment.road_name} | "
                f"manholes={count}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()