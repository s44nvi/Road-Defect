"""
assignment.py
=============
Deterministic mapping of a defect (latitude/longitude) to its one canonical
road segment.

Rules, in order:

  1. For every segment, compute the perpendicular distance from the defect to
     the segment's polyline (clamped to the polyline, so a defect off the end
     of a road measures to its endpoint, not to an imaginary extension).
  2. The nearest segment wins.
  3. Ties are broken by ascending `segment_id`, so the result never depends on
     database row order.
  4. If the nearest segment is farther than `MAX_SNAP_DISTANCE_KM`, the defect
     is left UNASSIGNED (`road_segment_id = None`). A defect is never forced
     onto a road it is not on.

A defect is assigned to exactly one segment; nothing here ever duplicates a
defect record.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config
from .geo import InvalidGeometryError, parse_geometry_parts, point_to_geometry_distance_km


@dataclass(frozen=True)
class SegmentGeometry:
    """The minimum a segment needs to expose to be a snapping candidate."""

    id: int
    segment_id: str
    geometry: dict


@dataclass(frozen=True)
class AssignmentResult:
    """Which segment a defect snapped to, and how far away it was."""

    segment_pk: int | None
    segment_id: str | None
    distance_km: float | None

    @property
    def assigned(self) -> bool:
        return self.segment_pk is not None


UNASSIGNED = AssignmentResult(segment_pk=None, segment_id=None, distance_km=None)


def find_nearest_segment(
    latitude: float,
    longitude: float,
    segments: list[SegmentGeometry],
    max_distance_km: float | None = None,
) -> AssignmentResult:
    """Snap one point to the nearest segment, or return UNASSIGNED."""
    if max_distance_km is None:
        max_distance_km = config.MAX_SNAP_DISTANCE_KM

    best: AssignmentResult = UNASSIGNED
    best_distance = float("inf")

    for segment in segments:
        try:
            parts = parse_geometry_parts(segment.geometry)
        except InvalidGeometryError:
            # A segment with unusable geometry is skipped rather than
            # crashing an import of thousands of defects.
            continue

        distance = point_to_geometry_distance_km(latitude, longitude, parts)

        # Strict `<` plus the segment_id tie-break keeps this deterministic
        # regardless of the order rows come back from the database.
        if distance < best_distance or (
            distance == best_distance
            and best.segment_id is not None
            and segment.segment_id < best.segment_id
        ):
            best_distance = distance
            best = AssignmentResult(
                segment_pk=segment.id,
                segment_id=segment.segment_id,
                distance_km=round(distance, 6),
            )

    if best.segment_pk is None or best_distance > max_distance_km:
        return UNASSIGNED

    return best
