"""
adapter.py
==========
The only piece of conversion logic this integration needs: turning a
`NormalizedDetection` (the pothole-detector contract) into a
`DetectionInput` (the existing `road_intelligence` contract).

`DetectionInput` already represents everything the Road Intelligence/AHP
service needs (class_id, class_name, confidence, bbox, image dimensions), so
this is a field mapping, not a second scoring/detection schema. `model_source`
has no equivalent in `DetectionInput` because AHP/severity scoring does not
use it; callers that need provenance read it off `NormalizedDetection`
directly before/alongside calling this function.
"""

from __future__ import annotations

from ...road_intelligence.schemas import DetectionInput
from .detector import NormalizedDetection


def to_detection_input(detection: NormalizedDetection) -> DetectionInput:
    """Map one normalized pothole detection onto the existing DetectionInput."""
    return DetectionInput(
        class_id=detection.class_id,
        class_name=detection.class_name,
        confidence=detection.confidence,
        bbox=list(detection.bbox_xyxy),
        image_width=detection.image_width,
        image_height=detection.image_height,
    )
