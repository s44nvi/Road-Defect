"""
test_mcgm_import.py
====================
Tests for MultiLineString geometry support (road_health.geo /
road_health.service / road_health.assignment) and the MCGM demo road
importer (backend/scripts/import_demo_roads.py).

Covers the two things that mattered most for this feature:
  * a genuinely disconnected MultiLineString round-trips through the API
    with its parts intact -- never bridged/merged/dropped.
  * the importer is idempotent: running it twice on the same CSV row
    updates the same RoadSegment rather than creating a duplicate.
"""

from __future__ import annotations

import sys

import pandas as pd
import pytest


def _import_demo_roads_module():
    """
    Fresh import of the importer module, bound to the CURRENT
    `backend.app.models`/`backend.app.database` classes.

    `conftest.db_session` deletes and re-imports every `backend.app.*`
    module per test (see its docstring), but `backend.scripts.*` modules
    are outside that prefix and are cached by Python's normal import
    machinery -- if `import_demo_roads` were imported once and reused, its
    `RoadSegment`/`SessionLocal` bindings would point at a PREVIOUS test's
    (already-torn-down) classes. Forcing a fresh import here keeps it
    bound to the same live `RoadSegment` class `db_session` uses.
    """
    for name in [m for m in list(sys.modules) if m.startswith("backend.scripts.import_demo_roads")]:
        del sys.modules[name]

    import backend.scripts.import_demo_roads as module

    return module


# ---------------------------------------------------------------------------
# geo.py: MultiLineString parsing/serialization/length/distance
# ---------------------------------------------------------------------------
def test_parse_multilinestring_preserves_each_part():
    from backend.app.road_health.geo import multi_linestring, parse_geometry_parts

    part_a = [[72.80, 19.00], [72.81, 19.00]]
    part_b = [[72.90, 19.10], [72.91, 19.10], [72.92, 19.10]]

    geometry = multi_linestring([part_a, part_b])
    parts = parse_geometry_parts(geometry)

    assert len(parts) == 2
    assert parts[0] == part_a
    assert parts[1] == part_b


def test_total_length_km_sums_parts_without_bridging_the_gap():
    from backend.app.road_health.geo import linestring_length_km, total_length_km

    # Two widely separated parts -- if the gap were ever bridged, the total
    # would include an extra ~50km leg between them.
    part_a = [[72.80, 19.00], [72.81, 19.00]]  # short leg near Mumbai
    part_b = [[73.80, 18.00], [73.81, 18.00]]  # short leg ~140km away

    total = total_length_km([part_a, part_b])
    expected = linestring_length_km(part_a) + linestring_length_km(part_b)

    assert total == pytest.approx(expected)
    # Sanity: nowhere near what bridging the ~140km gap would add.
    assert total < 10.0


def test_linestring_still_round_trips_as_linestring_not_multilinestring():
    from backend.app.road_health.geo import linestring, parse_geometry_parts

    geometry = linestring([[72.80, 19.00], [72.81, 19.00]])
    assert geometry["type"] == "LineString"

    parts = parse_geometry_parts(geometry)
    assert len(parts) == 1


def test_point_to_geometry_distance_uses_nearest_part():
    from backend.app.road_health.geo import point_to_geometry_distance_km

    near_part = [[72.80, 19.00], [72.81, 19.00]]
    far_part = [[73.80, 18.00], [73.81, 18.00]]

    # A point right on near_part's first vertex.
    distance = point_to_geometry_distance_km(19.00, 72.80, [near_part, far_part])

    assert distance == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# service.py / API: a MultiLineString segment round-trips through
# GET /road-health/segments and GET /road-health/segments/{id}
# ---------------------------------------------------------------------------
def _make_multipart_segment(db_session, segment_id="SEG-MULTI"):
    from backend.app.models import RoadSegment
    from backend.app.road_health.geo import multi_linestring, total_length_km

    part_a = [[72.8300, 19.0700], [72.8310, 19.0705]]
    part_b = [[72.8400, 19.0800], [72.8410, 19.0805]]  # genuinely disconnected

    segment = RoadSegment(
        segment_id=segment_id,
        road_name="Test Multi Road",
        geometry=multi_linestring([part_a, part_b]),
        length_km=round(total_length_km([part_a, part_b]), 3),
        geometry_source="mcgm_demo_csv_v1",
        mcgm_id="99999",
        ward="TEST",
        work_status="Work In Progress",
        source_length_m=1.23,
    )
    db_session.add(segment)
    db_session.commit()
    db_session.refresh(segment)
    return segment, part_a, part_b


def test_multilinestring_segment_appears_in_collection(client, db_session):
    _make_multipart_segment(db_session)

    body = client.get("/road-health/segments").json()
    feature = next(
        f for f in body["features"] if f["properties"]["segment_id"] == "SEG-MULTI"
    )

    assert feature["geometry"]["type"] == "MultiLineString"
    assert len(feature["geometry"]["coordinates"]) == 2


def test_multilinestring_segment_detail_preserves_disconnected_parts(client, db_session):
    _, part_a, part_b = _make_multipart_segment(db_session)

    body = client.get("/road-health/segments/SEG-MULTI").json()

    assert body["geometry"]["type"] == "MultiLineString"
    assert body["geometry"]["coordinates"] == [part_a, part_b]
    # MCGM metadata surfaced end-to-end.
    assert body["mcgm_id"] == "99999"
    assert body["ward"] == "TEST"
    assert body["work_status"] == "Work In Progress"
    assert body["source_length_m"] == 1.23
    assert body["mcgmId"] == "99999"
    assert body["workStatus"] == "Work In Progress"
    assert body["sourceLengthM"] == 1.23


def test_defect_snaps_to_the_nearer_part_of_a_multilinestring_segment(client, db_session, make_defect):
    from backend.app.road_health import service as road_health_service

    segment, part_a, _ = _make_multipart_segment(db_session)

    # A defect placed right on part_a should snap to this segment even
    # though part_b is a different, disconnected chunk of the same row.
    defect = make_defect(19.0700, 72.8300, segment=None)
    road_health_service.assign_defect_to_segment(db_session, defect)
    db_session.commit()

    assert defect.road_segment_id == segment.id


# ---------------------------------------------------------------------------
# Importer: WKT parsing preserves disconnected parts (no silent drop / no
# fabricated bridge), and the DB upsert is idempotent.
# ---------------------------------------------------------------------------
def test_parse_wkt_linestring():
    from backend.scripts.import_demo_roads import parse_wkt

    parts = parse_wkt("LINESTRING(72.80 19.00, 72.81 19.00, 72.82 19.00)")

    assert len(parts) == 1
    assert parts[0] == [[72.80, 19.00], [72.81, 19.00], [72.82, 19.00]]


def test_parse_wkt_multilinestring_keeps_disconnected_parts_separate():
    """
    Mirrors the real 13th Road,Khar(W) shape: two parts, ~770m apart.
    Must NOT be merged into one LineString and must NOT silently drop the
    second part.
    """
    from backend.app.road_health.geo import total_length_km
    from backend.scripts.import_demo_roads import parse_wkt

    wkt = (
        "MULTILINESTRING("
        "(72.8300 19.0700, 72.8290 19.0720),"
        "(72.8400 19.0600, 72.8410 19.0590))"
    )

    parts = parse_wkt(wkt)

    assert len(parts) == 2
    assert parts[0] == [[72.8300, 19.0700], [72.8290, 19.0720]]
    assert parts[1] == [[72.8400, 19.0600], [72.8410, 19.0590]]
    # Both parts contribute to the total length -- nothing silently dropped.
    assert total_length_km(parts) == pytest.approx(
        total_length_km([parts[0]]) + total_length_km([parts[1]])
    )
    assert total_length_km(parts) > total_length_km([parts[0]])


def _demo_row(**overrides) -> pd.Series:
    base = {
        "id": 99999,
        "road_name": "Test Import Road",
        "ward": "H/W",
        "status": "Work In Progress",
        "length_of_road_m": 0.5,
        "geometry_wkt": "LINESTRING(72.8300 19.0700, 72.8310 19.0705)",
    }
    base.update(overrides)
    return pd.Series(base)


def test_import_row_is_idempotent(db_session):
    from backend.app.models import RoadSegment
    import_row = _import_demo_roads_module().import_row

    row = _demo_row()

    import_row(db_session, row)
    db_session.commit()

    import_row(db_session, row)  # run again with the same row
    db_session.commit()

    segments = (
        db_session.query(RoadSegment).filter(RoadSegment.segment_id == "MCGM-99999").all()
    )
    assert len(segments) == 1


def test_import_row_sets_mcgm_metadata_and_geometry_source(db_session):
    from backend.app.road_health.config import GEOMETRY_SOURCE_MCGM_DEMO
    import_row = _import_demo_roads_module().import_row

    segment = import_row(db_session, _demo_row())
    db_session.commit()

    assert segment.segment_id == "MCGM-99999"
    assert segment.road_name == "Test Import Road"
    assert segment.ward == "H/W"
    assert segment.work_status == "Work In Progress"
    assert segment.source_length_m == 0.5
    assert segment.geometry_source == GEOMETRY_SOURCE_MCGM_DEMO
    assert segment.geometry["type"] == "LineString"


def test_import_row_multilinestring_disconnected_stays_disconnected(db_session):
    import_row = _import_demo_roads_module().import_row

    wkt = (
        "MULTILINESTRING("
        "(72.8300 19.0700, 72.8290 19.0720),"
        "(72.8400 19.0600, 72.8410 19.0590))"
    )

    segment = import_row(db_session, _demo_row(geometry_wkt=wkt))
    db_session.commit()

    assert segment.geometry["type"] == "MultiLineString"
    assert len(segment.geometry["coordinates"]) == 2
    assert segment.geometry["coordinates"][0] == [[72.8300, 19.0700], [72.8290, 19.0720]]
    assert segment.geometry["coordinates"][1] == [[72.8400, 19.0600], [72.8410, 19.0590]]


def test_import_row_updates_existing_segment_fields_on_rerun(db_session):
    import_row = _import_demo_roads_module().import_row

    import_row(db_session, _demo_row(status="Work In Progress"))
    db_session.commit()

    updated = import_row(db_session, _demo_row(status="Completed"))
    db_session.commit()

    assert updated.work_status == "Completed"
