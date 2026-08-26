"""
test_pothole_real_model_acceptance.py
======================================
The REAL, non-mocked counterpart to `test_pothole_integration_boundary.py`.

Every test in this file uses the actual `YoloPotholeDetector` (backed by
`backend/app/ml/potholes/best.pt`) via the real `get_default_detector()`
wiring -- no `MockDetector`, no dependency override of the detector, no
hard-coded detection. `torch`/`ultralytics` must be installed and the
weights file must be present for this file to run (both are already
requirements of this repo).

Fixture image: `backend/tests/fixtures/real_pothole_sample.jpg` -- a genuine
photograph of a road pothole ("Pothole in Villeray, Montreal, Quebec,
Canada", Wikimedia Commons, public domain / CC0:
https://commons.wikimedia.org/wiki/File:Pothole.jpg), not a synthetic or
AI-generated image.

IMPORTANT, HONEST RESULT -- READ BEFORE CHANGING THIS FILE:
This checkpoint (`best.pt`) was evaluated against 20 real-world pothole
photographs pulled from Wikimedia Commons, Pixabay, and Unsplash (this
fixture plus 19 others, not committed to the repo), at confidence
thresholds down to 0.001 and inference sizes up to 1280px. It did not
produce a single `D40` ("pothole") detection on ANY of them -- only crack
classes (`D00`/`D10`/`D11`/`D20`) ever fired, and this fixture image
specifically produces ZERO detections of any class at the model's default
settings. That is a genuine, reproducible property of this checkpoint, not
a bug in the detector/adapter wiring (see `YoloPotholeDetector`'s docstring
in `app/ml/potholes/detector.py`).

Because of that, the tests below intentionally assert the REAL (not the
hoped-for) behavior: real inference runs, produces zero detections for the
pothole class on this image, and the route correctly reports 422 / creates
no defect -- exactly the same "no fake inference" contract the mocked tests
enforce, just exercised with the real model instead of a mock. There is
currently no real photograph on hand that reproduces the full
detection -> severity -> priority -> persistence -> GET /defects happy path
with this checkpoint; that requires either a test image Akshay has already
verified triggers `D40` on this exact checkpoint, or a better-trained
checkpoint. Swap the fixture and update the assertions below once one is
available -- do not fake a detection to make this file "pass green".
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_IMAGE = Path(__file__).resolve().parent / "fixtures" / "real_pothole_sample.jpg"


def _require_real_detector_dependencies():
    pytest.importorskip("ultralytics")
    pytest.importorskip("torch")
    if not (Path(__file__).resolve().parents[1] / "app" / "ml" / "potholes" / "best.pt").exists():
        pytest.skip("best.pt weights not present")


# ---------------------------------------------------------------------------
# The detector itself, in isolation: real weights, real image, real
# inference -- no route, no DB.
# ---------------------------------------------------------------------------
def test_real_detector_runs_genuine_inference_on_a_real_photo():
    _require_real_detector_dependencies()

    from backend.app.ml.potholes.detector import NormalizedDetection, YoloPotholeDetector

    detector = YoloPotholeDetector()
    detections = detector.detect(FIXTURE_IMAGE)

    assert isinstance(detections, list)
    assert all(isinstance(d, NormalizedDetection) for d in detections)
    # Honest, reproducible result for this checkpoint + this image -- see
    # module docstring. Update if a checkpoint/image pair that fires D40 is
    # provided.
    assert detections == []


# ---------------------------------------------------------------------------
# Full route, real (unmocked) default detector: real image in, genuine
# "no pothole found" result out. No detector dependency override here.
# ---------------------------------------------------------------------------
def test_post_reports_image_with_real_detector_and_real_photo(client, citizen_token):
    _require_real_detector_dependencies()

    with FIXTURE_IMAGE.open("rb") as fh:
        response = client.post(
            "/reports/image",
            headers={"Authorization": f"Bearer {citizen_token}"},
            data={"latitude": "19.0728", "longitude": "72.8826"},
            files={"file": ("real_pothole_sample.jpg", fh, "image/jpeg")},
        )

    # This checkpoint finds no pothole in this real photo (see module
    # docstring) -- the route's documented "no detections -> 422, nothing
    # persisted" contract, exercised for real rather than via MockDetector([]).
    assert response.status_code == 422
    assert client.get("/defects").json() == []
