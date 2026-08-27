"""
consolidation.py
=================
Minimal canonical-incident/duplicate-report consolidation.

Problem: today every citizen report becomes its own independent `Defect`
row, even when several different citizens photograph the same real-world
pothole/crack/encroachment. This module links repeat reports of the same
real-world issue together so the officer/public-facing views can present
ONE municipal defect with an aggregated report count, while every
individual citizen report row (image, ownership, timestamp) stays intact
and separately queryable.

Matching rule (deliberately simple and deterministic):

  A new report is linked as a *duplicate* of an existing *canonical* defect
  when BOTH of the following hold:
    1. Same `defect_type` (exact string match -- "pothole" only matches
       "pothole", never "alligator_crack", etc).
    2. Within `CONSOLIDATION_RADIUS_METERS` (20m) great-circle distance of
       the existing canonical defect's stored lat/lon.

  No temporal constraint is applied. The `Defect` model has no creation
  timestamp column today (only `DefectStatusHistory.changed_at`, which is
  a separate table), and a real-world pothole can legitimately be
  re-reported months apart -- so recency is not treated as a matching
  requirement. If a temporal window is desired later this is the function
  to extend.

  Ties (multiple existing canonical defects within radius) are broken by
  nearest distance.

A "canonical" defect is any `Defect` row whose `canonical_defect_id` is
NULL. A "duplicate" defect has `canonical_defect_id` set to the id of the
canonical row it was matched to. Duplicates are never themselves matched
against (only canonical rows are candidates), so a chain can never form --
every duplicate points directly at a canonical root, one hop.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Defect
from .road_health.geo import haversine_km

# 20 meters: close enough that two reports at this distance are almost
# certainly the same physical defect (a pothole/crack/vendor stall does not
# move), while being safely smaller than the distance between distinct
# defects on the same road. Chosen from the 15-25m guidance range.
CONSOLIDATION_RADIUS_METERS = 20.0


def find_canonical_match(
    db: Session,
    defect_type: str,
    latitude: float,
    longitude: float,
    exclude_defect_id: int | None = None,
) -> Defect | None:
    """
    Return the nearest existing canonical `Defect` of the same type within
    `CONSOLIDATION_RADIUS_METERS`, or `None` if no such defect exists.

    Only considers canonical rows (`canonical_defect_id IS NULL`) as match
    candidates -- duplicates are never matched against directly.

    `exclude_defect_id`, when given, is left out of the candidate set -- so
    that a defect that has already been flushed (and so has an id, and
    would otherwise be its own zero-distance "nearest" candidate) is not
    matched against itself.
    """
    query = db.query(Defect).filter(
        Defect.defect_type == defect_type,
        Defect.canonical_defect_id.is_(None),
    )

    if exclude_defect_id is not None:
        query = query.filter(Defect.id != exclude_defect_id)

    candidates = query.all()

    best: Defect | None = None
    best_distance_m = float("inf")

    for candidate in candidates:
        distance_m = (
            haversine_km(latitude, longitude, candidate.latitude, candidate.longitude)
            * 1000.0
        )
        if distance_m <= CONSOLIDATION_RADIUS_METERS and distance_m < best_distance_m:
            best = candidate
            best_distance_m = distance_m

    return best


def link_to_canonical(db: Session, defect: Defect) -> Defect | None:
    """
    Look up a matching canonical defect for `defect` (same type, within
    radius) and, if found, set `defect.canonical_defect_id` to point at it.

    Must be called after `defect` has been flushed (so it has an id) but
    before the same transaction commits. Excludes `defect` itself from
    matching. Returns the canonical defect it was linked to, or `None` if
    `defect` remains its own canonical root.
    """
    match = find_canonical_match(
        db,
        defect.defect_type,
        defect.latitude,
        defect.longitude,
        exclude_defect_id=defect.id,
    )

    if match is not None:
        defect.canonical_defect_id = match.id
        return match

    return None


def report_count(db: Session, canonical_defect: Defect) -> int:
    """
    Number of reports (the canonical defect itself + every duplicate linked
    to it) representing this real-world issue.
    """
    duplicates = (
        db.query(Defect)
        .filter(Defect.canonical_defect_id == canonical_defect.id)
        .count()
    )
    return 1 + duplicates
