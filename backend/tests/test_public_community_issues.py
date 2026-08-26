"""
Tests for the citizen-facing community map:

    GET /community/issues

Requirement: citizens may see other users' reports on the map only once an
officer has confirmed them. `reported` (not yet reviewed) and `rejected`
(dismissed) defects must never appear here. Uses the `client`/`make_defect`
fixtures from conftest.py against a throwaway per-test SQLite database.
"""

from __future__ import annotations


def test_returns_200_unauthenticated(client):
    response = client.get("/community/issues")

    assert response.status_code == 200


def test_reported_defect_is_not_publicly_visible(client, make_defect):
    make_defect(19.00, 72.80, status="reported")

    body = client.get("/community/issues").json()

    assert body == []


def test_rejected_defect_is_not_publicly_visible(client, make_defect):
    make_defect(19.00, 72.80, status="rejected")

    body = client.get("/community/issues").json()

    assert body == []


def test_confirmed_defect_is_publicly_visible(client, make_defect):
    defect = make_defect(19.00, 72.80, severity="high", status="confirmed", defect_type="pothole")

    body = client.get("/community/issues").json()

    assert len(body) == 1
    entry = body[0]
    assert entry["defect_id"] == defect.id
    assert entry["defect_type"] == "pothole"
    assert entry["defect_status"] == "confirmed"
    assert entry["defect_severity"] == "high"
    assert entry["latitude"] == 19.00
    assert entry["longitude"] == 72.80
    assert entry["observation_count"] == 1
    assert entry["defectId"] == defect.id
    assert entry["defectStatus"] == "confirmed"
    assert entry["observationCount"] == 1


def test_in_progress_defect_is_publicly_visible(client, make_defect):
    make_defect(19.00, 72.80, status="in_progress")

    body = client.get("/community/issues").json()

    assert len(body) == 1
    assert body[0]["defect_status"] == "in_progress"


def test_resolved_defect_is_publicly_visible(client, make_defect):
    make_defect(19.00, 72.80, status="resolved")

    body = client.get("/community/issues").json()

    assert len(body) == 1
    assert body[0]["defect_status"] == "resolved"


def test_mixed_statuses_only_expose_public_ones(client, make_defect):
    make_defect(19.00, 72.80, status="reported")
    make_defect(19.01, 72.81, status="confirmed")
    make_defect(19.02, 72.82, status="in_progress")
    make_defect(19.03, 72.83, status="resolved")
    make_defect(19.04, 72.84, status="rejected")

    body = client.get("/community/issues").json()

    statuses = {entry["defect_status"] for entry in body}
    assert statuses == {"confirmed", "in_progress", "resolved"}
    assert len(body) == 3


def test_road_segment_id_is_included_when_assigned(client, make_segment, make_defect):
    segment = make_segment("SEG-A", [[72.80, 19.00], [72.81, 19.00]], length_km=1.0)
    defect = make_defect(19.00, 72.805, status="confirmed", segment=segment)

    body = client.get("/community/issues").json()

    assert body[0]["defect_id"] == defect.id
    assert body[0]["road_segment_id"] == "SEG-A"
    assert body[0]["roadSegmentId"] == "SEG-A"
