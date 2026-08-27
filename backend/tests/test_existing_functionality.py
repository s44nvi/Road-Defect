"""
Regression tests for pre-existing endpoints that must keep working exactly as
before: GET /defects, POST /reports, and the general health check.

`POST /reports` now requires an authenticated citizen because reports must be
owned by the citizen who submitted them. These tests therefore authenticate a
test citizen before creating reports.

`defect_priority` is deliberately included because GET /defects and
POST /reports expose the AHP priority score persisted by the pothole image
pipeline. JSON-only reports have no detection and therefore return null.
"""

from __future__ import annotations


def _citizen_headers(client) -> dict[str, str]:
    """Create a test citizen, log in, and return its bearer header."""
    from backend.app.auth.security import hash_password
    from backend.app.database import SessionLocal
    from backend.app.models import Citizen

    db = SessionLocal()
    try:
        citizen = Citizen(
            name="Regression Test Citizen",
            email="regression@example.com",
            password_hash=hash_password("test-password"),
        )
        db.add(citizen)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/auth/citizen/login",
        json={
            "email": "regression@example.com",
            "password": "test-password",
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check_still_works(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_reports_still_returns_the_original_response_shape(client):
    headers = _citizen_headers(client)

    response = client.post(
        "/reports",
        headers=headers,
        json={
            "defect_type": "pothole",
            "defect_severity": "medium",
            "latitude": 19.05,
            "longitude": 72.85,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == {
        "defect_id",
        "defect_type",
        "defect_status",
        "defect_severity",
        "latitude",
        "longitude",
        "defect_priority",
    }
    assert body["defect_status"] == "reported"
    assert body["defect_type"] == "pothole"
    assert body["defect_severity"] == "medium"
    assert body["latitude"] == 19.05
    assert body["longitude"] == 72.85
    assert body["defect_priority"] is None


def test_get_defects_still_works_and_returns_created_reports(client):
    headers = _citizen_headers(client)

    client.post(
        "/reports",
        headers=headers,
        json={
            "defect_type": "pothole",
            "defect_severity": "high",
            "latitude": 19.1,
            "longitude": 72.9,
        },
    )

    response = client.get("/defects")

    assert response.status_code == 200
    body = response.json()

    assert isinstance(body, list)
    assert len(body) == 1
    # GET /defects additively gained `report_count` (consolidation of
    # duplicate reports into one municipal defect -- see
    # backend/app/consolidation.py); every other key is unchanged.
    assert set(body[0].keys()) == {
        "defect_id",
        "defect_type",
        "defect_status",
        "report_count",
        "defect_severity",
        "latitude",
        "longitude",
        "defect_priority",
    }


def test_get_defects_returns_empty_list_when_nothing_reported(client):
    response = client.get("/defects")

    assert response.status_code == 200
    assert response.json() == []


def test_multiple_reports_all_appear_in_get_defects(client):
    headers = _citizen_headers(client)

    for i in range(3):
        client.post(
            "/reports",
            headers=headers,
            json={
                "defect_type": "crack",
                "defect_severity": "low",
                "latitude": 19.0 + i * 0.01,
                "longitude": 72.8,
            },
        )

    body = client.get("/defects").json()

    assert len(body) == 3