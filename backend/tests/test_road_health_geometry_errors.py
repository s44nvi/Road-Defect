"""
Tests for malformed-geometry handling in Road Health.

Covers the fix that normalizes bare `ValueError`/`TypeError` from
non-numeric coordinates into `InvalidGeometryError` (`geo.parse_linestring`),
and the fix that keeps a single malformed segment from crashing either the
`GET /road-health/segments` list endpoint or the
`GET /road-health/segments/{segment_id}` detail endpoint.
"""

from __future__ import annotations

import pytest

from backend.app.road_health.geo import InvalidGeometryError, parse_linestring

SIMPLE_LINE = [[72.80, 19.00], [72.81, 19.00], [72.82, 19.00]]


def _bad_geometry(bad_point):
    return {"type": "LineString", "coordinates": [[72.80, 19.00], bad_point]}


def test_parse_linestring_raises_invalid_geometry_error_for_non_numeric_longitude():
    with pytest.raises(InvalidGeometryError):
        parse_linestring(_bad_geometry(["not-a-number", 19.01]))


def test_parse_linestring_raises_invalid_geometry_error_for_non_numeric_latitude():
    with pytest.raises(InvalidGeometryError):
        parse_linestring(_bad_geometry([72.81, "not-a-number"]))


def test_parse_linestring_does_not_leak_bare_value_or_type_error():
    """The normalized error must be catchable purely as InvalidGeometryError
    by callers that only expect that type (e.g. build_feature_collection)."""
    try:
        parse_linestring(_bad_geometry([None, 19.01]))
    except InvalidGeometryError:
        pass
    except (ValueError, TypeError) as exc:
        pytest.fail(f"leaked a bare {type(exc).__name__} instead of InvalidGeometryError")
    else:
        pytest.fail("expected InvalidGeometryError to be raised")


def test_valid_linestring_still_parses_normally():
    """Fix 1 must not change behavior for well-formed input."""
    parsed = parse_linestring({"type": "LineString", "coordinates": SIMPLE_LINE})
    assert parsed == [[72.80, 19.00], [72.81, 19.00], [72.82, 19.00]]


def test_malformed_segment_is_skipped_not_fatal_in_list_endpoint(client, make_segment, db_session):
    make_segment("SEG-GOOD", SIMPLE_LINE, length_km=2.0, road_name="Good Road")
    bad = make_segment("SEG-BAD", SIMPLE_LINE, length_km=2.0, road_name="Bad Road")

    # Corrupt the stored geometry directly, bypassing the factory's own
    # validation, to simulate a genuinely malformed row already in the DB.
    bad.geometry = _bad_geometry(["not-a-number", 19.01])
    db_session.add(bad)
    db_session.commit()

    response = client.get("/road-health/segments")

    assert response.status_code == 200
    body = response.json()
    segment_ids = [f["properties"]["segment_id"] for f in body["features"]]

    assert "SEG-GOOD" in segment_ids
    assert "SEG-BAD" not in segment_ids


def test_malformed_segment_detail_returns_controlled_error_not_500(client, make_segment, db_session):
    bad = make_segment("SEG-BAD-DETAIL", SIMPLE_LINE, length_km=2.0, road_name="Bad Detail Road")

    bad.geometry = _bad_geometry(["not-a-number", 19.01])
    db_session.add(bad)
    db_session.commit()

    response = client.get("/road-health/segments/SEG-BAD-DETAIL")

    # Must be a controlled 4xx client error, never an unhandled 500.
    assert response.status_code == 422
    assert "SEG-BAD-DETAIL" in response.json()["detail"]
