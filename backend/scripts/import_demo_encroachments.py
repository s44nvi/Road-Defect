from __future__ import annotations

import math
import sys

import pandas as pd
from sqlalchemy.orm import Session

sys.path.insert(0, "backend")

from app.database import SessionLocal
from app.models import Encroachment, RoadSegment


CSV_PATH = "/Users/akshaykumar/Downloads/demo_encroachments.csv"


def point_to_segment_distance_m(
    lat,
    lon,
    lat1,
    lon1,
    lat2,
    lon2,
):
    """Approximate point-to-line-segment distance in metres."""
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

    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    t = (
        (px - ax) * dx + (py - ay) * dy
    ) / (dx * dx + dy * dy)

    t = max(0.0, min(1.0, t))

    closest_x = ax + t * dx
    closest_y = ay + t * dy

    return math.hypot(
        px - closest_x,
        py - closest_y,
    )


def geometry_parts(geometry):
    """Extract LineString/MultiLineString coordinate parts."""
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

    # LineString
    if (
        isinstance(coordinates, list)
        and coordinates
        and isinstance(coordinates[0], list)
        and len(coordinates[0]) >= 2
        and isinstance(coordinates[0][0], (int, float))
    ):
        return [coordinates]

    # MultiLineString
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
    """Find nearest distance from a point to stored road geometry."""
    parts = geometry_parts(geometry)

    if not parts:
        return float("inf")

    best = float("inf")

    for points in parts:
        if len(points) == 1:
            continue

        for a, b in zip(points, points[1:]):
            distance = point_to_segment_distance_m(
                lat,
                lon,
                a[1],
                a[0],
                b[1],
                b[0],
            )

            best = min(best, distance)

    return best


def clean_string(value):
    """Return None for missing CSV values."""
    if pd.isna(value):
        return None

    value = str(value).strip()

    return value if value else None


def main():
    df = pd.read_csv(CSV_PATH)

    print(f"CSV ENCROACHMENTS: {len(df)}")

    db: Session = SessionLocal()

    try:
        # Only the 10 real MCGM demo roads.
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

        print(
            f"MCGM ROAD SEGMENTS: {len(segments)}"
        )

        imported = 0
        updated = 0
        unmatched = 0

        for _, row in df.iterrows():
            object_id = str(row["object_id"])

            latitude = float(row["latitude"])
            longitude = float(row["longitude"])

            candidates = []

            for segment in segments:
                distance = nearest_distance_m(
                    latitude,
                    longitude,
                    segment.geometry,
                )

                candidates.append(
                    (distance, segment)
                )

            candidates.sort(
                key=lambda item: item[0]
            )

            best_distance, best_segment = candidates[0]

            if best_distance > 50:
                unmatched += 1
                road_segment_id = None
            else:
                road_segment_id = best_segment.id

            address = clean_string(
                row.get("address")
            )

            complaint_number = clean_string(
                row.get("complaint_number")
            )

            reference_number = clean_string(
                row.get("reference_number")
            )

            # Preserve the source complaint context without
            # inventing a complaint type or calling it a hawker.
            description_parts = []

            if address:
                description_parts.append(
                    f"Address: {address}"
                )

            if complaint_number:
                description_parts.append(
                    f"Complaint: {complaint_number}"
                )

            if reference_number:
                description_parts.append(
                    f"Reference: {reference_number}"
                )

            notice_number = clean_string(
                row.get("notice_number")
            )

            if notice_number:
                description_parts.append(
                    f"Notice: {notice_number}"
                )

            sac_number = clean_string(
                row.get("sac_number")
            )

            if sac_number:
                description_parts.append(
                    f"SAC: {sac_number}"
                )

            description = (
                " | ".join(description_parts)
                if description_parts
                else None
            )

            values = {
                "object_id": object_id,
                "road_name": (
                    best_segment.road_name
                    if road_segment_id is not None
                    else None
                ),
                "ward": clean_string(
                    row.get("ward_guess")
                ),
                "latitude": latitude,
                "longitude": longitude,
                "status": clean_string(
                    row.get("status")
                ),
                # Source does not provide a structured
                # complaint_type. Do not invent one.
                "complaint_type": None,
                "description": description,
                "created_date": None,
                "last_edited_date": None,
                "road_segment_id": road_segment_id,
            }

            existing = (
                db.query(Encroachment)
                .filter(
                    Encroachment.object_id
                    == object_id
                )
                .first()
            )

            if existing:
                for key, value in values.items():
                    setattr(
                        existing,
                        key,
                        value,
                    )

                updated += 1
            else:
                db.add(
                    Encroachment(**values)
                )

                imported += 1

        db.commit()

        total = (
            db.query(Encroachment).count()
        )

        associated = (
            db.query(Encroachment)
            .filter(
                Encroachment.road_segment_id.isnot(None)
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
        print("ENCROACHMENTS BY MCGM ROAD:")

        for segment in sorted(
            segments,
            key=lambda s: s.segment_id,
        ):
            count = (
                db.query(Encroachment)
                .filter(
                    Encroachment.road_segment_id
                    == segment.id
                )
                .count()
            )

            print(
                f"{segment.segment_id} | "
                f"{segment.road_name} | "
                f"encroachments={count}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()