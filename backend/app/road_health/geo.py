"""
geo.py
======
Pure-Python geometry helpers for road segments. No PostGIS, no shapely, no
SQLAlchemy, no FastAPI -- just the maths needed to:

  * measure a GeoJSON LineString in kilometres (haversine chainage),
  * cut a corridor polyline into segments ALONG ITS OWN GEOMETRY,
  * measure how far a defect (lat/lon point) is from a road polyline.

PostGIS is deliberately not required: the deployment target runs PostgreSQL
without the extension, and everything Road Health needs is cheap to compute
in Python over the JSON geometry already stored on `road_segments`.

Coordinate convention: GeoJSON order, `[longitude, latitude]`, degrees,
WGS84. Functions taking a bare point take `(lat, lon)` and say so.
"""

from __future__ import annotations

import math

from .config import EARTH_RADIUS_KM

# A GeoJSON LineString coordinate list: [[lon, lat], [lon, lat], ...]
Coordinates = list[list[float]]


class InvalidGeometryError(ValueError):
    """Raised when a geometry is not a usable GeoJSON LineString."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def parse_linestring(geometry: object) -> Coordinates:
    """
    Validate a GeoJSON LineString mapping and return its coordinate list.

    Accepts the geometry object itself (``{"type": "LineString",
    "coordinates": [...]}``) -- the shape stored in `road_segments.geometry`.
    """
    if not isinstance(geometry, dict):
        raise InvalidGeometryError("geometry must be a GeoJSON object")

    if geometry.get("type") != "LineString":
        raise InvalidGeometryError(
            f"unsupported geometry type {geometry.get('type')!r}; expected LineString"
        )

    coordinates = geometry.get("coordinates")

    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise InvalidGeometryError("LineString needs at least 2 coordinate pairs")

    parsed: Coordinates = []

    for point in coordinates:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise InvalidGeometryError(f"invalid coordinate pair: {point!r}")

        try:
            lon, lat = float(point[0]), float(point[1])
        except (TypeError, ValueError) as exc:
            raise InvalidGeometryError(f"non-numeric coordinate: {point!r}") from exc

        if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
            raise InvalidGeometryError(f"coordinate out of range: {point!r}")

        parsed.append([lon, lat])

    return parsed


def linestring(coordinates: Coordinates) -> dict:
    """Wrap a coordinate list into a GeoJSON LineString geometry object."""
    return {"type": "LineString", "coordinates": [[c[0], c[1]] for c in coordinates]}


# ---------------------------------------------------------------------------
# MultiLineString support
# ---------------------------------------------------------------------------
# Real-world road source data (e.g. the MCGM demo CSV) sometimes supplies a
# road as a MultiLineString with genuinely disconnected parts (a road split
# by a junction, a gap in the survey, etc). The rest of this module works in
# terms of a plain list of `Coordinates` "parts" -- a LineString is just the
# one-part case -- so callers never have to special-case the two GeoJSON
# geometry types, and a disconnected part is never bridged with an invented
# straight line just to force it into a single LineString.
def parse_multilinestring(geometry: object) -> list[Coordinates]:
    """
    Validate a GeoJSON MultiLineString mapping and return its parts.

    Each part is validated exactly like `parse_linestring` validates a bare
    LineString's coordinates. Parts are returned in their original order and
    are NEVER merged/reordered/bridged here -- that would fabricate geometry
    that was not in the source.
    """
    if not isinstance(geometry, dict):
        raise InvalidGeometryError("geometry must be a GeoJSON object")

    if geometry.get("type") != "MultiLineString":
        raise InvalidGeometryError(
            f"unsupported geometry type {geometry.get('type')!r}; expected MultiLineString"
        )

    parts = geometry.get("coordinates")

    if not isinstance(parts, list) or len(parts) < 1:
        raise InvalidGeometryError("MultiLineString needs at least 1 part")

    return [
        parse_linestring({"type": "LineString", "coordinates": part})
        for part in parts
    ]


def multi_linestring(parts: list[Coordinates]) -> dict:
    """Wrap a list of coordinate lists into a GeoJSON MultiLineString geometry object."""
    return {
        "type": "MultiLineString",
        "coordinates": [[[c[0], c[1]] for c in part] for part in parts],
    }


def parse_geometry_parts(geometry: object) -> list[Coordinates]:
    """
    Validate ANY supported geometry (LineString or MultiLineString) and
    return it as a list of one or more parts.

    This is the single entry point the rest of Road Health (assignment,
    length, GeoJSON passthrough) should use instead of `parse_linestring`
    directly, so both geometry types are handled uniformly.
    """
    if not isinstance(geometry, dict):
        raise InvalidGeometryError("geometry must be a GeoJSON object")

    geometry_type = geometry.get("type")

    if geometry_type == "LineString":
        return [parse_linestring(geometry)]

    if geometry_type == "MultiLineString":
        return parse_multilinestring(geometry)

    raise InvalidGeometryError(
        f"unsupported geometry type {geometry_type!r}; expected LineString or MultiLineString"
    )


def total_length_km(parts: list[Coordinates]) -> float:
    """
    Sum of each part's own length.

    Deliberately NOT the length of a single polyline drawn through all
    parts -- for a genuinely disconnected MultiLineString (see
    `parse_multilinestring`) there is no real edge between the parts, so
    summing each part's independent length is the only measurement that
    does not fabricate a connecting distance.
    """
    return sum(linestring_length_km(part) for part in parts)


def point_to_geometry_distance_km(
    lat: float,
    lon: float,
    parts: list[Coordinates],
) -> float:
    """Shortest distance from a point to any part of a (possibly multi-part) geometry."""
    return min(point_to_linestring_distance_km(lat, lon, part) for part in parts)


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )

    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


def linestring_length_km(coordinates: Coordinates) -> float:
    """Total length of a polyline, summed haversine leg by leg."""
    total = 0.0

    for (lon1, lat1), (lon2, lat2) in zip(coordinates, coordinates[1:]):
        total += haversine_km(lat1, lon1, lat2, lon2)

    return total


def cumulative_chainage_km(coordinates: Coordinates) -> list[float]:
    """
    Distance from the start of the polyline to each vertex.

    ``result[0]`` is always 0.0 and ``result[-1]`` is the total length.
    """
    chainage = [0.0]

    for (lon1, lat1), (lon2, lat2) in zip(coordinates, coordinates[1:]):
        chainage.append(chainage[-1] + haversine_km(lat1, lon1, lat2, lon2))

    return chainage


# ---------------------------------------------------------------------------
# Point-to-polyline distance
# ---------------------------------------------------------------------------
def _local_xy(lat: float, lon: float, lat_origin: float) -> tuple[float, float]:
    """
    Project degrees to a local flat (x, y) frame in kilometres.

    Equirectangular projection about `lat_origin`. Over the few tens of
    kilometres a single road segment spans this is accurate to well under a
    metre, which is far finer than the 150 m snapping tolerance it feeds.
    """
    x = math.radians(lon) * math.cos(math.radians(lat_origin)) * EARTH_RADIUS_KM
    y = math.radians(lat) * EARTH_RADIUS_KM

    return x, y


def point_to_leg_distance_km(
    lat: float,
    lon: float,
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    """Shortest distance from a point to a single polyline leg (not the
    infinite line -- the projection is clamped to the leg's endpoints)."""
    origin = (lat1 + lat2) / 2.0

    px, py = _local_xy(lat, lon, origin)
    ax, ay = _local_xy(lat1, lon1, origin)
    bx, by = _local_xy(lat2, lon2, origin)

    abx, aby = bx - ax, by - ay
    ab_squared = abx * abx + aby * aby

    if ab_squared == 0.0:
        # Degenerate leg (duplicated vertex): fall back to point distance.
        return haversine_km(lat, lon, lat1, lon1)

    t = ((px - ax) * abx + (py - ay) * aby) / ab_squared
    t = max(0.0, min(1.0, t))

    closest_x = ax + t * abx
    closest_y = ay + t * aby

    return math.hypot(px - closest_x, py - closest_y)


def point_to_linestring_distance_km(
    lat: float,
    lon: float,
    coordinates: Coordinates,
) -> float:
    """Shortest distance from a point to any part of a polyline."""
    return min(
        point_to_leg_distance_km(lat, lon, lon1, lat1, lon2, lat2)
        for (lon1, lat1), (lon2, lat2) in zip(coordinates, coordinates[1:])
    )


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------
def _interpolate(
    start: list[float],
    end: list[float],
    fraction: float,
) -> list[float]:
    """Linear interpolation between two vertices, in degrees."""
    return [
        start[0] + (end[0] - start[0]) * fraction,
        start[1] + (end[1] - start[1]) * fraction,
    ]


def point_at_chainage(coordinates: Coordinates, distance_km: float) -> list[float]:
    """
    The `[lon, lat]` point lying `distance_km` along the polyline.

    Clamped to the polyline's ends. Used to place development defects onto
    real segment geometry instead of at arbitrary coordinates.
    """
    chainage = cumulative_chainage_km(coordinates)
    total = chainage[-1]

    distance_km = max(0.0, min(distance_km, total))

    for index in range(len(coordinates) - 1):
        leg_start, leg_end = chainage[index], chainage[index + 1]

        if leg_start <= distance_km <= leg_end:
            leg_length = leg_end - leg_start

            if leg_length <= 0.0:
                return list(coordinates[index])

            fraction = (distance_km - leg_start) / leg_length

            return _interpolate(coordinates[index], coordinates[index + 1], fraction)

    return list(coordinates[-1])


def slice_linestring(
    coordinates: Coordinates,
    start_km: float,
    end_km: float,
) -> Coordinates:
    """
    Extract the part of a polyline between two chainage positions.

    Every original vertex inside the range is kept, and the cut points are
    interpolated onto the leg they fall on -- so the slice traces exactly the
    same path as the parent corridor, with no shape invented or lost.
    """
    chainage = cumulative_chainage_km(coordinates)
    total = chainage[-1]

    start_km = max(0.0, min(start_km, total))
    end_km = max(start_km, min(end_km, total))

    sliced: Coordinates = []

    for index in range(len(coordinates) - 1):
        leg_start, leg_end = chainage[index], chainage[index + 1]

        if leg_end < start_km or leg_start > end_km:
            continue

        leg_length = leg_end - leg_start

        if leg_length <= 0.0:
            continue

        if leg_start <= start_km <= leg_end and not sliced:
            fraction = (start_km - leg_start) / leg_length
            sliced.append(_interpolate(coordinates[index], coordinates[index + 1], fraction))

        if start_km < leg_end < end_km:
            sliced.append(list(coordinates[index + 1]))

        if leg_start <= end_km <= leg_end:
            fraction = (end_km - leg_start) / leg_length
            sliced.append(_interpolate(coordinates[index], coordinates[index + 1], fraction))
            break

    if len(sliced) < 2:
        # Degenerate slice (zero-length range): return the two nearest vertices
        # rather than an unusable single-point "LineString".
        return [list(coordinates[0]), list(coordinates[1])]

    return sliced


def _best_piece_count(total_km: float, target_length_km: float) -> int:
    """
    Number of equal pieces whose length sits closest to `target_length_km`.

    Considers only the two candidates that bracket the ideal ratio, so the
    result is stable and never explodes into many tiny pieces.
    """
    ratio = total_km / target_length_km

    candidates = {max(1, math.floor(ratio)), max(1, math.ceil(ratio))}

    return min(
        sorted(candidates),
        key=lambda n: (abs(total_km / n - target_length_km), n),
    )


def split_into_segments(
    coordinates: Coordinates,
    target_length_km: float,
) -> list[Coordinates]:
    """
    Cut a corridor polyline into equal pieces of about `target_length_km`.

    The piece count is whichever of ``floor(total / target)`` or
    ``ceil(total / target)`` produces a piece length closest to the target --
    so a 21 km corridor becomes 2 x 10.5 km rather than one 21 km segment,
    while a 17.5 km corridor stays as a single 17.5 km segment rather than
    being halved into two 8.8 km stubs.

    Equal division is used instead of "cut every target km and keep the
    remainder" so a 15.4 km corridor yields one 15.4 km segment rather than a
    15 km segment plus a 0.4 km orphan tail.

    Cuts follow the corridor's own geometry; nothing is straightened,
    buffered, or replaced with a synthetic shape.
    """
    if target_length_km <= 0.0:
        raise ValueError("target_length_km must be positive")

    total = linestring_length_km(coordinates)

    if total <= 0.0:
        raise InvalidGeometryError("cannot segment a zero-length polyline")

    count = _best_piece_count(total, target_length_km)
    piece = total / count

    return [
        slice_linestring(coordinates, index * piece, (index + 1) * piece)
        for index in range(count)
    ]
