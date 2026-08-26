"""
test_pothole_integration_boundary.py
=====================================
INTEGRATION-CONTRACT tests for the pothole ML integration boundary
(`POST /reports/image`).

These tests use a MOCKED `PotholeDetector` (see `MockDetector` below). They
verify the *plumbing* -- that an image reaches the detector interface, that a
`NormalizedDetection` converts correctly to `DetectionInput`, that the
existing Road Intelligence/AHP service scores it, and that the result is
persisted and returned -- NOT real ML inference. No real model weights are
loaded and no claim is made about real-world detection accuracy.

Until Harmeet's real `PotholeDetector` implementation is wired into
`app.ml.potholes.detector.get_default_detector`, the default detector raises
`ModelUnavailableError`; this is also covered here so the "no fake inference"
guarantee is enforced by the test suite.
"""

from __future__ import annotations

import io

import pytest

from backend.app.ml.potholes.adapter import to_detection_input
from backend.app.ml.potholes.detector import NormalizedDetection

# NOTE: `get_pothole_detector` and `app` are deliberately imported inside each
# fixture/test below rather than at module level. `conftest.db_session`
# reloads every `backend.app.*` module per test (to pick up a fresh
# `DATABASE_URL`), so a module-level import here would hold a stale function
# object that no longer matches the one FastAPI resolves via `Depends(...)`
# in the freshly-reloaded `app.main` -- `app.dependency_overrides` would
# silently have no effect. This mirrors how the `client` fixture in
# conftest.py imports `get_db`/`app` locally for the same reason.


class MockDetector:
    """A stand-in for Harmeet's real detector, returning a fixed, clearly
    test-only detection. Exists ONLY in this test module."""

    def __init__(self, detections):
        self._detections = detections

    def detect(self, image_path):
        return self._detections


def _tiny_jpeg_bytes() -> bytes:
    """Minimal non-empty byte payload; content is never actually decoded as
    an image anywhere in this pipeline (the mocked detector ignores it)."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 32 + b"\xff\xd9"


@pytest.fixture()
def mock_detection() -> NormalizedDetection:
    return NormalizedDetection(
        class_id=0,
        class_name="pothole",
        confidence=0.87,
        bbox_xyxy=(120.0, 80.0, 340.0, 260.0),
        image_width=640,
        image_height=480,
        model_source="mock-test-detector-v0",
    )


@pytest.fixture()
def client_with_mock_detector(client, mock_detection):
    """The shared `client` fixture, with the detector dependency overridden."""
    from backend.app.dependencies import get_pothole_detector
    from backend.app.main import app

    def override_detector():
        return MockDetector([mock_detection])

    app.dependency_overrides[get_pothole_detector] = override_detector
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_pothole_detector, None)


# ---------------------------------------------------------------------------
# 1 & 2: image/path reaches the detector, and it produces a NormalizedDetection
# ---------------------------------------------------------------------------
def test_mock_detector_is_invoked_with_the_uploaded_image(client_with_mock_detector, mock_detection):
    from backend.app.dependencies import get_pothole_detector
    from backend.app.main import app

    called_with = {}

    class RecordingDetector(MockDetector):
        def detect(self, image_path):
            called_with["path"] = image_path
            return super().detect(image_path)

    app.dependency_overrides[get_pothole_detector] = lambda: RecordingDetector([mock_detection])

    response = client_with_mock_detector.post(
        "/reports/image",
        data={"latitude": "19.0728", "longitude": "72.8826"},
        files={"file": ("pothole.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")},
    )

    assert response.status_code == 200
    assert "path" in called_with
    assert str(called_with["path"]).endswith(".jpg")


# ---------------------------------------------------------------------------
# 3: NormalizedDetection converts correctly to DetectionInput
# ---------------------------------------------------------------------------
def test_normalized_detection_converts_to_detection_input(mock_detection):
    detection_input = to_detection_input(mock_detection)

    assert detection_input.class_id == mock_detection.class_id
    assert detection_input.class_name == mock_detection.class_name
    assert detection_input.confidence == mock_detection.confidence
    assert detection_input.bbox == list(mock_detection.bbox_xyxy)
    assert detection_input.image_width == mock_detection.image_width
    assert detection_input.image_height == mock_detection.image_height


# ---------------------------------------------------------------------------
# 4 & 5: DetectionInput reaches the existing Road Intelligence service, and
# the returned severity/priority are persisted correctly
# ---------------------------------------------------------------------------
def test_post_reports_image_persists_road_intelligence_output(client_with_mock_detector):
    response = client_with_mock_detector.post(
        "/reports/image",
        data={"latitude": "19.0728", "longitude": "72.8826"},
        files={"file": ("pothole.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["defect_type"] == "pothole"
    assert body["defect_status"] == "reported"
    assert body["defect_severity"] in {"low", "medium", "high", "critical"}
    assert isinstance(body["defect_priority"], float)
    assert 0.0 <= body["defect_priority"] <= 100.0
    assert body["image_path"]

    # camelCase mirror, consistent with the rest of the officer-facing API
    assert body["defectPriority"] == body["defect_priority"]
    assert body["imagePath"] == body["image_path"]


# ---------------------------------------------------------------------------
# 6 & 7: POST /reports/image returns the persisted intelligence, and it is
# then visible through the existing GET /defects contract
# ---------------------------------------------------------------------------
def test_created_defect_is_visible_through_get_defects(client_with_mock_detector):
    create_response = client_with_mock_detector.post(
        "/reports/image",
        data={"latitude": "19.0728", "longitude": "72.8826"},
        files={"file": ("pothole.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")},
    )
    defect_id = create_response.json()["defect_id"]

    list_response = client_with_mock_detector.get("/defects")
    assert list_response.status_code == 200

    matching = [d for d in list_response.json() if d["defect_id"] == defect_id]
    assert len(matching) == 1
    assert matching[0]["defect_status"] == "reported"
    assert matching[0]["defect_severity"] == create_response.json()["defect_severity"]
    assert matching[0]["defect_priority"] == create_response.json()["defect_priority"]
    assert matching[0]["defect_priority"] is not None


# ---------------------------------------------------------------------------
# No detections -> no defect created, no fabricated result
# ---------------------------------------------------------------------------
def test_no_detections_returns_422_and_creates_no_defect(client):
    from backend.app.dependencies import get_pothole_detector
    from backend.app.main import app

    app.dependency_overrides[get_pothole_detector] = lambda: MockDetector([])
    try:
        response = client.post(
            "/reports/image",
            data={"latitude": "19.0728", "longitude": "72.8826"},
            files={"file": ("empty.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")},
        )
    finally:
        app.dependency_overrides.pop(get_pothole_detector, None)

    assert response.status_code == 422
    assert client.get("/defects").json() == []


# ---------------------------------------------------------------------------
# Default detector (no override): model genuinely not available yet
# ---------------------------------------------------------------------------
def test_default_detector_raises_model_unavailable_not_fake_inference():
    from backend.app.ml.potholes.detector import ModelUnavailableError, get_default_detector

    detector = get_default_detector()

    with pytest.raises(ModelUnavailableError):
        detector.detect("irrelevant/path.jpg")


def test_post_reports_image_returns_503_when_model_unavailable(client):
    # No override: exercises the real default (`UnavailablePotholeDetector`).
    response = client.post(
        "/reports/image",
        data={"latitude": "19.0728", "longitude": "72.8826"},
        files={"file": ("pothole.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")},
    )

    assert response.status_code == 503
    assert client.get("/defects").json() == []
