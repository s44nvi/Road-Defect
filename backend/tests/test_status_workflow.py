"""
Defect status workflow: valid transitions, rejection of invalid/arbitrary
statuses, and backwards compatibility of the pre-existing
`PATCH /defects/{id}` Confirm/Reject behaviour.
"""

from __future__ import annotations

import pytest


def _create_defect(client, severity="medium", status_check=True):
    response = client.post(
        "/reports",
        json={
            "defect_type": "pothole",
            "defect_severity": severity,
            "latitude": 19.0,
            "longitude": 72.81,
        },
    )

    if status_check:
        assert response.status_code == 200

    return response.json()["defect_id"]


# ---------------------------------------------------------------------------
# PATCH /defects/{id}/status -- the new, strictly validated workflow endpoint
# ---------------------------------------------------------------------------
def test_new_report_starts_in_reported_status(client):
    defect_id = _create_defect(client)

    response = client.get("/defects").json()
    defect = next(d for d in response if d["defect_id"] == defect_id)

    assert defect["defect_status"] == "reported"


@pytest.mark.parametrize(
    "path",
    [
        ["under_review", "confirmed", "assigned", "repair_in_progress", "resolved"],
        ["under_review", "rejected"],
        ["rejected"],
    ],
)
def test_the_full_normal_workflow_path_is_accepted(client, path):
    defect_id = _create_defect(client)

    for status in path:
        response = client.patch(
            f"/defects/{defect_id}/status",
            json={"status": status, "note": f"moving to {status}"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["defect_status"] == status


@pytest.mark.parametrize(
    "bad_status",
    ["done", "DELETED", "in_progress", "", "reported; DROP TABLE defects"],
)
def test_arbitrary_or_unknown_status_strings_are_rejected(client, bad_status):
    defect_id = _create_defect(client)

    response = client.patch(
        f"/defects/{defect_id}/status",
        json={"status": bad_status},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "illegal_target",
    ["assigned", "repair_in_progress", "resolved"],
)
def test_skipping_ahead_in_the_workflow_is_rejected(client, illegal_target):
    """A freshly reported defect cannot jump straight to a later stage."""
    defect_id = _create_defect(client)

    response = client.patch(
        f"/defects/{defect_id}/status",
        json={"status": illegal_target},
    )

    assert response.status_code == 409


def test_resolved_is_a_terminal_status(client):
    defect_id = _create_defect(client)

    for status in ["under_review", "confirmed", "assigned", "repair_in_progress", "resolved"]:
        assert client.patch(f"/defects/{defect_id}/status", json={"status": status}).status_code == 200

    response = client.patch(f"/defects/{defect_id}/status", json={"status": "under_review"})

    assert response.status_code == 409


def test_rejected_is_a_terminal_status(client):
    defect_id = _create_defect(client)

    assert client.patch(f"/defects/{defect_id}/status", json={"status": "rejected"}).status_code == 200

    response = client.patch(f"/defects/{defect_id}/status", json={"status": "under_review"})

    assert response.status_code == 409


def test_status_update_on_unknown_defect_returns_404(client):
    response = client.patch("/defects/999999/status", json={"status": "confirmed"})

    assert response.status_code == 404


def test_setting_the_same_status_again_is_an_idempotent_no_op(client):
    defect_id = _create_defect(client)

    first = client.patch(f"/defects/{defect_id}/status", json={"status": "under_review"})
    second = client.patch(f"/defects/{defect_id}/status", json={"status": "under_review"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["defect_status"] == "under_review"


# ---------------------------------------------------------------------------
# PATCH /defects/{id} -- the pre-existing endpoint, Confirm/Reject compatibility
# ---------------------------------------------------------------------------
def test_legacy_patch_still_returns_the_original_response_shape(client):
    defect_id = _create_defect(client)

    response = client.patch(f"/defects/{defect_id}", json={"defect_status": "under_review"})

    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == {
        "defect_id",
        "defect_type",
        "defect_status",
        "defect_severity",
        "latitude",
        "longitude",
    }
    assert body["defect_status"] == "under_review"


def test_legacy_confirm_button_one_step_reported_to_confirmed_still_works(client):
    """
    The existing officer UI's Confirm button calls this endpoint to move a
    freshly reported defect straight to 'confirmed'. That one-step transition
    is not in the strict workflow graph, but the legacy endpoint must keep
    allowing it.
    """
    defect_id = _create_defect(client)

    response = client.patch(f"/defects/{defect_id}", json={"defect_status": "confirmed"})

    assert response.status_code == 200
    assert response.json()["defect_status"] == "confirmed"


def test_legacy_reject_button_still_works(client):
    defect_id = _create_defect(client)

    response = client.patch(f"/defects/{defect_id}", json={"defect_status": "rejected"})

    assert response.status_code == 200
    assert response.json()["defect_status"] == "rejected"


def test_legacy_endpoint_still_rejects_unknown_statuses(client):
    defect_id = _create_defect(client)

    response = client.patch(f"/defects/{defect_id}", json={"defect_status": "banana"})

    assert response.status_code == 422


def test_legacy_endpoint_still_enforces_illegal_transitions(client):
    """
    The legacy endpoint gets one extra allowance (reported -> confirmed) but
    is not a free-for-all: a defect already resolved cannot be bounced back.
    """
    defect_id = _create_defect(client)

    for status in ["under_review", "confirmed", "assigned", "repair_in_progress", "resolved"]:
        assert client.patch(f"/defects/{defect_id}/status", json={"status": status}).status_code == 200

    response = client.patch(f"/defects/{defect_id}", json={"defect_status": "under_review"})

    assert response.status_code == 409


def test_legacy_endpoint_on_unknown_defect_returns_404(client):
    response = client.patch("/defects/999999", json={"defect_status": "confirmed"})

    assert response.status_code == 404
