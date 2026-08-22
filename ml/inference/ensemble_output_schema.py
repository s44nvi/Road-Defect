"""Unified output contract emitted by all hazard models."""

from typing import TypedDict


class BoundingBox(TypedDict):
    x: float
    y: float
    width: float
    height: float


DetectionResult = TypedDict(
    "DetectionResult",
    {
        "class": str,
        "bbox": BoundingBox,
        "confidence": float,
        "model_source": str,
    },
)