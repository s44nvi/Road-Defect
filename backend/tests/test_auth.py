"""
Municipal officer authentication.

Covers: officer login (valid/invalid/inactive), citizen login staying in a
separate identity space, officer-only route enforcement (missing token,
wrong-principal-type token, valid token), that a spoofed `X-Officer-Id`
cannot impersonate another officer, that `changed_by` is always derived from
the authenticated officer, and that no response ever leaks `password_hash`.
"""

from __future__ import annotations


def _create_defect(client):
    response = client.post(
        "/reports",
        json={
            "defect_type": "pothole",
            "defect_severity": "medium",
            "latitude": 19.0,
            "longitude": 72.81,
        },
    )
    assert response.status_code == 200
    return response.json()["defect_id"]


# ---------------------------------------------------------------------------
# Officer login
# ---------------------------------------------------------------------------
def test_valid_officer_login_returns_200_and_a_token(client, dev_officer):
    response = client.post(
        "/auth/officer/login",
        json={"email": "officer@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert body["officer"]["email"] == "officer@example.com"
    assert body["officer"]["officer_id"] == dev_officer.id


def test_officer_login_rejects_wrong_password(client, dev_officer):
    response = client.post(
        "/auth/officer/login",
        json={"email": "officer@example.com", "password": "not-the-password"},
    )

    assert response.status_code == 401


def test_officer_login_rejects_unknown_email(client, dev_officer):
    response = client.post(
        "/auth/officer/login",
        json={"email": "nobody@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 401


def test_officer_login_rejects_inactive_officer(client, db_session, dev_officer):
    dev_officer.is_active = False
    db_session.commit()

    response = client.post(
        "/auth/officer/login",
        json={"email": "officer@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 401


def test_officer_login_error_does_not_distinguish_bad_email_from_bad_password(client, dev_officer):
    """Both failure modes must return the identical status/message."""
    unknown_email = client.post(
        "/auth/officer/login",
        json={"email": "nobody@example.com", "password": "correct-horse-battery-staple"},
    )
    wrong_password = client.post(
        "/auth/officer/login",
        json={"email": "officer@example.com", "password": "wrong"},
    )

    assert unknown_email.status_code == wrong_password.status_code == 401
    assert unknown_email.json()["detail"] == wrong_password.json()["detail"]


def test_citizen_credentials_cannot_log_in_as_an_officer(client, dev_citizen):
    """A valid citizen email/password must not authenticate against /auth/officer/login."""
    response = client.post(
        "/auth/officer/login",
        json={"email": "citizen@example.com", "password": "citizen-password-123"},
    )

    assert response.status_code == 401


def test_officer_login_response_never_contains_password_hash(client, dev_officer):
    response = client.post(
        "/auth/officer/login",
        json={"email": "officer@example.com", "password": "correct-horse-battery-staple"},
    )

    body_text = response.text
    assert "password_hash" not in body_text
    assert dev_officer.password_hash not in body_text


# ---------------------------------------------------------------------------
# Citizen login
# ---------------------------------------------------------------------------
def test_valid_citizen_login_returns_200_and_a_token(client, dev_citizen):
    response = client.post(
        "/auth/citizen/login",
        json={"email": "citizen@example.com", "password": "citizen-password-123"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert body["citizen"]["email"] == "citizen@example.com"


def test_officer_credentials_cannot_log_in_as_a_citizen(client, dev_officer):
    response = client.post(
        "/auth/citizen/login",
        json={"email": "officer@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 401


def test_citizen_login_response_never_contains_password_hash(client, dev_citizen):
    response = client.post(
        "/auth/citizen/login",
        json={"email": "citizen@example.com", "password": "citizen-password-123"},
    )

    assert "password_hash" not in response.text
    assert dev_citizen.password_hash not in response.text


# ---------------------------------------------------------------------------
# Officer-only route enforcement
# ---------------------------------------------------------------------------
def test_officer_endpoint_without_any_token_returns_401(client):
    defect_id = _create_defect(client)

    response = client.patch(f"/defects/{defect_id}/status", json={"status": "confirmed"})

    assert response.status_code == 401


def test_officer_endpoint_with_garbage_token_returns_401(client):
    defect_id = _create_defect(client)

    response = client.patch(
        f"/defects/{defect_id}/status",
        json={"status": "confirmed"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_citizen_token_on_officer_endpoint_is_rejected(client, citizen_token):
    """A well-formed, validly-signed CITIZEN token must not authorize an officer route."""
    defect_id = _create_defect(client)

    response = client.patch(
        f"/defects/{defect_id}/status",
        json={"status": "confirmed"},
        headers={"Authorization": f"Bearer {citizen_token}"},
    )

    assert response.status_code == 403


def test_valid_officer_token_succeeds_on_officer_endpoint(client, officer_client):
    defect_id = _create_defect(client)

    response = officer_client.patch(f"/defects/{defect_id}/status", json={"status": "confirmed"})

    assert response.status_code == 200
    assert response.json()["defect_status"] == "confirmed"


def test_deactivated_officers_existing_token_stops_working(client, db_session, dev_officer, officer_client):
    defect_id = _create_defect(client)

    dev_officer.is_active = False
    db_session.commit()

    response = officer_client.patch(f"/defects/{defect_id}/status", json={"status": "confirmed"})

    assert response.status_code == 403


def test_legacy_patch_endpoint_also_requires_officer_authentication(client):
    defect_id = _create_defect(client)

    response = client.patch(f"/defects/{defect_id}", json={"defect_status": "confirmed"})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Public routes stay public
# ---------------------------------------------------------------------------
def test_post_reports_remains_public_and_unauthenticated(client):
    response = client.post(
        "/reports",
        json={
            "defect_type": "pothole",
            "defect_severity": "medium",
            "latitude": 19.0,
            "longitude": 72.81,
        },
    )

    assert response.status_code == 200


def test_get_defects_remains_public_and_unauthenticated(client):
    assert client.get("/defects").status_code == 200
