"""
test_analyze_submit_and_arbitration.py
=======================================
Covers the new analyze/submit split (POST /reports/analyze,
POST /reports/submit) and the dual-pothole-model (best.pt + best2.pt)
arbitration logic.

Uses MOCKED detectors throughout (deterministic, no real model loading) --
same convention as `test_pothole_integration_boundary.py`. Real-model smoke
tests for best2.pt live in the manual verification done during
implementation (see arbitration.py / detector.py docstrings); this file
exercises the plumbing and the arbitration rules themselves.
"""

from __future__ import annotations

import pytest


class MockPotholeDetector:
    def __init__(self, detections):
        self._detections = detections

    def detect(self, image_path):
        return self._detections


class MockHawkerDetector:
    def __init__(self, detections):
        self._detections = detections

    def __call__(self, image_path):
        return self._detections


def _tiny_jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 32 + b"\xff\xd9"


def _citizen_headers(client, email="analyze-submit@example.com") -> dict[str, str]:
    from backend.app.auth.security import hash_password
    from backend.app.database import SessionLocal
    from backend.app.models import Citizen

    db = SessionLocal()
    try:
        citizen = Citizen(
            name="Analyze Submit Citizen",
            email=email,
            password_hash=hash_password("test-password"),
        )
        db.add(citizen)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/auth/citizen/login",
        json={"email": email, "password": "test-password"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _pothole_detection(confidence=0.9, class_name="pothole"):
    from backend.app.ml.potholes.detector import NormalizedDetection

    return NormalizedDetection(
        class_id=0,
        class_name=class_name,
        confidence=confidence,
        bbox_xyxy=(10.0, 10.0, 100.0, 100.0),
        image_width=640,
        image_height=480,
        model_source="mock",
    )


def _hawker_detection(confidence=0.9, class_name="hawker"):
    return {
        "class_id": 0,
        "class_name": class_name,
        "confidence": confidence,
        "bbox": [5.0, 5.0, 50.0, 50.0],
        "image_width": 640,
        "image_height": 480,
    }


# ---------------------------------------------------------------------------
# 1 & 2: analyze does not create a Defect; real category returned
# ---------------------------------------------------------------------------
def test_analyze_does_not_create_defect_and_returns_real_category(client, db_session):
    from backend.app.dependencies import get_dual_pothole_detector, get_hawker_detector
    from backend.app.main import app
    from backend.app.models import Defect

    headers = _citizen_headers(client)

    app.dependency_overrides[get_dual_pothole_detector] = lambda: MockPotholeDetector(
        [_pothole_detection(confidence=0.85)]
    )
    app.dependency_overrides[get_hawker_detector] = lambda: MockHawkerDetector([])

    response = client.post(
        "/reports/analyze",
        headers=headers,
        data={"latitude": "19.07", "longitude": "72.87"},
        files={"file": ("pothole.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "pothole"
    assert body["confidence"] == 0.85
    assert body["image_token"]

    assert db_session.query(Defect).count() == 0


def test_analyze_no_detection_returns_explicit_null_not_pothole_default(client):
    from backend.app.dependencies import get_dual_pothole_detector, get_hawker_detector
    from backend.app.main import app

    headers = _citizen_headers(client, email="no-detect@example.com")

    app.dependency_overrides[get_dual_pothole_detector] = lambda: MockPotholeDetector([])
    app.dependency_overrides[get_hawker_detector] = lambda: MockHawkerDetector([])

    response = client.post(
        "/reports/analyze",
        headers=headers,
        files={"file": ("blank.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] is None
    assert body["confidence"] is None
    assert body["bbox"] is None


# ---------------------------------------------------------------------------
# 4: vendor/hawker image never comes back as "pothole"
# ---------------------------------------------------------------------------
def test_analyze_hawker_image_not_returned_as_pothole(client):
    from backend.app.dependencies import get_dual_pothole_detector, get_hawker_detector
    from backend.app.main import app

    headers = _citizen_headers(client, email="hawker-analyze@example.com")

    app.dependency_overrides[get_dual_pothole_detector] = lambda: MockPotholeDetector([])
    app.dependency_overrides[get_hawker_detector] = lambda: MockHawkerDetector(
        [_hawker_detection(confidence=0.77)]
    )

    response = client.post(
        "/reports/analyze",
        headers=headers,
        files={"file": ("vendor.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "hawker"
    assert body["category"] != "pothole"


# ---------------------------------------------------------------------------
# 2 & 3: submit creates exactly one Defect with correct fields; officer can
# retrieve full detail after submit.
# ---------------------------------------------------------------------------
def test_submit_creates_defect_and_officer_can_retrieve_full_detail(client, db_session, officer_token):
    from backend.app.dependencies import get_dual_pothole_detector, get_hawker_detector
    from backend.app.main import app
    from backend.app.models import Defect

    headers = _citizen_headers(client, email="submit-flow@example.com")

    app.dependency_overrides[get_dual_pothole_detector] = lambda: MockPotholeDetector(
        [_pothole_detection(confidence=0.9)]
    )
    app.dependency_overrides[get_hawker_detector] = lambda: MockHawkerDetector([])

    analyze_response = client.post(
        "/reports/analyze",
        headers=headers,
        data={"latitude": "19.07", "longitude": "72.87"},
        files={"file": ("pothole.jpg", _tiny_jpeg_bytes(), "image/jpeg")},
    )
    assert analyze_response.status_code == 200
    token = analyze_response.json()["image_token"]
    assert db_session.query(Defect).count() == 0

    submit_response = client.post(
        "/reports/submit",
        headers=headers,
        json={
            "image_token": token,
            "latitude": 19.07,
            "longitude": 72.87,
            "defect_type": "pothole",
            "defect_severity": "high",
        },
    )
    assert submit_response.status_code == 200
    body = submit_response.json()
    assert body["defect_severity"] == "high"
    assert body["image_path"]
    assert body["image_url"] is not None and body["image_url"].startswith("/uploads/")

    assert db_session.query(Defect).count() == 1
    defect = db_session.query(Defect).first()
    assert defect.citizen_id is not None
    assert defect.defect_severity == "high"
    assert defect.image_path == body["image_path"]
    assert defect.ai_confidence == 0.9

    # Officer detail retrieval.
    officer_response = client.get(
        f"/defects/{defect.id}",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert officer_response.status_code == 200
    detail = officer_response.json()
    assert detail["ai_confidence"] == 0.9
    assert detail["reported_at"] is not None
    assert detail["reporter"]["email"] == "submit-flow@example.com"
    assert "password_hash" not in detail["reporter"]


def test_submit_unknown_image_token_returns_404(client):
    headers = _citizen_headers(client, email="bad-token@example.com")

    response = client.post(
        "/reports/submit",
        headers=headers,
        json={
            "image_token": "doesnotexist",
            "latitude": 19.07,
            "longitude": 72.87,
            "defect_type": "pothole",
            "defect_severity": "medium",
        },
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 5-8: dual-model arbitration unit tests
# ---------------------------------------------------------------------------
def test_arbitration_strong_v2_pothole_wins_over_weak_v1():
    from backend.app.ml.potholes.arbitration import arbitrate_pothole_detections
    from backend.app.ml.potholes.detector import NormalizedDetection

    v1 = [
        NormalizedDetection(0, "pothole", 0.05, (0, 0, 10, 10), 100, 100, "v1"),
    ]
    v2 = [
        NormalizedDetection(0, "pothole", 0.6, (0, 0, 10, 10), 100, 100, "v2"),
    ]

    winner = arbitrate_pothole_detections(v1, v2)
    assert winner is not None
    assert winner.model_source == "v2"
    assert winner.confidence == 0.6


def test_arbitration_v1_crack_preserved_when_v2_weak():
    from backend.app.ml.potholes.arbitration import arbitrate_pothole_detections
    from backend.app.ml.potholes.detector import NormalizedDetection

    v1 = [
        NormalizedDetection(0, "crack", 0.7, (0, 0, 10, 10), 100, 100, "v1"),
    ]
    v2 = [
        NormalizedDetection(0, "pothole", 0.05, (0, 0, 10, 10), 100, 100, "v2"),
    ]

    winner = arbitrate_pothole_detections(v1, v2)
    assert winner is not None
    assert winner.model_source == "v1"
    assert winner.class_name == "crack"


def test_arbitration_v1_crack_preserved_when_v2_absent():
    from backend.app.ml.potholes.arbitration import arbitrate_pothole_detections
    from backend.app.ml.potholes.detector import NormalizedDetection

    v1 = [
        NormalizedDetection(0, "crack", 0.55, (0, 0, 10, 10), 100, 100, "v1"),
    ]

    winner = arbitrate_pothole_detections(v1, [])
    assert winner is not None
    assert winner.class_name == "crack"


def test_arbitration_both_detect_pothole_v2_authoritative():
    from backend.app.ml.potholes.arbitration import arbitrate_pothole_detections
    from backend.app.ml.potholes.detector import NormalizedDetection

    v1 = [
        NormalizedDetection(0, "pothole", 0.99, (0, 0, 10, 10), 100, 100, "v1"),
    ]
    v2 = [
        NormalizedDetection(0, "pothole", 0.2, (0, 0, 10, 10), 100, 100, "v2"),
    ]

    winner = arbitrate_pothole_detections(v1, v2)
    assert winner is not None
    assert winner.model_source == "v2"


def test_arbitration_neither_confident_no_detection():
    from backend.app.ml.potholes.arbitration import arbitrate_pothole_detections
    from backend.app.ml.potholes.detector import NormalizedDetection

    v1 = [
        NormalizedDetection(0, "some_other_class", 0.9, (0, 0, 10, 10), 100, 100, "v1"),
    ]
    v2 = [
        NormalizedDetection(0, "pothole", 0.05, (0, 0, 10, 10), 100, 100, "v2"),
    ]

    winner = arbitrate_pothole_detections(v1, v2)
    assert winner is None


def test_arbitration_threshold_value_matches_readme_recall_priority_start():
    """
    Pin the threshold to the documented handoff README value (0.15, the low
    end of the "0.15-0.20" recall-priority range) so a future accidental
    change is caught explicitly.
    """
    from backend.app.ml.potholes.arbitration import POTHOLE_V2_CONFIDENCE_THRESHOLD

    assert POTHOLE_V2_CONFIDENCE_THRESHOLD == 0.15


# ---------------------------------------------------------------------------
# 10: status transitions persist correctly end to end (re-verification)
# ---------------------------------------------------------------------------
def test_status_transitions_persist_and_invalid_transition_rejected(officer_client):
    created = officer_client.post(
        "/reports",
        json={
            "defect_type": "pothole",
            "defect_severity": "medium",
            "latitude": 19.07,
            "longitude": 72.87,
        },
    )
    assert created.status_code == 200
    defect_id = created.json()["defect_id"]

    class _D:
        id = defect_id

    defect = _D()

    confirm = officer_client.patch(
        f"/defects/{defect.id}/status",
        json={"status": "confirmed"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["defect_status"] == "confirmed"

    refetch = officer_client.get(f"/defects/{defect.id}")
    assert refetch.status_code == 200
    assert refetch.json()["defect_status"] == "confirmed"

    in_progress = officer_client.patch(
        f"/defects/{defect.id}/status",
        json={"status": "in_progress"},
    )
    assert in_progress.status_code == 200
    assert in_progress.json()["defect_status"] == "in_progress"

    resolved = officer_client.patch(
        f"/defects/{defect.id}/status",
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["defect_status"] == "resolved"

    # Terminal status: no further transition allowed.
    invalid = officer_client.patch(
        f"/defects/{defect.id}/status",
        json={"status": "confirmed"},
    )
    assert invalid.status_code == 409

    history = officer_client.get(f"/defects/{defect.id}/status-history")
    assert history.status_code == 200
    statuses = [entry["new_status"] for entry in history.json()]
    assert statuses == ["reported", "confirmed", "in_progress", "resolved"]
    # IST-converted timestamps still parse as timezone-aware ISO datetimes.
    for entry in history.json():
        assert "+" in entry["changed_at"] or entry["changed_at"].endswith("Z")
