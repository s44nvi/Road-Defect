"""
Status history: every status change must create a `defect_status_history`
row carrying old_status, new_status, changed_by, changed_at, and note.
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


def test_reporting_a_defect_seeds_its_history_with_one_entry(client):
    defect_id = _create_defect(client)

    history = client.get(f"/defects/{defect_id}/status-history").json()

    assert len(history) == 1
    assert history[0]["old_status"] is None
    assert history[0]["new_status"] == "reported"
    assert history[0]["changed_at"] is not None


def test_every_successful_status_change_appends_a_history_row(client):
    defect_id = _create_defect(client)

    client.patch(
        f"/defects/{defect_id}/status",
        json={"status": "confirmed", "note": "confirmed on site"},
    )

    history = client.get(f"/defects/{defect_id}/status-history").json()

    assert len(history) == 2
    assert [entry["new_status"] for entry in history] == ["reported", "confirmed"]


def test_history_entry_records_old_and_new_status(client):
    defect_id = _create_defect(client)

    client.patch(f"/defects/{defect_id}/status", json={"status": "confirmed"})

    history = client.get(f"/defects/{defect_id}/status-history").json()
    last = history[-1]

    assert last["old_status"] == "reported"
    assert last["new_status"] == "confirmed"


def test_history_entry_records_the_note(client):
    defect_id = _create_defect(client)

    client.patch(
        f"/defects/{defect_id}/status",
        json={"status": "confirmed", "note": "Verified by municipal officer"},
    )

    history = client.get(f"/defects/{defect_id}/status-history").json()

    assert history[-1]["note"] == "Verified by municipal officer"


def test_history_entry_records_changed_by_from_request_body(client):
    defect_id = _create_defect(client)

    client.patch(
        f"/defects/{defect_id}/status",
        json={"status": "confirmed", "changedBy": "officer_priya"},
    )

    history = client.get(f"/defects/{defect_id}/status-history").json()

    assert history[-1]["changed_by"] == "officer_priya"


def test_history_entry_records_changed_by_from_header_when_body_omits_it(client):
    defect_id = _create_defect(client)

    client.patch(
        f"/defects/{defect_id}/status",
        json={"status": "confirmed"},
        headers={"X-Officer-Id": "officer_rahul"},
    )

    history = client.get(f"/defects/{defect_id}/status-history").json()

    assert history[-1]["changed_by"] == "officer_rahul"


def test_changed_by_is_nullable_when_no_identity_is_supplied(client):
    """
    This project has no authentication layer, so changed_by must be able to
    stay NULL rather than the request being rejected or a fake identity being
    invented.
    """
    defect_id = _create_defect(client)

    response = client.patch(f"/defects/{defect_id}/status", json={"status": "confirmed"})
    assert response.status_code == 200

    history = client.get(f"/defects/{defect_id}/status-history").json()

    assert history[-1]["changed_by"] is None


def test_a_rejected_status_change_does_not_create_a_history_row(client):
    defect_id = _create_defect(client)

    before = client.get(f"/defects/{defect_id}/status-history").json()

    response = client.patch(f"/defects/{defect_id}/status", json={"status": "not_a_real_status"})
    assert response.status_code == 422

    after = client.get(f"/defects/{defect_id}/status-history").json()

    assert len(after) == len(before)


def test_history_is_ordered_oldest_first(client):
    defect_id = _create_defect(client)

    client.patch(f"/defects/{defect_id}/status", json={"status": "confirmed"})
    client.patch(f"/defects/{defect_id}/status", json={"status": "confirmed"})
    client.patch(f"/defects/{defect_id}/status", json={"status": "in_progress"})

    history = client.get(f"/defects/{defect_id}/status-history").json()
    timestamps = [entry["changed_at"] for entry in history]

    assert timestamps == sorted(timestamps)


def test_legacy_patch_endpoint_also_records_history(client):
    defect_id = _create_defect(client)

    client.patch(
        f"/defects/{defect_id}",
        json={"defect_status": "confirmed", "note": "Verified by municipal officer"},
    )

    history = client.get(f"/defects/{defect_id}/status-history").json()

    assert len(history) == 2
    assert history[-1]["new_status"] == "confirmed"
    assert history[-1]["note"] == "Verified by municipal officer"


def test_status_history_for_unknown_defect_returns_404(client):
    response = client.get("/defects/999999/status-history")

    assert response.status_code == 404
