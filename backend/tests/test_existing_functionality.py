"""
Regression tests for pre-existing endpoints that must keep working exactly as
before: GET /defects, POST /reports, and the general health check. These
guard against the Road Health feature accidentally changing existing
behaviour.

`defect_priority` was added deliberately (not a regression) so GET /defects
and POST /reports expose the AHP priority score persisted by the pothole
image pipeline (POST /reports/image); it is always null for JSON-only
reports, which have no detection to score. See test_pothole_integration_boundary.py.
"""

from __future__ import annotations


def test_health_check_still_works(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_reports_still_returns_the_original_response_shape(client):
    response = client.post(
        "/reports",
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
    client.post(
        "/reports",
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
    assert set(body[0].keys()) == {
        "defect_id",
        "defect_type",
        "defect_status",
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
    for i in range(3):
        client.post(
            "/reports",
            json={
                "defect_type": "crack",
                "defect_severity": "low",
                "latitude": 19.0 + i * 0.01,
                "longitude": 72.8,
            },
        )

    body = client.get("/defects").json()

    assert len(body) == 3
