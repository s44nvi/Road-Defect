"""
test_reporter_info.py
======================
Proves the full reporter-identity path an officer relies on:

    citizen account -> report submitted -> Defect persisted with citizen_id
    -> officer calls GET /defects/{id} -> response includes reporter.full_name
    -> reporter identity matches the correct citizen
    -> password_hash is never serialized
    -> the route is officer-only (unauthenticated / citizen-token callers
       are rejected, same as the other officer-only mutation routes)

Covers both reporting paths (`POST /reports/image`, and a defect
constructed the way the legacy/anonymous `POST /reports` produces one --
no citizen at all) since a report submitted through the unauthenticated
JSON path has no citizen to report, and that must not error, just come
back with `reporter: null`.
"""

from __future__ import annotations

import io


def _tiny_jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 32 + b"\xff\xd9"


class _MockDetector:
    """Test-only PotholeDetector returning one fixed detection."""

    def __init__(self, detections):
        self._detections = detections

    def detect(self, image_path):
        return self._detections


def _mock_pothole_detection():
    from backend.app.ml.potholes.detector import NormalizedDetection

    return NormalizedDetection(
        class_id=0,
        class_name="pothole",
        confidence=0.9,
        bbox_xyxy=(10.0, 10.0, 100.0, 100.0),
        image_width=640,
        image_height=480,
        model_source="test-mock",
    )


def _submit_image_report(client, citizen_token):
    """POST /reports/image with a mocked detector -- returns the created defect_id."""
    from backend.app.dependencies import get_pothole_detector
    from backend.app.main import app

    app.dependency_overrides[get_pothole_detector] = lambda: _MockDetector(
        [_mock_pothole_detection()]
    )
    try:
        response = client.post(
            "/reports/image",
            headers={"Authorization": f"Bearer {citizen_token}"},
            data={"latitude": "19.0728", "longitude": "72.8826"},
            files={
                "file": ("pothole.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")
            },
        )
    finally:
        app.dependency_overrides.pop(get_pothole_detector, None)

    assert response.status_code == 200, response.json()
    return response.json()["defect_id"]


# ---------------------------------------------------------------------------
# End-to-end path: citizen -> image report -> Defect.citizen_id persisted
# -> officer sees reporter.full_name
# ---------------------------------------------------------------------------
def test_officer_sees_reporter_full_name_for_an_image_report(
    client, officer_client, citizen_token, dev_citizen, db_session
):
    defect_id = _submit_image_report(client, citizen_token)

    # Prove persistence directly against the DB, not just the API response.
    from backend.app.models import Defect

    defect = db_session.query(Defect).filter(Defect.id == defect_id).first()
    assert defect is not None
    assert defect.citizen_id == dev_citizen.id

    # Now the officer-facing read.
    response = officer_client.get(f"/defects/{defect_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["reporter"]["full_name"] == dev_citizen.name
    assert body["reporter"]["id"] == dev_citizen.id
    assert body["reporter"]["email"] == dev_citizen.email


def test_reporter_identity_matches_the_correct_citizen_not_just_any_citizen(
    client, officer_client, citizen_token, dev_citizen, db_session
):
    """Guards against a join/filter bug that could attach the wrong citizen."""
    from backend.app.auth.security import hash_password
    from backend.app.models import Citizen

    other = Citizen(
        name="Someone Else",
        email="someone-else@example.com",
        password_hash=hash_password("irrelevant"),
    )
    db_session.add(other)
    db_session.commit()

    defect_id = _submit_image_report(client, citizen_token)

    body = officer_client.get(f"/defects/{defect_id}").json()

    assert body["reporter"]["full_name"] == dev_citizen.name
    assert body["reporter"]["full_name"] != other.name
    assert body["reporter"]["id"] == dev_citizen.id


def test_reporter_is_null_for_a_legacy_anonymous_defect(client, officer_client, db_session):
    """
    A defect created without a citizen (the unauthenticated `POST /reports`
    path, or any pre-existing row from before citizen association existed)
    must not crash the response -- `reporter` is simply null.
    """
    from backend.app.models import Defect

    defect = Defect(
        defect_type="pothole",
        defect_status="reported",
        defect_severity="medium",
        latitude=19.07,
        longitude=72.88,
        citizen_id=None,
    )
    db_session.add(defect)
    db_session.commit()
    db_session.refresh(defect)

    response = officer_client.get(f"/defects/{defect.id}")

    assert response.status_code == 200
    assert response.json()["reporter"] is None


def test_reporter_response_never_contains_password_hash(
    client, officer_client, citizen_token
):
    defect_id = _submit_image_report(client, citizen_token)

    body = officer_client.get(f"/defects/{defect_id}").json()

    assert "password_hash" not in body["reporter"]
    assert "password" not in body["reporter"]
    assert set(body["reporter"].keys()) == {"id", "full_name", "email"}


# ---------------------------------------------------------------------------
# Access control: reporter info is officer-only.
# ---------------------------------------------------------------------------
def test_unauthenticated_request_cannot_read_defect_detail(client, citizen_token):
    # Deliberately does NOT use `officer_client` -- it mutates `client`'s
    # headers in place (see conftest.py), so requesting both fixtures in one
    # test would leave `client` carrying an officer bearer token, defeating
    # the point of an "unauthenticated" check.
    defect_id = _submit_image_report(client, citizen_token)

    response = client.get(f"/defects/{defect_id}")

    assert response.status_code == 401


def test_citizen_token_cannot_read_defect_detail(client, citizen_token):
    """A citizen token (valid, but the wrong principal type) must not
    authorize the officer-only defect detail route -- same rule already
    enforced on the PATCH endpoints."""
    defect_id = _submit_image_report(client, citizen_token)

    response = client.get(
        f"/defects/{defect_id}",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )

    assert response.status_code == 403


def test_garbage_token_cannot_read_defect_detail(client, citizen_token):
    defect_id = _submit_image_report(client, citizen_token)

    response = client.get(
        f"/defects/{defect_id}",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_inactive_officer_cannot_read_defect_detail(
    client, officer_client, citizen_token, dev_officer, db_session
):
    defect_id = _submit_image_report(client, citizen_token)

    dev_officer.is_active = False
    db_session.commit()

    response = officer_client.get(f"/defects/{defect_id}")

    assert response.status_code == 403


def test_nonexistent_defect_returns_404_not_401_for_officer(officer_client):
    response = officer_client.get("/defects/999999")

    assert response.status_code == 404
