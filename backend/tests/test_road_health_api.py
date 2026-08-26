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


def test_segments_endpoint_filters_by_geometry_source(client, make_segment):
    make_segment(
        "SEG-DEV", SIMPLE_LINE, length_km=2.0, road_name="Dev Road",
        geometry_source="dev_approximate_v1",
    )
    make_segment(
        "SEG-MCGM", SIMPLE_LINE, length_km=2.0, road_name="MCGM Road",
        geometry_source="mcgm_demo_csv_v1",
    )

    # No filter: both segments, unchanged from before this param existed.
    unfiltered = client.get("/road-health/segments").json()
    assert len(unfiltered["features"]) == 2

    # Filtered: only the MCGM one, nothing deleted/hidden from the other call.
    filtered = client.get(
        "/road-health/segments", params={"geometry_source": "mcgm_demo_csv_v1"}
    ).json()
    assert len(filtered["features"]) == 1
    assert filtered["features"][0]["properties"]["segment_id"] == "SEG-MCGM"


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


def test_segment_properties_include_status_breakdown(client, make_segment, make_defect):
    segment = make_segment("SEG-A", SIMPLE_LINE, length_km=2.0, road_name="Test Road A")
    make_defect(19.00, 72.805, severity="critical", status="reported", segment=segment)
    make_defect(19.00, 72.806, severity="medium", status="confirmed", segment=segment)
    make_defect(19.00, 72.807, severity="low", status="in_progress", segment=segment)
    make_defect(19.00, 72.808, severity="low", status="resolved", segment=segment)

    body = client.get("/road-health/segments").json()
    properties = body["features"][0]["properties"]

    assert properties["reported_issues"] == 1
    assert properties["confirmed_issues"] == 1
    assert properties["in_progress_issues"] == 1
    assert (
        properties["reported_issues"]
        + properties["confirmed_issues"]
        + properties["in_progress_issues"]
        == properties["active_issues"]
    )
    assert properties["reportedIssues"] == 1
    assert properties["confirmedIssues"] == 1
    assert properties["inProgressIssues"] == 1


def test_segment_detail_includes_status_breakdown(client, make_segment, make_defect):
    segment = make_segment("SEG-A", SIMPLE_LINE, length_km=2.0, road_name="Test Road A")
    make_defect(19.00, 72.805, severity="critical", status="confirmed", segment=segment)

    body = client.get("/road-health/segments/SEG-A").json()

    assert body["confirmed_issues"] == 1
    assert body["reported_issues"] == 0
    assert body["in_progress_issues"] == 0


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
