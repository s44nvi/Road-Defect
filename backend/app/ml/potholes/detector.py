"""
detector.py
===========
Integration boundary for Harmeet's real pothole detector.

This module defines the CONTRACT the production model must satisfy --
`PotholeDetector.detect(image_path) -> list[NormalizedDetection]` -- and
nothing else. It intentionally contains no inference logic and no
hard-coded/fake detections.

Until the real model artifact and adapter are available, `get_default_detector()`
returns `UnavailablePotholeDetector`, which fails loudly and explicitly
(`ModelUnavailableError`) rather than pretending inference succeeded. This
lets `POST /reports/image` exist and be exercised end-to-end (with a mocked
detector in tests) before the real model lands, without ever fabricating a
detection.

When Harmeet's model is ready, the expected handoff is a class that
implements `PotholeDetector` -- e.g. a `YoloPotholeDetector` in this same
package, following the pattern already used by `app/ml/hawkers/inference.py`
(load the model once, run inference, normalize the raw output into
`NormalizedDetection`). Nothing outside this file needs to change: swap what
`get_default_detector()` returns and the rest of the pipeline
(`main.py` -> `adapter.py` -> `road_intelligence`) is unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class NormalizedDetection:
    """
    The normalized shape every pothole detector implementation must produce,
    regardless of what raw format its underlying model emits.

    Mirrors `road_intelligence.schemas.DetectionInput` plus provenance
    (`model_source`) that DetectionInput does not need but the rest of the
    system (persistence/audit) may want to know.
    """

    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
    image_width: int | None
    image_height: int | None
    model_source: str


class PotholeDetector(Protocol):
    """
    The interface Harmeet's real detector implements.

    `detect()` takes a path to an already-persisted image and returns zero or
    more normalized detections found in it. Implementations own their own
    model loading/caching (see `app/ml/hawkers/inference.py` for the pattern:
    load once into a module-level singleton, reuse across calls).
    """

    def detect(self, image_path: str | Path) -> list[NormalizedDetection]:
        ...


class ModelUnavailableError(RuntimeError):
    """
    Raised by `UnavailablePotholeDetector` -- the production model artifact
    and inference implementation have not been provided yet.

    Callers (the `POST /reports/image` route) must translate this into a
    clear HTTP error (503) rather than allow the request to silently succeed
    with no detections.
    """


class UnavailablePotholeDetector:
    """
    Placeholder `PotholeDetector` used until Harmeet's real implementation is
    plugged in.

    Deliberately does NOT return `[]` or any hard-coded detection -- an empty
    list would be indistinguishable from "the model ran and found no
    potholes", which is a fake result. This raises instead, so the failure is
    unambiguous.
    """

    def detect(self, image_path: str | Path) -> list[NormalizedDetection]:
        raise ModelUnavailableError(
            "Pothole detection model is not available yet. "
            "This is the integration boundary for Harmeet's real detector "
            "(see app/ml/potholes/detector.py) -- no real or fabricated "
            "inference has been performed."
        )


def get_default_detector() -> PotholeDetector:
    """
    FastAPI dependency factory (see `app/dependencies.get_pothole_detector`).

    Returns the placeholder detector today. Once Harmeet's real
    implementation exists, this is the single place to swap it in.
    """
    return UnavailablePotholeDetector()
