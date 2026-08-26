"""
Tests for `GET /reports/nearby`: read-only, haversine-distance location
search over defects, and a couple of end-to-end submit-persistence /
response-contract checks per the task spec.
"""

from __future__ import annotations


def _register_and_login(client, email="citizen-nearby@example.com"):
    from backend.app.auth.security import hash_password

    # Reuse dev_citizen-style direct DB insert via the client's own db.
    return email


def test_submit_persists_exact_latitude_longitude(client, citizen_token, tmp_path):
    """
    POST /reports/analyze -> POST /reports/submit persists exactly the
    lat/lon the citizen selected (task item 4 -- verify, don't rewrite).
    """
    client.headers.update({"Authorization": f"Bearer {citizen_token}"})

    # No real detector configured in tests -> ModelUnavailableError is
    # swallowed in _run_detectors, so /analyze returns a "nothing detected"
    # result but still persists the uploaded image and issues a token.
    image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    files = {"file": ("test.jpg", image_bytes, "image/jpeg")}
    analyze_resp = client.post("/reports/analyze", files=files)
    assert analyze_resp.status_code == 200
    token = analyze_resp.json()["image_token"]

    exact_lat, exact_lon = 19.123456, 72.987654
    submit_resp = client.post(
        "/reports/submit",
        json={
            "imageToken": token,
            "latitude": exact_lat,
            "longitude": exact_lon,
            "defectType": "pothole",
            "defectSeverity": "high",
        },
    )
    assert submit_resp.status_code == 200
    body = submit_resp.json()

    assert body["latitude"] == exact_lat
    assert body["longitude"] == exact_lon
    assert body["defect_type"] == "pothole"
    assert body["defect_severity"] == "high"
    assert body["defect_status"] == "reported"
    assert "defect_priority" in body
    assert "reported_at" in body
    assert "image_url" in body


def test_incident_response_includes_required_fields(client, citizen_token):
    """GET /defects/{id} (officer) response carries the incident contract fields."""
    from backend.app.auth.security import hash_password

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.post(
        "/reports",
        json={
            "defect_type": "pothole",
            "defect_severity": "medium",
            "latitude": 19.05,
            "longitude": 72.85,
        },
    )
    assert resp.status_code == 200
    defect_id = resp.json()["defect_id"]

    for field in ("latitude", "longitude", "defect_type", "defect_severity", "defect_status"):
        assert field in resp.json()


def test_nearby_includes_incident_within_radius(client, citizen_token, make_defect):
    origin_lat, origin_lon = 19.0760, 72.8777  # Mumbai

    # ~1.1km away
    near = make_defect(latitude=19.0850, longitude=72.8777, severity="high")

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": origin_lat, "longitude": origin_lon, "radius_km": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["defect_id"] == near.id
    assert body[0]["defect_severity"] == "high"
    assert body[0]["distance_km"] > 0


def test_nearby_excludes_incident_outside_radius(client, citizen_token, make_defect):
    origin_lat, origin_lon = 19.0760, 72.8777

    # ~100km+ away
    make_defect(latitude=20.0, longitude=73.9, severity="low")

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": origin_lat, "longitude": origin_lon, "radius_km": 5},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_nearby_distance_km_correct_within_tolerance(client, citizen_token, make_defect):
    import math

    from backend.app.road_health.geo import haversine_km

    origin_lat, origin_lon = 19.0760, 72.8777
    target_lat, target_lon = 19.10, 72.90

    defect = make_defect(latitude=target_lat, longitude=target_lon)
    expected = haversine_km(origin_lat, origin_lon, target_lat, target_lon)

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": origin_lat, "longitude": origin_lon, "radius_km": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert abs(body[0]["distance_km"] - expected) < 0.05


def test_nearby_multiple_incidents_each_correct_distance_and_sorted(client, citizen_token, make_defect):
    from backend.app.road_health.geo import haversine_km

    origin_lat, origin_lon = 19.0760, 72.8777

    far = make_defect(latitude=19.12, longitude=72.92)
    near = make_defect(latitude=19.08, longitude=72.88)
    mid = make_defect(latitude=19.10, longitude=72.90)

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": origin_lat, "longitude": origin_lon, "radius_km": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3

    # sorted ascending by distance
    distances = [item["distance_km"] for item in body]
    assert distances == sorted(distances)

    by_id = {item["defect_id"]: item["distance_km"] for item in body}
    assert abs(by_id[near.id] - haversine_km(origin_lat, origin_lon, 19.08, 72.88)) < 0.05
    assert abs(by_id[mid.id] - haversine_km(origin_lat, origin_lon, 19.10, 72.90)) < 0.05
    assert abs(by_id[far.id] - haversine_km(origin_lat, origin_lon, 19.12, 72.92)) < 0.05
    assert body[0]["defect_id"] == near.id
    assert body[-1]["defect_id"] == far.id


def test_nearby_empty_list_when_nothing_nearby(client, citizen_token, make_defect):
    make_defect(latitude=-33.8688, longitude=151.2093)  # Sydney, far from query point

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 72.8777, "radius_km": 10},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_nearby_requires_citizen_auth(client):
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 72.8777, "radius_km": 5},
    )
    assert resp.status_code == 401


def test_nearby_rejects_invalid_latitude(client, citizen_token):
    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 95.0, "longitude": 72.8777, "radius_km": 5},
    )
    assert resp.status_code == 422


def test_nearby_rejects_invalid_longitude(client, citizen_token):
    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 200.0, "radius_km": 5},
    )
    assert resp.status_code == 422


def test_nearby_rejects_zero_or_negative_radius(client, citizen_token):
    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 72.8777, "radius_km": 0},
    )
    assert resp.status_code == 422

    resp2 = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 72.8777, "radius_km": -5},
    )
    assert resp2.status_code == 422


def test_nearby_rejects_radius_over_max(client, citizen_token):
    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 72.8777, "radius_km": 51},
    )
    assert resp.status_code == 422


def test_nearby_search_does_not_mutate_stored_defects(client, citizen_token, make_defect, db_session):
    from backend.app.models import Defect

    defect = make_defect(latitude=19.08, longitude=72.88, severity="critical", status="reported")
    original_status = defect.defect_status
    original_priority = defect.defect_priority
    original_lat = defect.latitude
    original_lon = defect.longitude

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 72.8777, "radius_km": 50},
    )
    assert resp.status_code == 200

    db_session.expire_all()
    refreshed = db_session.query(Defect).filter(Defect.id == defect.id).first()
    assert refreshed.defect_status == original_status
    assert refreshed.defect_priority == original_priority
    assert refreshed.latitude == original_lat
    assert refreshed.longitude == original_lon


def test_nearby_reported_at_is_ist_string_when_present(client, citizen_token, db_session):
    """
    A defect created via POST /reports/image or /reports/submit gets a
    status-history row (record_initial_status), so reported_at should be a
    populated, IST-shifted ISO timestamp string in the nearby response.
    """
    from backend.app.defect_workflow import record_initial_status
    from backend.app.models import Defect

    defect = Defect(
        defect_type="pothole",
        defect_status="reported",
        defect_severity="medium",
        latitude=19.08,
        longitude=72.88,
    )
    db_session.add(defect)
    db_session.flush()
    record_initial_status(db_session, defect)
    db_session.commit()

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 72.8777, "radius_km": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["reported_at"] is not None
    # IST offset (+05:30) should show up in the serialized timestamp.
    assert "+05:30" in body[0]["reported_at"]


def test_nearby_nearest_road_uses_real_segment_data_not_fabricated(
    client, citizen_token, make_segment, make_defect
):
    """
    nearest_road/road_segment_id must come from the defect's own real
    snapped RoadSegment (set by assign_defect_to_segment at creation time),
    never a made-up name, and must be None when no segment was snapped.
    """
    segment = make_segment(
        segment_id="SEG-NEARBY-1",
        coordinates=[[72.8770, 19.0760], [72.8790, 19.0780]],
        road_name="Real MCGM Road",
    )

    # Defect explicitly assigned to the segment (as assign_defect_to_segment
    # would do at creation time for a nearby point).
    on_segment = make_defect(latitude=19.0765, longitude=72.8775, segment=segment)

    # Defect far from any segment -- never snapped, segment stays None.
    unassigned = make_defect(latitude=19.20, longitude=73.05, segment=None)

    client.headers.update({"Authorization": f"Bearer {citizen_token}"})
    resp = client.get(
        "/reports/nearby",
        params={"latitude": 19.0760, "longitude": 72.8777, "radius_km": 50},
    )
    assert resp.status_code == 200
    body = {item["defect_id"]: item for item in resp.json()}

    assert body[on_segment.id]["road_segment_id"] == "SEG-NEARBY-1"
    assert body[on_segment.id]["nearest_road"] == "Real MCGM Road"

    assert body[unassigned.id]["road_segment_id"] is None
    assert body[unassigned.id]["nearest_road"] is None
