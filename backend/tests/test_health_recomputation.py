"""
Road health recomputation: since health is always computed on read (never
stored), changing a defect's status or severity must be reflected immediately
on the next `GET /road-health/segments*` call -- there is no cache to
invalidate, but this proves the read path actually behaves that way.
"""

from __future__ import annotations

LINE = [[72.80, 19.00], [72.81, 19.00], [72.82, 19.00]]


def _segment_properties(client, segment_id):
    body = client.get("/road-health/segments").json()
    return next(f["properties"] for f in body["features"] if f["properties"]["segment_id"] == segment_id)


def test_an_active_defect_degrades_the_segments_health(client, make_segment, make_defect):
    segment = make_segment("SEG-A", LINE, length_km=2.0)

    before = _segment_properties(client, "SEG-A")
    assert before["health_score"] == 10.0
    assert before["health_status"] == "healthy"

    make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)

    after = _segment_properties(client, "SEG-A")

    assert after["health_score"] < before["health_score"]
    assert after["active_issues"] == 1


def test_resolving_a_defect_through_the_api_improves_the_segments_health(
    client, make_segment, make_defect
):
    segment = make_segment("SEG-A", LINE, length_km=2.0)
    defect = make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)

    degraded = _segment_properties(client, "SEG-A")
    assert degraded["active_issues"] == 1
    assert degraded["resolved_issues"] == 0

    # Walk the real workflow to 'resolved' rather than writing the status
    # directly, so this exercises the same path an officer would use.
    for status in ["under_review", "confirmed", "assigned", "repair_in_progress", "resolved"]:
        response = client.patch(f"/defects/{defect.id}/status", json={"status": status})
        assert response.status_code == 200

    recovered = _segment_properties(client, "SEG-A")

    assert recovered["active_issues"] == 0
    assert recovered["resolved_issues"] == 1
    assert recovered["total_issues"] == degraded["total_issues"]
    assert recovered["health_score"] > degraded["health_score"]
    assert recovered["health_score"] == 10.0


def test_rejecting_a_defect_also_removes_it_from_active_degradation(
    client, make_segment, make_defect
):
    segment = make_segment("SEG-A", LINE, length_km=2.0)
    defect = make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)

    assert client.patch(f"/defects/{defect.id}/status", json={"status": "rejected"}).status_code == 200

    result = _segment_properties(client, "SEG-A")

    assert result["active_issues"] == 0
    assert result["rejected_issues"] == 1
    assert result["health_score"] == 10.0


def test_severity_weights_are_applied_correctly(client, make_segment, make_defect):
    """Critical (3) must degrade health more than medium (2) or low (1)."""
    critical_segment = make_segment("SEG-CRIT", LINE, length_km=5.0, road_name="Critical Road")
    medium_segment = make_segment("SEG-MED", LINE, length_km=5.0, road_name="Medium Road")
    low_segment = make_segment("SEG-LOW", LINE, length_km=5.0, road_name="Low Road")

    make_defect(19.0, 72.805, severity="critical", status="reported", segment=critical_segment)
    make_defect(19.0, 72.805, severity="medium", status="reported", segment=medium_segment)
    make_defect(19.0, 72.805, severity="low", status="reported", segment=low_segment)

    body = client.get("/road-health/segments").json()
    scores = {f["properties"]["segment_id"]: f["properties"]["health_score"] for f in body["features"]}

    assert scores["SEG-CRIT"] < scores["SEG-MED"] < scores["SEG-LOW"]


def test_a_high_severity_defect_counts_as_critical_in_the_response(
    client, make_segment, make_defect
):
    segment = make_segment("SEG-A", LINE, length_km=5.0)
    make_defect(19.0, 72.805, severity="high", status="reported", segment=segment)

    result = _segment_properties(client, "SEG-A")

    assert result["critical_issues"] == 1
    assert result["medium_issues"] == 0
    assert result["low_issues"] == 0


def test_multiple_active_defects_accumulate_load(client, make_segment, make_defect):
    segment = make_segment("SEG-A", LINE, length_km=5.0)

    make_defect(19.0, 72.805, severity="low", status="reported", segment=segment)
    one = _segment_properties(client, "SEG-A")

    make_defect(19.0, 72.805, severity="low", status="reported", segment=segment)
    two = _segment_properties(client, "SEG-A")

    assert two["active_issues"] == 2
    assert two["health_score"] <= one["health_score"]
