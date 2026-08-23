"""
config.py
=========
Single source of truth for every tunable constant used by the Road
Intelligence module (severity estimation + AHP priority scoring).

Nothing in `severity.py`, `ahp.py`, or `scoring.py` should hard-code a
weight, threshold, or mapping. If you need to change a number, change it
here.

IMPORTANT — ADAPT BEFORE PRODUCTION USE
----------------------------------------
This module was built WITHOUT access to the actual project repository
(no YOLO class list, no existing FastAPI/DB models were available at
implementation time). Every value below that depends on the real YOLO
model or road-domain knowledge is a documented, reasonable placeholder.

Before shipping, a human must:
  1. Replace `DEFECT_TYPE_BASE_SEVERITY` keys with the EXACT class names
     (or class_id -> name mapping) produced by the real YOLO model.
  2. Confirm the severity weights (`SEVERITY_WEIGHTS`) and AHP pairwise
     matrix (`AHP_PAIRWISE_COMPARISON`) reflect the organization's actual
     risk priorities (they are currently a defensible starting point,
     not a validated/calibrated model).
  3. Confirm `ROAD_TYPE_CRITICALITY` matches whatever road classification
     scheme (if any) the backend/GIS system actually uses.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. DEFECT TYPE -> BASELINE SEVERITY
# ---------------------------------------------------------------------------
# Maps a YOLO class_name to a baseline severity score in [0, 1].
# Rationale (placeholder domain reasoning — replace with real classes):
#   - A pothole is an acute safety hazard (vehicle damage/accident risk)
#     -> highest baseline severity.
#   - Alligator cracking indicates structural/subsurface failure and
#     tends to precede pothole formation -> high baseline severity.
#   - Rutting affects vehicle control (esp. in rain) -> moderately high.
#   - Surface damage / raveling degrades ride quality but is rarely an
#     acute hazard -> moderate.
#   - Linear cracks (longitudinal/transverse) are early-stage defects
#     -> lower baseline severity.
#   - A prior patch/repair is the least severe (already remediated,
#     may just be showing wear) -> low baseline severity.
DEFECT_TYPE_BASE_SEVERITY: dict[str, float] = {
    "pothole": 0.95,
    "alligator_crack": 0.75,
    "rutting": 0.65,
    "surface_damage": 0.55,
    "longitudinal_crack": 0.45,
    "transverse_crack": 0.45,
    "crack": 0.45,          # generic fallback if only one "crack" class exists
    "patch_repair": 0.25,
}

# Score used when an incoming class_name is not found in the mapping above.
# Chosen as the midpoint so an unmapped/unknown class neither dominates nor
# is ignored by the severity formula -- it is flagged in the breakdown so
# the caller/backend can log and later add the missing class to the map.
UNKNOWN_DEFECT_TYPE_SEVERITY: float = 0.50

# ---------------------------------------------------------------------------
# 2. SEVERITY FORMULA WEIGHTS  (must sum to 1.0)
# ---------------------------------------------------------------------------
# defect_type : intrinsic risk of this class of defect (most important —
#               a small pothole is still fundamentally more dangerous
#               than a small hairline crack)
# size        : how much of the visible road surface is affected
# confidence  : how strong the detection evidence is (lowest weight —
#               this reflects detector certainty, not real-world severity;
#               it should nudge, not dominate, the score)
# dimension   : how far the defect extends across the frame (captures
#               elongated defects like long cracks that a pure area
#               ratio under-represents)
SEVERITY_WEIGHTS: dict[str, float] = {
    "defect_type": 0.35,
    "size": 0.30,
    "dimension": 0.20,
    "confidence": 0.15,
}
assert abs(sum(SEVERITY_WEIGHTS.values()) - 1.0) < 1e-9, "SEVERITY_WEIGHTS must sum to 1.0"

# ---------------------------------------------------------------------------
# 3. SIZE / DIMENSION NORMALIZATION
# ---------------------------------------------------------------------------
# bbox_area_ratio at or above this value is treated as maximally severe
# from a "size" standpoint (score saturates to 1.0). 0.15 means a defect
# covering 15% or more of the analyzed frame is considered as large as it
# gets for scoring purposes. Tune based on typical camera mounting/FOV.
SIZE_SATURATION_RATIO: float = 0.15

# max(bbox_width / image_width, bbox_height / image_height) at or above
# this value saturates the "dimension"/extent score to 1.0.
DIMENSION_SATURATION_RATIO: float = 0.50

# Used only when image_width/image_height are NOT provided, so
# bbox_area_ratio and the frame-extent ratio cannot be computed.
# Documented fallback: neutral midpoint, and the breakdown will mark
# `"estimated": true` for that component so downstream consumers know
# the value is not derived from real measurements.
FALLBACK_SIZE_SCORE: float = 0.50
FALLBACK_DIMENSION_SCORE: float = 0.50

# ---------------------------------------------------------------------------
# 4. SEVERITY CATEGORY THRESHOLDS  (inclusive lower bound, inclusive upper bound)
# ---------------------------------------------------------------------------
SEVERITY_CATEGORY_THRESHOLDS: list[tuple[int, int, str]] = [
    (0, 24, "Low"),
    (25, 49, "Medium"),
    (50, 74, "High"),
    (75, 100, "Critical"),
]

# ---------------------------------------------------------------------------
# 5. AHP CRITERIA
# ---------------------------------------------------------------------------
# Order here defines row/column order of AHP_PAIRWISE_COMPARISON below.
AHP_CRITERIA: list[str] = [
    "severity",
    "size",
    "traffic_criticality",
    "recurrence",
    "location_criticality",
]

# ---------------------------------------------------------------------------
# 6. AHP PAIRWISE COMPARISON MATRIX (Saaty 1-9 scale, reciprocal)
# ---------------------------------------------------------------------------
# Rationale for each judgment (row vs column, "how much more important"):
#
#  severity vs size                 = 3  severity (safety/structural risk)
#                                         is moderately more important than
#                                         raw physical size alone.
#  severity vs traffic_criticality  = 3  an equally severe defect matters
#                                         more than road class alone, but
#                                         road class still matters a lot.
#  severity vs recurrence           = 5  severity is strongly more important
#                                         than how often defects recur —
#                                         recurrence is a secondary signal.
#  severity vs location_criticality = 3  severity moderately outweighs
#                                         proximity to sensitive locations,
#                                         since location data is often
#                                         optional/approximate.
#  size vs traffic_criticality      = 1  treated as equally important —
#                                         both are concrete, measurable
#                                         repair-urgency signals.
#  size vs recurrence                = 3  a currently large defect matters
#                                         moderately more than repeated
#                                         small detections.
#  size vs location_criticality     = 1  equally important.
#  traffic_criticality vs recurrence = 3  road importance moderately
#                                          outweighs recurrence.
#  traffic_criticality vs location   = 1  equally important — both describe
#                                          "where" this defect sits.
#  recurrence vs location_criticality = 1/3  location criticality is
#                                             moderately more important
#                                             than recurrence.
#
# This matrix is intentionally simple/defensible; it is NOT empirically
# calibrated against real repair-priority outcomes. It has been verified
# to be consistent (see ahp.py -> consistency_ratio, computed = 0.0094,
# well under the 0.10 acceptability threshold).
AHP_PAIRWISE_COMPARISON: list[list[float]] = [
    #        severity   size    traffic   recur   location
    [        1.0,       3.0,    3.0,      5.0,    3.0   ],  # severity
    [        1 / 3,     1.0,    1.0,      3.0,    1.0   ],  # size
    [        1 / 3,     1.0,    1.0,      3.0,    1.0   ],  # traffic_criticality
    [        1 / 5,     1 / 3,  1 / 3,    1.0,    1 / 3 ],  # recurrence
    [        1 / 3,     1.0,    1.0,      3.0,    1.0   ],  # location_criticality
]

# Saaty Random Index (RI) table, used to compute the Consistency Ratio.
AHP_RANDOM_INDEX: dict[int, float] = {
    1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12,
    6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49,
}

# A matrix with CR above this value is flagged as inconsistent. The AHP
# module raises/flags rather than silently returning weights in that case.
AHP_CONSISTENCY_RATIO_THRESHOLD: float = 0.10

# ---------------------------------------------------------------------------
# 7. AHP CRITERION FALLBACKS (used when optional context data is missing)
# ---------------------------------------------------------------------------
# road_type -> normalized traffic criticality in [0, 1], used only when the
# caller supplies a `road_type` string instead of a numeric
# `traffic_criticality` value directly.
ROAD_TYPE_CRITICALITY: dict[str, float] = {
    "local": 0.25,
    "collector": 0.50,
    "arterial": 0.75,
    "highway": 1.00,
}

# Used when NEITHER `traffic_criticality` NOR `road_type` is supplied.
# Documented as a neutral, non-alarmist default: we do not know the road
# class, so we assume "average" rather than "highway" or "local".
TRAFFIC_CRITICALITY_FALLBACK: float = 0.50

# Defect count (in the same road segment/cluster) at or above which the
# recurrence score saturates to 1.0.
RECURRENCE_SATURATION_COUNT: int = 5

# Used when `recurrence_count` is not supplied. Documented as a
# CONSERVATIVE (not neutral) default: absence of recurrence data should
# not inflate priority, so we assume no known recurrence (0), not "average".
RECURRENCE_FALLBACK_NORMALIZED: float = 0.0

# Used when `location_criticality` (proximity to schools/hospitals/
# junctions/etc.) is not supplied by the backend. This criterion requires
# external GIS/contextual data this module does not have access to.
# Documented as a CONSERVATIVE default of 0 (no known proximity to
# critical infrastructure) rather than fabricating a value.
LOCATION_CRITICALITY_FALLBACK: float = 0.0
