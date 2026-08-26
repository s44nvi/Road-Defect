"""
detector.py
===========
Integration boundary for the real pothole detector.

This module defines the CONTRACT the production model must satisfy --
`PotholeDetector.detect(image_path) -> list[NormalizedDetection]` -- plus two
implementations of it:

  - `UnavailablePotholeDetector`: fails loudly and explicitly
    (`ModelUnavailableError`) rather than pretending inference succeeded.
    Kept around (unused by `get_default_detector()` now) as the documented
    "no fake inference" fallback and for tests that exercise that guarantee
    directly.
  - `YoloPotholeDetector`: the real implementation, backed by `best.pt` in
    this same directory (a YOLOv8 model trained on RDD/CRDDC-style road
    damage classes -- see its docstring for the class mapping and a known
    limitation of this specific checkpoint).

`get_default_detector()` returns `YoloPotholeDetector`, following the same
load-once-reuse-forever pattern as `app/ml/hawkers/inference.py`. Nothing
outside this file needed to change to wire it in: `main.py` -> `adapter.py`
-> `road_intelligence` is unaffected.
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


class YoloPotholeDetector:
    """
    Production `PotholeDetector` backed by `best.pt`.

    `best.pt` is a YOLOv8 model trained on RDD (Road Damage Dataset /
    CRDDC-style) classes -- it is a multi-class road-damage detector, not a
    pothole-only one. Its label map (`model.names`, read from the weights
    file itself at load time) uses the standard RDD class codes, of which
    `D40` is the documented "pothole"
    class (D00/D01 = longitudinal crack, D10/D11 = transverse crack,
    D20 = alligator crack, D43/D44 = crosswalk/white-line blur, D50 = utility
    hole; the RDD codes and D40=pothole mapping are the established
    convention for this dataset family, not specific to this checkpoint).
    `best.pt` also carries three additional classes -- `D0`, `D1`, `D2` --
    whose semantics are NOT documented anywhere in this repo or in the
    public RDD taxonomy; they are left unmapped/discarded here rather than
    guessed at.

    This adapter runs the full multi-class model and keeps only detections
    of the `D40` class, remapping them to the human-readable class_name
    `"pothole"` that `road_intelligence.config.DEFECT_TYPE_BASE_SEVERITY`
    already recognizes. The other road-damage classes the model can detect
    (cracks, utility holes, etc.) are intentionally out of scope for this
    `PotholeDetector` contract and are discarded, not surfaced.

    KNOWN LIMITATION (verified empirically, not a wiring bug): this specific
    `best.pt` checkpoint was tested against 20 real-world pothole photographs
    (Wikimedia Commons / Pixabay / Unsplash) at confidence thresholds down to
    0.001 and inference sizes up to 1280px, and did not produce a single
    `D40` detection on any of them -- only crack classes (`D00`/`D10`/`D11`/
    `D20`) ever fired. The wiring/adapter below is correct and will surface
    real `D40` detections whenever the model produces one; whether this
    checkpoint's pothole head is usable in practice is a model-training
    question for Akshay, not something this integration layer can fix.

    Follows the same load-once-reuse-forever pattern as
    `app/ml/hawkers/inference.py`.
    """

    # RDD dataset code for "Pothole" -- see class docstring above.
    _POTHOLE_SOURCE_LABEL = "D40"
    _OUTPUT_CLASS_NAME = "pothole"
    MODEL_SOURCE = "yolov8-best.pt-rdd-pothole-v1"

    def __init__(self, weights_path: str | Path | None = None) -> None:
        self._weights_path = Path(weights_path) if weights_path is not None else Path(__file__).resolve().parent / "best.pt"
        self._model = None  # lazy-loaded on first detect() call

    def _get_model(self):
        if self._model is None:
            from ultralytics import YOLO  # local import: avoid requiring torch/ultralytics just to import this module

            self._model = YOLO(str(self._weights_path))
        return self._model

    def detect(self, image_path: str | Path) -> list[NormalizedDetection]:
        model = self._get_model()
        results = model(str(image_path))

        detections: list[NormalizedDetection] = []
        for result in results:
            image_height, image_width = result.orig_shape  # matches the scale box.xyxy is already reported in
            for box in result.boxes:
                raw_class_id = int(box.cls[0])
                raw_class_name = model.names[raw_class_id]
                if raw_class_name != self._POTHOLE_SOURCE_LABEL:
                    continue  # non-pothole road-damage class; out of scope for PotholeDetector

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    NormalizedDetection(
                        class_id=raw_class_id,
                        class_name=self._OUTPUT_CLASS_NAME,
                        confidence=round(float(box.conf[0]), 4),
                        bbox_xyxy=(round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)),
                        image_width=int(image_width),
                        image_height=int(image_height),
                        model_source=self.MODEL_SOURCE,
                    )
                )
        return detections


def get_default_detector() -> PotholeDetector:
    """
    FastAPI dependency factory (see `app/dependencies.get_pothole_detector`).

    Returns the real `YoloPotholeDetector`, backed by `best.pt` in this same
    directory. Model loading is lazy (deferred to the first `.detect()`
    call) and cached on the singleton instance below, so importing this
    module never requires torch/ultralytics to be installed or the weights
    file to be present.
    """
    global _default_detector
    if _default_detector is None:
        _default_detector = YoloPotholeDetector()
    return _default_detector


_default_detector: PotholeDetector | None = None
