"""
Covers: PATCH /defects/{defect_id}/severity -- officer-only defect severity
update. Auth behavior mirrors PATCH /defects/{defect_id}/status (401/403/404),
severity values are validated and normalized, and only `defect_severity` is
ever changed.
"""

from __future__ import annotations


def _create_defect(client):
    response = client.post(
        "/reports",
        json={
            "defect_type": "pothole",
            "defect_severity": "medium",
            "latitude": 19.076,
            "longitude": 72.877,
        },
    )
    assert response.status_code == 200
    return response.json()["defect_id"]


def test_unauthenticated_request_is_rejected(client):
    defect_id = _create_defect(client)

    response = client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "high"},
    )

    assert response.status_code == 401


def test_garbage_token_is_rejected(client):
    defect_id = _create_defect(client)

    response = client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "high"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_citizen_token_on_officer_endpoint_is_rejected(client, citizen_token):
    defect_id = _create_defect(client)

    response = client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "high"},
        headers={"Authorization": f"Bearer {citizen_token}"},
    )

    assert response.status_code == 403


def test_inactive_officer_token_is_rejected(client, db_session, dev_officer, officer_client):
    defect_id = _create_defect(client)

    dev_officer.is_active = False
    db_session.commit()

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "high"},
    )

    assert response.status_code == 403


def test_nonexistent_defect_returns_404(officer_client):
    response = officer_client.patch(
        "/defects/999999/severity",
        json={"defect_severity": "high"},
    )

    assert response.status_code == 404


def test_invalid_severity_returns_422(officer_client):
    defect_id = _create_defect(officer_client)

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "catastrophic"},
    )

    assert response.status_code == 422


def test_officer_can_change_medium_to_critical(officer_client):
    defect_id = _create_defect(officer_client)

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "critical"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["defect_severity"] == "critical"
    assert body["defectSeverity"] == "critical"


def test_officer_can_change_to_low(officer_client):
    defect_id = _create_defect(officer_client)

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "low"},
    )

    assert response.status_code == 200
    assert response.json()["defect_severity"] == "low"


def test_officer_can_change_to_medium(officer_client):
    defect_id = _create_defect(officer_client)

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "medium"},
    )

    assert response.status_code == 200
    assert response.json()["defect_severity"] == "medium"


def test_officer_can_change_to_high(officer_client):
    defect_id = _create_defect(officer_client)

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "high"},
    )

    assert response.status_code == 200
    assert response.json()["defect_severity"] == "high"


def test_officer_can_change_to_critical(officer_client):
    defect_id = _create_defect(officer_client)

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "critical"},
    )

    assert response.status_code == 200
    assert response.json()["defect_severity"] == "critical"


def test_whitespace_and_case_are_normalized(officer_client):
    defect_id = _create_defect(officer_client)

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": " CRITICAL "},
    )

    assert response.status_code == 200
    assert response.json()["defect_severity"] == "critical"


def test_changing_severity_does_not_change_status(officer_client):
    defect_id = _create_defect(officer_client)

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "high"},
    )

    assert response.status_code == 200
    assert response.json()["defect_status"] == "reported"


def test_changing_severity_does_not_modify_unrelated_fields(officer_client):
    defect_id = _create_defect(officer_client)
    before = officer_client.get(f"/defects/{defect_id}").json()

    response = officer_client.patch(
        f"/defects/{defect_id}/severity",
        json={"defect_severity": "high"},
    )

    assert response.status_code == 200
    after = response.json()

    for key in ("defect_id", "defect_type", "defect_status", "latitude", "longitude", "road_segment_id"):
        assert after[key] == before[key]
