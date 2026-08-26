"""
API-level tests for the Road Health endpoints:

    GET /road-health/segments
    GET /road-health/segments/{segment_id}

Uses the `client`/`make_segment`/`make_defect` fixtures from conftest.py, which
run against a throwaway per-test SQLite database -- no migrations, no seed
script, no real database is touched.
"""

from __future__ import annotations


SIMPLE_LINE = [[72.80, 19.00], [72.81, 19.00], [72.82, 19.00]]


def test_segments_endpoint_returns_200(client):
    response = client.get("/road-health/segments")

    assert response.status_code == 200


def test_segments_endpoint_returns_a_valid_feature_collection(client, make_segment):
    make_segment("SEG-A", SIMPLE_LINE, length_km=2.0, road_name="Test Road A")
    make_segment("SEG-B", SIMPLE_LINE, length_km=2.0, road_name="Test Road B")

    body = client.get("/road-health/segments").json()

    assert body["type"] == "FeatureCollection"
    assert isinstance(body["features"], list)
    assert len(body["features"]) == 2


def test_every_feature_has_linestring_geometry(client, make_segment):
    make_segment("SEG-A", SIMPLE_LINE, length_km=2.0)

    body = client.get("/road-health/segments").json()
    feature = body["features"][0]

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "LineString"
    assert feature["geometry"]["coordinates"] == SIMPLE_LINE


REQUIRED_HEALTH_PROPERTIES = {
    "segment_id",
    "road_name",
    "length_km",
    "health_score",
    "health_status",
    "total_issues",
    "active_issues",
    "resolved_issues",
    "critical_issues",
    "medium_issues",
    "low_issues",
    # camelCase mirror for the existing officer frontend contract
    "segmentId",
    "roadName",
    "healthScore",
    "totalIssues",
    "activeIssues",
    "resolvedIssues",
    "criticalCount",
    "mediumCount",
    "lowCount",
}


def test_every_feature_has_the_required_health_properties(client, make_segment, make_defect):
    segment = make_segment("SEG-A", SIMPLE_LINE, length_km=2.0, road_name="Test Road A")
    make_defect(19.00, 72.805, severity="critical", status="reported", segment=segment)

    body = client.get("/road-health/segments").json()
    properties = body["features"][0]["properties"]

    missing = REQUIRED_HEALTH_PROPERTIES - properties.keys()
    assert not missing, f"missing properties: {missing}"

    assert properties["segment_id"] == "SEG-A"
    assert properties["total_issues"] == 1
    assert properties["active_issues"] == 1
    assert properties["critical_issues"] == 1


def test_segment_detail_returns_required_information(client, make_segment):
    make_segment("SEG-A", SIMPLE_LINE, length_km=2.0, road_name="Test Road A")

    body = client.get("/road-health/segments/SEG-A").json()

    for field in [
        "segment_id",
        "road_name",
        "geometry",
        "length_km",
        "health_score",
        "health_status",
        "total_issues",
        "active_issues",
        "resolved_issues",
        "critical_issues",
        "medium_issues",
        "low_issues",
        "defects",
    ]:
        assert field in body, f"missing field: {field}"

    assert body["geometry"]["type"] == "LineString"
    assert body["segment_id"] == "SEG-A"


def test_segment_detail_includes_associated_defects(client, make_segment, make_defect):
    segment = make_segment("SEG-A", SIMPLE_LINE, length_km=2.0)
    other_segment = make_segment("SEG-B", SIMPLE_LINE, length_km=2.0)

    on_segment = make_defect(19.00, 72.805, severity="medium", status="reported", segment=segment)
    make_defect(19.00, 72.815, severity="low", status="reported", segment=other_segment)

    body = client.get("/road-health/segments/SEG-A").json()

    assert len(body["defects"]) == 1
    assert body["defects"][0]["defect_id"] == on_segment.id


def test_segment_detail_returns_404_for_unknown_segment(client):
    response = client.get("/road-health/segments/DOES-NOT-EXIST")

    assert response.status_code == 404


def test_segment_detail_404_does_not_leak_internals(client):
    body = client.get("/road-health/segments/NOPE").json()

    assert "detail" in body
    assert "traceback" not in str(body).lower()
