"""
arbitration.py
===============
Class-semantics-based arbitration between the two pothole-family models:

  - `best.pt`  (v1, RDD/CRDDC multi-class road-damage model): authoritative
    source for non-pothole road-damage classes it supports (currently
    "crack", mapped from the RDD codes D00/D01/D10/D11/D20). Its pothole
    (`D40`) detections are also considered, but only as a fallback -- see
    below.
  - `pothole.pt` (v2, YOLO26s "MWPD" single-class pothole model -- confirmed
    by direct inspection of the checkpoint's embedded `train_args`:
    `scale: 's'`, `yaml_file: yolo26s.yaml`, 640px, 100 epochs, run name
    `yolo26s_mwpd`):
    authoritative for "pothole" whenever it clears
    `POTHOLE_V2_CONFIDENCE_THRESHOLD`.

Threshold source: the handoff README for `yolo26s_mwpd_v1_handoff`
states "Lower `conf` to trade precision for recall; 0.15-0.20 is a
reasonable starting point if missing a pothole matters more than a false
alarm." We start at the low (highest-recall) end of that documented range,
0.15, as an explicit named constant -- not a magic number inline in a
route.

Arbitration rules (NOT a raw-confidence comparison across models -- v2 is
class-semantics-authoritative for "pothole" once past its threshold,
regardless of what v1's pothole confidence happens to be):

  1. If v2 has a pothole detection >= POTHOLE_V2_CONFIDENCE_THRESHOLD,
     it wins (highest-confidence v2 pothole detection returned). This is
     true whether or not v1 also detected a pothole.
  2. Else, if v1 detected a supported non-pothole class it owns (e.g.
     "crack"), that detection wins -- a weak/absent v2 pothole result
     never suppresses a v1 crack detection.
  3. Else, if v1 detected a pothole (its own D40 class) even though v2
     did not clear its threshold, that is used as a last-resort fallback
     (v1 is a general detector and may occasionally catch what v2 misses).
  4. Else: no detection (None). Never fabricated.
"""

from __future__ import annotations

from .detector import NormalizedDetection

# Handoff README ("yolo26s_mwpd_v1_handoff"): "0.15-0.20 is a reasonable
# starting point if missing a pothole matters more than a false alarm."
# Recall-priority -> pick the low end of the documented range.
POTHOLE_V2_CONFIDENCE_THRESHOLD = 0.15

# Non-pothole road-damage classes `best.pt` (v1) is authoritative for.
# See `YoloPotholeDetector` docstring for the RDD class-code mapping.
V1_SUPPORTED_NON_POTHOLE_CLASSES = frozenset({"crack"})

POTHOLE_CLASS_NAME = "pothole"


def arbitrate_pothole_detections(
    v1_detections: list[NormalizedDetection],
    v2_detections: list[NormalizedDetection],
) -> NormalizedDetection | None:
    """
    Combine `best.pt` (v1) and `pothole.pt` (v2) detections for one image into
    a single arbitrated `NormalizedDetection`, or `None` if nothing
    sufficiently confident/supported was found.
    """
    v2_potholes = [
        d
        for d in v2_detections
        if d.class_name == POTHOLE_CLASS_NAME
        and d.confidence >= POTHOLE_V2_CONFIDENCE_THRESHOLD
    ]
    if v2_potholes:
        return max(v2_potholes, key=lambda d: d.confidence)

    v1_supported = [
        d for d in v1_detections if d.class_name in V1_SUPPORTED_NON_POTHOLE_CLASSES
    ]
    if v1_supported:
        return max(v1_supported, key=lambda d: d.confidence)

    v1_potholes = [d for d in v1_detections if d.class_name == POTHOLE_CLASS_NAME]
    if v1_potholes:
        return max(v1_potholes, key=lambda d: d.confidence)

    return None
