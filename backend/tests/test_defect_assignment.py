"""
Defect -> road segment assignment.

Covers both the pure assignment logic (`find_nearest_segment`) and the
end-to-end path through `POST /reports`, which calls
`road_health_service.assign_defect_to_segment` on every new report.
"""

from __future__ import annotations

from backend.app.road_health.assignment import SegmentGeometry, find_nearest_segment
from backend.app.road_health.config import MAX_SNAP_DISTANCE_KM
# A short east-west line at latitude 19.00, from lon 72.80 to 72.82 (~2.1 km).
LINE_A = [[72.80, 19.00], [72.81, 19.00], [72.82, 19.00]]

# A parallel line ~1 km further north, so a point can be unambiguously closer
# to one or the other.
LINE_B = [[72.80, 19.009], [72.81, 19.009], [72.82, 19.009]]


def test_a_defect_is_assigned_to_the_nearest_of_several_segments():
    segments = [
        SegmentGeometry(id=1, segment_id="SEG-A", geometry={"type": "LineString", "coordinates": LINE_A}),
        SegmentGeometry(id=2, segment_id="SEG-B", geometry={"type": "LineString", "coordinates": LINE_B}),
    ]

    # A point just north of LINE_A (much closer to A than to B).
    result = find_nearest_segment(19.0005, 72.81, segments)

    assert result.assigned
    assert result.segment_id == "SEG-A"
    assert result.segment_pk == 1


def test_a_defect_closer_to_the_second_segment_is_assigned_there():
    segments = [
        SegmentGeometry(id=1, segment_id="SEG-A", geometry={"type": "LineString", "coordinates": LINE_A}),
        SegmentGeometry(id=2, segment_id="SEG-B", geometry={"type": "LineString", "coordinates": LINE_B}),
    ]

    result = find_nearest_segment(19.0085, 72.81, segments)

    assert result.segment_id == "SEG-B"


def test_a_defect_beyond_the_snap_tolerance_is_left_unassigned():
    segments = [
        SegmentGeometry(id=1, segment_id="SEG-A", geometry={"type": "LineString", "coordinates": LINE_A}),
    ]

    # ~1 km north of LINE_A, far beyond the default 150 m tolerance.
    far_lat = 19.00 + (1.0 / 111.0)

    result = find_nearest_segment(far_lat, 72.81, segments)

    assert not result.assigned
    assert result.segment_pk is None
    assert result.segment_id is None


def test_a_defect_just_inside_the_tolerance_is_assigned():
    segments = [
        SegmentGeometry(id=1, segment_id="SEG-A", geometry={"type": "LineString", "coordinates": LINE_A}),
    ]

    # Offset chosen so the perpendicular distance is comfortably inside
    # MAX_SNAP_DISTANCE_KM (0.15 km by default).
    close_lat = 19.00 + (0.05 / 111.0)

    result = find_nearest_segment(close_lat, 72.81, segments)

    assert result.assigned
    assert result.distance_km < MAX_SNAP_DISTANCE_KM


def test_a_defect_just_outside_the_tolerance_is_unassigned():
    segments = [
        SegmentGeometry(id=1, segment_id="SEG-A", geometry={"type": "LineString", "coordinates": LINE_A}),
    ]

    # Offset chosen so the perpendicular distance is just past the 150 m
    # tolerance.
    far_lat = 19.00 + (0.2 / 111.0)

    result = find_nearest_segment(far_lat, 72.81, segments)

    assert not result.assigned


def test_ties_break_on_ascending_segment_id():
    # Two identical lines at the same location: distance is a tie, so the
    # lexicographically-smaller segment_id must win regardless of row order.
    segments = [
        SegmentGeometry(id=2, segment_id="SEG-Z", geometry={"type": "LineString", "coordinates": LINE_A}),
        SegmentGeometry(id=1, segment_id="SEG-A", geometry={"type": "LineString", "coordinates": LINE_A}),
    ]

    result = find_nearest_segment(19.0, 72.81, segments)

    assert result.segment_id == "SEG-A"


# ---------------------------------------------------------------------------
# End-to-end via POST /reports
# ---------------------------------------------------------------------------
def test_a_new_report_is_snapped_to_its_segment_via_the_api(client, make_segment):
    make_segment("SEG-A", LINE_A, length_km=2.0, road_name="Test Road A")

    response = client.post(
        "/reports",
        json={
            "defect_type": "pothole",
            "defect_severity": "medium",
            "latitude": 19.0005,
            "longitude": 72.81,
        },
    )

    assert response.status_code == 200
    defect_id = response.json()["defect_id"]

    detail = client.get("/road-health/segments/SEG-A").json()
    assert any(d["defect_id"] == defect_id for d in detail["defects"])


def test_a_report_far_from_any_segment_is_not_forced_onto_one(client, make_segment):
    make_segment("SEG-A", LINE_A, length_km=2.0, road_name="Test Road A")

    response = client.post(
        "/reports",
        json={
            "defect_type": "pothole",
            "defect_severity": "medium",
            "latitude": 25.0,  # far from Mumbai/LINE_A
            "longitude": 80.0,
        },
    )

    assert response.status_code == 200

    detail = client.get("/road-health/segments/SEG-A").json()
    assert detail["total_issues"] == 0


def test_a_report_is_accepted_even_when_no_segments_exist(client):
    """POST /reports must not fail just because road_segments is empty."""
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
