"""
config.py
=========
Single source of truth for every tunable constant used by the Road Health
module (segmentation, defect->segment assignment, health scoring, bands).

Nothing in `geo.py`, `scoring.py`, `assignment.py`, or `service.py` should
hard-code a weight, threshold, or status name. If a number needs to change,
change it here.

The health formula itself is intentionally expressed as a small number of
named constants so it can be tuned without touching logic (see
`scoring.calculate_health_score`).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. DEFECT STATUS VOCABULARY
# ---------------------------------------------------------------------------
# The exact, closed set of statuses the officer workflow allows. Arbitrary
# status strings are rejected at the API boundary (see
# `backend.app.defect_workflow`).
#
# Statuses are stored lowercase in the database. The API accepts any casing
# and normalizes, so an officer frontend sending "CONFIRMED" or "confirmed"
# both work.
STATUS_REPORTED = "reported"
STATUS_CONFIRMED = "confirmed"
STATUS_IN_PROGRESS = "in_progress"
STATUS_RESOLVED = "resolved"
STATUS_REJECTED = "rejected"

ALL_STATUSES: tuple[str, ...] = (
    STATUS_REPORTED,
    STATUS_CONFIRMED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLVED,
    STATUS_REJECTED,
)

# Statuses that represent a defect still degrading the road *right now*.
# These are the only ones that contribute to the health penalty.
ACTIVE_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_REPORTED,
        STATUS_CONFIRMED,
        STATUS_IN_PROGRESS,
    }
)

# Statuses that contribute ZERO to current road degradation.
#   - resolved: the road has been repaired.
#   - rejected: the report was not a real defect in the first place.
RESOLVED_STATUSES: frozenset[str] = frozenset({STATUS_RESOLVED})
REJECTED_STATUSES: frozenset[str] = frozenset({STATUS_REJECTED})
INACTIVE_STATUSES: frozenset[str] = RESOLVED_STATUSES | REJECTED_STATUSES

# ---------------------------------------------------------------------------
# 2. SEVERITY WEIGHTS
# ---------------------------------------------------------------------------
# Severity -> weight contributed to the active issue load. Per the officer
# spec: Critical = 3, Medium = 2, Low = 1.
#
# "high" is included because `road_intelligence` emits a four-band severity
# scale (Low/Medium/High/Critical). A "high" defect is treated as
# critical-equivalent for both weighting and counting rather than being
# silently dropped -- see SEVERITY_BUCKETS below.
SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 3.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
}

# Weight used when a defect's severity string is not in the map above.
# Documented choice: the medium weight. An unrecognized severity should
# neither be ignored (which would understate degradation) nor treated as
# the worst case (which would overstate it).
UNKNOWN_SEVERITY_WEIGHT: float = 2.0

# Severity string -> reported count bucket. The API exposes exactly three
# buckets (critical/medium/low) because that is what the officer frontend
# consumes; "high" folds into critical, and anything unrecognized folds
# into medium, consistent with UNKNOWN_SEVERITY_WEIGHT above.
SEVERITY_BUCKETS: dict[str, str] = {
    "critical": "critical",
    "high": "critical",
    "medium": "medium",
    "low": "low",
}
UNKNOWN_SEVERITY_BUCKET: str = "medium"

# ---------------------------------------------------------------------------
# 3. HEALTH SCORE FORMULA
# ---------------------------------------------------------------------------
# The score is computed on read from canonical segment + defect data. It is
# never stored, so it can never go stale (see road_health/README.md).
#
#   active_load   = sum of SEVERITY_WEIGHTS over ACTIVE defects on the segment
#   load_density  = active_load / max(length_km, MIN_NORMALIZATION_LENGTH_KM)
#   penalty       = MAX_HEALTH_SCORE * load_density
#                                    / (load_density + HALF_HEALTH_LOAD_DENSITY)
#   health_score  = round(MAX_HEALTH_SCORE - penalty, HEALTH_SCORE_DECIMALS)
#
# Normalizing by length is what makes this a *density*, not a count: 6 active
# critical defects spread over 20 km is a healthier road than the same 6
# packed into 2 km. That, plus the severity weighting, is why the result is
# nothing like `10 - number_of_defects`.

MAX_HEALTH_SCORE: float = 10.0

# The severity-weighted active load PER KILOMETRE at which a road's health is
# exactly halved (score 5.0). This is the single most meaningful tuning knob:
# lower it to make the scoring harsher, raise it to make it more forgiving.
#
# Default 1.0 reads as: "one critical defect (weight 3) every 3 km, or one
# low defect (weight 1) every 1 km, halves a road's health score."
HALF_HEALTH_LOAD_DENSITY: float = 1.0

# Guards against divide-by-zero and against a pathologically short segment
# (e.g. a 50 m stub imported from OSM) producing an absurd density from a
# single defect.
MIN_NORMALIZATION_LENGTH_KM: float = 0.5

# The score is rounded before banding so band boundaries are exact and
# deterministic (7.0 -> needs_attention, 7.1 -> healthy).
HEALTH_SCORE_DECIMALS: int = 1

# ---------------------------------------------------------------------------
# 4. HEALTH BANDS
# ---------------------------------------------------------------------------
# Applied to the ROUNDED score. Required boundary behaviour:
#     score > 7.0            -> healthy         (GREEN)
#     4.0 <= score <= 7.0    -> needs_attention (ORANGE)
#     score < 4.0            -> critical        (RED)
# so 7.0 is orange, 7.1 is green, 4.0 is orange, 3.9 is red.
HEALTH_STATUS_HEALTHY: str = "healthy"
HEALTH_STATUS_NEEDS_ATTENTION: str = "needs_attention"
HEALTH_STATUS_CRITICAL: str = "critical"

# Exclusive lower bound for GREEN: a score must be strictly greater than this.
HEALTHY_THRESHOLD: float = 7.0
# Inclusive lower bound for ORANGE: below this is RED.
NEEDS_ATTENTION_THRESHOLD: float = 4.0

# Display colour for each band, so the frontend does not have to hard-code
# the mapping if it would rather read it from the API.
HEALTH_STATUS_COLORS: dict[str, str] = {
    HEALTH_STATUS_HEALTHY: "green",
    HEALTH_STATUS_NEEDS_ATTENTION: "orange",
    HEALTH_STATUS_CRITICAL: "red",
}

# ---------------------------------------------------------------------------
# 5. SEGMENTATION
# ---------------------------------------------------------------------------
# A road corridor polyline is cut along its own geometry by cumulative
# haversine chainage -- never into circles or synthetic shapes.
#
# The corridor is divided into equal pieces, choosing whichever piece count
# lands closest to this target (see geo._best_piece_count). Equal division --
# rather than "cut at 15 km and keep the remainder" -- avoids emitting a
# 0.4 km orphan tail at the end of a 15.4 km road.
TARGET_SEGMENT_LENGTH_KM: float = 15.0

# ---------------------------------------------------------------------------
# 6. DEFECT -> SEGMENT ASSIGNMENT
# ---------------------------------------------------------------------------
# A defect is assigned to the segment whose polyline passes closest to it
# (perpendicular point-to-polyline distance). Beyond this distance the defect
# is left UNASSIGNED (road_segment_id = NULL) rather than being forced onto a
# road it is not actually on.
MAX_SNAP_DISTANCE_KM: float = 0.15

# Mean Earth radius (km), used by the haversine distance in geo.py.
EARTH_RADIUS_KM: float = 6371.0088

# ---------------------------------------------------------------------------
# 7. GEOMETRY PROVENANCE
# ---------------------------------------------------------------------------
# Written to `road_segments.geometry_source` so every row states where its
# geometry came from. See road_health/data/README.md -- the bundled Mumbai
# corridors are APPROXIMATE DEVELOPMENT GEOMETRY, not surveyed/OSM data.
GEOMETRY_SOURCE_DEV: str = "dev_approximate_v1"
GEOMETRY_SOURCE_OSM: str = "osm_overpass"
