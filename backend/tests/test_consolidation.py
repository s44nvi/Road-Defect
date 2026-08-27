"""
Regression tests for duplicate-report consolidation (see
`backend/app/consolidation.py`).

Rule under test: two reports of the SAME defect_type within
CONSOLIDATION_RADIUS_METERS (20m) of each other are linked -- the second
becomes a duplicate of the first (canonical) -- and canonical-facing views
(`GET /defects`, `GET /community/issues`) expose ONE row with an aggregated
`report_count`/`observation_count`, while the individual underlying report
rows are never deleted and remain independently retrievable with their own
ownership.
"""

from __future__ import annotations


def _post_report(client, latitude, longitude, defect_type="pothole", severity="medium"):
    response = client.post(
        "/reports",
        json={
            "defect_type": defect_type,
            "defect_severity": severity,
            "latitude": latitude,
            "longitude": longitude,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_nearby_same_type_reports_consolidate_into_one_municipal_defect(client, db_session):
    from backend.app.models import Defect

    base_lat, base_lon = 19.0728, 72.8826
    # ~5m offset in latitude (well within the 20m radius).
    near_lat = base_lat + 0.00004

    first = _post_report(client, base_lat, base_lon)
    second = _post_report(client, near_lat, base_lon)

    first_row = db_session.query(Defect).filter(Defect.id == first["defect_id"]).one()
    second_row = db_session.query(Defect).filter(Defect.id == second["defect_id"]).one()

    # Second report links to the first as its canonical parent.
    assert first_row.canonical_defect_id is None
    assert second_row.canonical_defect_id == first_row.id

    # Both individual rows still exist as separate DB rows.
    assert first_row.id != second_row.id

    # The officer dashboard shows exactly one municipal defect for this
    # cluster, with report_count reflecting both reports.
    officer_view = client.get("/defects")
    assert officer_view.status_code == 200
    matching = [d for d in officer_view.json() if d["defect_id"] == first_row.id]
    assert len(matching) == 1
    assert matching[0]["report_count"] == 2

    # The duplicate must never appear as its own row in the officer list.
    duplicate_rows = [d for d in officer_view.json() if d["defect_id"] == second_row.id]
    assert duplicate_rows == []


def test_far_apart_same_type_reports_stay_independent(client, db_session):
    from backend.app.models import Defect

    first = _post_report(client, 19.0728, 72.8826)
    # ~1km away -- far outside the consolidation radius.
    second = _post_report(client, 19.0818, 72.8826)

    first_row = db_session.query(Defect).filter(Defect.id == first["defect_id"]).one()
    second_row = db_session.query(Defect).filter(Defect.id == second["defect_id"]).one()

    assert first_row.canonical_defect_id is None
    assert second_row.canonical_defect_id is None

    officer_view = client.get("/defects")
    ids = {d["defect_id"] for d in officer_view.json()}
    assert first_row.id in ids
    assert second_row.id in ids
    for row in officer_view.json():
        assert row["report_count"] == 1


def test_different_defect_type_does_not_consolidate(client, db_session):
    from backend.app.models import Defect

    base_lat, base_lon = 19.0728, 72.8826
    near_lat = base_lat + 0.00004

    first = _post_report(client, base_lat, base_lon, defect_type="pothole")
    second = _post_report(client, near_lat, base_lon, defect_type="alligator_crack")

    first_row = db_session.query(Defect).filter(Defect.id == first["defect_id"]).one()
    second_row = db_session.query(Defect).filter(Defect.id == second["defect_id"]).one()

    assert first_row.canonical_defect_id is None
    assert second_row.canonical_defect_id is None


def test_individual_citizen_reports_remain_retrievable_after_consolidation(
    client, db_session, dev_citizen, citizen_token
):
    """
    Consolidating reports for the aggregated municipal-defect view must NOT
    remove or overwrite the individual citizen report rows -- ownership,
    image, and timestamp for each original report stay intact and
    separately queryable (here via GET /reports/mine).
    """
    client.headers.update({"Authorization": f"Bearer {citizen_token}"})

    base_lat, base_lon = 19.10, 72.90
    near_lat = base_lat + 0.00004

    first = _post_report(client, base_lat, base_lon)
    second = _post_report(client, near_lat, base_lon)

    # POST /reports is unauthenticated and doesn't attach citizen_id, so
    # attach ownership directly to exercise "individually retrievable with
    # correct ownership" the way the authenticated image/submit paths would.
    from backend.app.models import Defect

    for defect_id in (first["defect_id"], second["defect_id"]):
        row = db_session.query(Defect).filter(Defect.id == defect_id).one()
        row.citizen_id = dev_citizen.id
    db_session.commit()

    mine = client.get("/reports/mine")
    assert mine.status_code == 200
    mine_ids = {d["defect_id"] for d in mine.json()}
    assert first["defect_id"] in mine_ids
    assert second["defect_id"] in mine_ids


def test_consolidation_radius_constant_is_sane():
    from backend.app.consolidation import CONSOLIDATION_RADIUS_METERS

    # Sanity check on the documented threshold (15-25m guidance).
    assert 15.0 <= CONSOLIDATION_RADIUS_METERS <= 25.0
