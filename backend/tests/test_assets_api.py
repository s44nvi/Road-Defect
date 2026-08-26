"""
test_assets_api.py
===================
Tests for the MCGM infrastructure/context layer:

    GET /assets/manholes
    GET /assets/encroachments
    GET /road-health/segments/{segment_id}/assets

Confirms the architectural separation: manholes/encroachments are readable
context data, never defects, and never change Road Health's health score.
"""

from __future__ import annotations


def _make_manhole(db_session, segment=None, **overrides):
    from backend.app.models import Manhole

    values = dict(
        object_id="M-1",
        road_name="Test Road",
        ward="H/W",
        latitude=19.0700,
        longitude=72.8300,
        status="Public",
        condition="Good",
        road_segment_id=segment.id if segment else None,
    )
    values.update(overrides)

    manhole = Manhole(**values)
    db_session.add(manhole)
    db_session.commit()
    db_session.refresh(manhole)
    return manhole


def _make_encroachment(db_session, segment=None, **overrides):
    from backend.app.models import Encroachment

    values = dict(
        object_id="E-1",
        road_name="Test Road",
        ward="H/W",
        latitude=19.0700,
        longitude=72.8300,
        status="Notice Delivered",
        road_segment_id=segment.id if segment else None,
    )
    values.update(overrides)

    encroachment = Encroachment(**values)
    db_session.add(encroachment)
    db_session.commit()
    db_session.refresh(encroachment)
    return encroachment


def test_list_manholes_returns_all(client, db_session):
    _make_manhole(db_session, object_id="M-1")
    _make_manhole(db_session, object_id="M-2")

    body = client.get("/assets/manholes").json()

    assert len(body) == 2
    assert {m["object_id"] for m in body} == {"M-1", "M-2"}


def test_list_encroachments_returns_all(client, db_session):
    _make_encroachment(db_session, object_id="E-1")
    _make_encroachment(db_session, object_id="E-2")

    body = client.get("/assets/encroachments").json()

    assert len(body) == 2
    assert {e["object_id"] for e in body} == {"E-1", "E-2"}


def test_manholes_filterable_by_segment_id(client, db_session, make_segment):
    segment_a = make_segment("SEG-A", [[72.80, 19.00], [72.81, 19.00]], length_km=1.0)
    segment_b = make_segment("SEG-B", [[72.90, 19.10], [72.91, 19.10]], length_km=1.0)

    _make_manhole(db_session, segment=segment_a, object_id="M-A")
    _make_manhole(db_session, segment=segment_b, object_id="M-B")

    body = client.get("/assets/manholes", params={"segment_id": "SEG-A"}).json()

    assert len(body) == 1
    assert body[0]["object_id"] == "M-A"
    assert body[0]["segment_id"] == "SEG-A"


def test_manholes_filter_unknown_segment_returns_404(client):
    response = client.get("/assets/manholes", params={"segment_id": "DOES-NOT-EXIST"})

    assert response.status_code == 404


def test_segment_assets_endpoint_returns_counts_and_records(client, db_session, make_segment):
    segment = make_segment("SEG-ASSETS", [[72.80, 19.00], [72.81, 19.00]], length_km=1.0)
    _make_manhole(db_session, segment=segment, object_id="M-1")
    _make_manhole(db_session, segment=segment, object_id="M-2")
    _make_encroachment(db_session, segment=segment, object_id="E-1")

    body = client.get("/road-health/segments/SEG-ASSETS/assets").json()

    assert body["segment_id"] == "SEG-ASSETS"
    assert body["manhole_count"] == 2
    assert body["encroachment_count"] == 1
    assert len(body["manholes"]) == 2
    assert len(body["encroachments"]) == 1


def test_segment_assets_endpoint_404_for_unknown_segment(client):
    response = client.get("/road-health/segments/DOES-NOT-EXIST/assets")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Architectural guarantee: manholes/encroachments never touch Road Health.
# ---------------------------------------------------------------------------
def test_manholes_and_encroachments_do_not_affect_road_health_score(
    client, db_session, make_segment, make_defect
):
    segment = make_segment("SEG-HEALTH", [[72.80, 19.00], [72.81, 19.00]], length_km=1.0)

    before = client.get("/road-health/segments/SEG-HEALTH").json()

    _make_manhole(db_session, segment=segment, object_id="M-1")
    _make_manhole(db_session, segment=segment, object_id="M-2")
    _make_encroachment(db_session, segment=segment, object_id="E-1")

    after_context_only = client.get("/road-health/segments/SEG-HEALTH").json()

    assert after_context_only["health_score"] == before["health_score"]
    assert after_context_only["total_issues"] == before["total_issues"] == 0
    assert after_context_only["active_issues"] == 0

    # A real defect DOES change health -- confirms the health inputs are
    # exactly what's expected, not that scoring is broken/inert.
    make_defect(19.005, 72.805, severity="critical", status="reported", segment=segment)
    after_defect = client.get("/road-health/segments/SEG-HEALTH").json()

    assert after_defect["total_issues"] == 1
    assert after_defect["health_score"] < before["health_score"]


def test_manholes_do_not_appear_in_defects_or_community_issues(client, db_session, make_segment):
    segment = make_segment("SEG-NO-LEAK", [[72.80, 19.00], [72.81, 19.00]], length_km=1.0)
    _make_manhole(db_session, segment=segment, object_id="M-LEAK-CHECK")
    _make_encroachment(db_session, segment=segment, object_id="E-LEAK-CHECK")

    assert client.get("/defects").json() == []
    assert client.get("/community/issues").json() == []
