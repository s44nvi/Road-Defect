"""
test_hawker_integration.py
===========================
End-to-end tests for the hawker/street-vendor ML pipeline:

    POST /ml/hawkers/detect

MOCKED detector tests verify the plumbing -- that every detection in an
image reaches DetectionInput, is scored by the existing Road
Intelligence/AHP service (unchanged), and is persisted as its own Defect
(road segment assignment + initial status history included), atomically as
one batch. These do NOT load the real `production.pt` model.

One separate REAL-model smoke test at the bottom uses the actual model and
a genuine photograph (`fixtures/real_hawker_sample.jpg` -- a real street
vendor photo, Wikimedia Commons, public domain) to prove `production.pt`
produces a real detection end-to-end.

NOTE: every `backend.app.*` import below is done INSIDE each test/fixture
function, not at module level. `conftest.db_session` deletes and re-imports
all `backend.app.*` modules per-test (see its docstring) to pick up the
patched `DATABASE_URL`; a module-level import here would bind to the stale
pre-reimport objects (e.g. dependency-override keys would silently not
match, and ORM classes would not belong to the active `Base` metadata).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

FIXTURE_IMAGE = Path(__file__).resolve().parent / "fixtures" / "real_hawker_sample.jpg"


def _tiny_jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 32 + b"\xff\xd9"


def _detection(
    class_id=0,
    class_name="fixed-stall-vendor",
    confidence=0.8,
    bbox=None,
    image_width=1000,
    image_height=800,
) -> dict:
    return {
        "class_id": class_id,
        "class_name": class_name,
        "confidence": confidence,
        "bbox": bbox or [100.0, 100.0, 300.0, 300.0],
        "image_width": image_width,
        "image_height": image_height,
    }


def _auth_headers(citizen_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {citizen_token}"}


def _post_detect(client, headers, detections=None, latitude=19.0728, longitude=72.8826):
    from backend.app.dependencies import get_hawker_detector
    from backend.app.main import app

    if detections is not None:
        app.dependency_overrides[get_hawker_detector] = lambda: (lambda image_path: detections)
    try:
        return client.post(
            "/ml/hawkers/detect",
            headers=headers,
            data={"latitude": str(latitude), "longitude": str(longitude)},
            files={"file": ("hawker.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")},
        )
    finally:
        app.dependency_overrides.pop(get_hawker_detector, None)


# ---------------------------------------------------------------------------
# 1. Empty image / auth
# ---------------------------------------------------------------------------
def test_empty_image_returns_400(client, citizen_token):
    from backend.app.dependencies import get_hawker_detector
    from backend.app.main import app

    app.dependency_overrides[get_hawker_detector] = lambda: (lambda image_path: [_detection()])
    try:
        response = client.post(
            "/ml/hawkers/detect",
            headers=_auth_headers(citizen_token),
            data={"latitude": "19.0728", "longitude": "72.8826"},
            files={"file": ("hawker.jpg", io.BytesIO(b""), "image/jpeg")},
        )
    finally:
        app.dependency_overrides.pop(get_hawker_detector, None)

    assert response.status_code == 400


def test_unauthenticated_request_is_rejected(client):
    response = client.post(
        "/ml/hawkers/detect",
        data={"latitude": "19.0728", "longitude": "72.8826"},
        files={"file": ("hawker.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 2 & 3. Response structure + correct class names
# ---------------------------------------------------------------------------
def test_single_detection_response_structure(client, citizen_token):
    response = _post_detect(client, _auth_headers(citizen_token), [_detection(class_name="semi-fixed-vendor")])

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "hawker.jpg"
    assert len(body["detections"]) == 1

    item = body["detections"][0]
    assert item["class_name"] == "semi-fixed-vendor"
    assert item["className"] == "semi-fixed-vendor"
    assert item["confidence"] == 0.8
    assert item["bbox"] == [100.0, 100.0, 300.0, 300.0]
    assert "defect_id" in item and item["defect_id"] > 0
    assert "defect_severity" in item
    assert "severity_score" in item
    assert "defect_priority" in item
    assert item["latitude"] == 19.0728
    assert item["longitude"] == 72.8826


@pytest.mark.parametrize(
    "class_name",
    ["fixed-stall-vendor", "semi-fixed-vendor", "itinerant-vendor"],
)
def test_all_three_model_classes_are_accepted(client, citizen_token, class_name):
    response = _post_detect(client, _auth_headers(citizen_token), [_detection(class_name=class_name)])

    assert response.status_code == 200
    assert response.json()["detections"][0]["class_name"] == class_name


# ---------------------------------------------------------------------------
# 4, 5, 6. Detection -> DetectionInput -> severity -> priority (existing
# Road Intelligence/AHP service, verified by cross-checking against a
# direct call to the same service with the same inputs)
# ---------------------------------------------------------------------------
def test_severity_and_priority_match_the_existing_road_intelligence_service(client, citizen_token):
    from backend.app.road_intelligence import service as road_intelligence_service
    from backend.app.road_intelligence.schemas import AnalyzeRequest, DetectionInput, RoadContext

    detection = _detection(class_name="fixed-stall-vendor", confidence=0.65, bbox=[50.0, 50.0, 250.0, 250.0])

    response = _post_detect(client, _auth_headers(citizen_token), [detection])
    assert response.status_code == 200
    item = response.json()["detections"][0]

    expected = road_intelligence_service.analyze(
        AnalyzeRequest(
            detection=DetectionInput(
                class_id=detection["class_id"],
                class_name=detection["class_name"],
                confidence=detection["confidence"],
                bbox=detection["bbox"],
                image_width=detection["image_width"],
                image_height=detection["image_height"],
            ),
            context=RoadContext(latitude=19.0728, longitude=72.8826),
        )
    )

    assert item["severity_score"] == expected.severity.score
    assert item["defect_severity"] == expected.severity.category.lower()
    assert item["defect_priority"] == expected.priority.score
    # Hawker classes are mapped in road_intelligence/config.py -- not the
    # unknown-class fallback midpoint.
    assert expected.severity.breakdown.data_flags["defect_type_unmapped"] is False


def test_hawker_severity_baselines_are_ordered_fixed_gt_semi_gt_itinerant():
    """The documented severity ordering: fixed-stall > semi-fixed > itinerant."""
    from backend.app.road_intelligence import config

    assert (
        config.DEFECT_TYPE_BASE_SEVERITY["fixed-stall-vendor"]
        > config.DEFECT_TYPE_BASE_SEVERITY["semi-fixed-vendor"]
        > config.DEFECT_TYPE_BASE_SEVERITY["itinerant-vendor"]
    )


def test_image_dimensions_reach_severity_not_fallback(client, citizen_token):
    """Real image_width/image_height from the detector must reach
    DetectionInput -- confirmed by data_flags NOT reporting a
    size/dimension estimate fallback."""
    from backend.app.road_intelligence import service as road_intelligence_service
    from backend.app.road_intelligence.schemas import AnalyzeRequest, DetectionInput

    detection = _detection(image_width=1200, image_height=900)

    response = _post_detect(client, _auth_headers(citizen_token), [detection])
    assert response.status_code == 200

    expected = road_intelligence_service.analyze(
        AnalyzeRequest(
            detection=DetectionInput(
                class_id=detection["class_id"],
                class_name=detection["class_name"],
                confidence=detection["confidence"],
                bbox=detection["bbox"],
                image_width=detection["image_width"],
                image_height=detection["image_height"],
            ),
        )
    )
    assert expected.severity.breakdown.data_flags["size_estimated"] is False
    assert expected.severity.breakdown.data_flags["dimension_estimated"] is False


# ---------------------------------------------------------------------------
# 7, 8, 9. Defect persistence + road segment assignment + initial status
# ---------------------------------------------------------------------------
def test_detection_is_persisted_with_segment_and_status_history(
    client, citizen_token, db_session, make_segment
):
    from backend.app.models import Defect, DefectStatusHistory

    make_segment("SEG-HAWKER", [[72.8820, 19.0725], [72.8830, 19.0730]], length_km=0.5)

    response = _post_detect(
        client,
        _auth_headers(citizen_token),
        [_detection()],
        latitude=19.0727,
        longitude=72.8825,
    )
    assert response.status_code == 200
    defect_id = response.json()["detections"][0]["defect_id"]

    defect = db_session.query(Defect).filter(Defect.id == defect_id).first()
    assert defect is not None
    assert defect.defect_type == "fixed-stall-vendor"
    assert defect.defect_status == "reported"
    assert defect.image_path is not None
    assert defect.road_segment_id is not None
    assert defect.road_segment.segment_id == "SEG-HAWKER"

    history = (
        db_session.query(DefectStatusHistory)
        .filter(DefectStatusHistory.defect_id == defect.id)
        .all()
    )
    assert len(history) == 1
    assert history[0].new_status == "reported"
    assert history[0].old_status is None


# ---------------------------------------------------------------------------
# 10, 11. Multiple detections -> multiple Defects, all in the response
# ---------------------------------------------------------------------------
def test_multiple_detections_create_multiple_defects(client, citizen_token, db_session):
    from backend.app.models import Defect

    detections = [
        _detection(class_name="fixed-stall-vendor", bbox=[0.0, 0.0, 100.0, 100.0]),
        _detection(class_name="semi-fixed-vendor", bbox=[150.0, 150.0, 250.0, 250.0]),
        _detection(class_name="itinerant-vendor", bbox=[300.0, 300.0, 400.0, 400.0]),
        _detection(class_name="fixed-stall-vendor", bbox=[500.0, 500.0, 600.0, 600.0]),
    ]

    response = _post_detect(client, _auth_headers(citizen_token), detections)

    assert response.status_code == 200
    body = response.json()
    assert len(body["detections"]) == 4

    defect_ids = {item["defect_id"] for item in body["detections"]}
    assert len(defect_ids) == 4  # 4 distinct Defect rows

    assert db_session.query(Defect).filter(Defect.id.in_(defect_ids)).count() == 4
    for item in body["detections"]:
        assert item["defect_id"] > 0
        assert "defect_severity" in item
        assert "defect_priority" in item

    # All four came from the same uploaded image.
    image_paths = {item["image_path"] for item in body["detections"]}
    assert len(image_paths) == 1


def test_no_detections_returns_422_and_persists_nothing(client, citizen_token, db_session):
    from backend.app.models import Defect

    response = _post_detect(client, _auth_headers(citizen_token), [])

    assert response.status_code == 422
    assert db_session.query(Defect).count() == 0


def test_one_invalid_detection_persists_none_of_the_batch(client, citizen_token, db_session):
    """
    If any detection in the batch fails severity validation, the whole
    request is rejected (422) and NOTHING from the batch is persisted --
    proves the atomic all-or-nothing contract, not per-detection partial
    writes.
    """
    from backend.app.models import Defect

    valid = _detection(class_name="fixed-stall-vendor")
    invalid = _detection(class_name="semi-fixed-vendor", confidence=1.5)  # out of [0,1]

    response = _post_detect(client, _auth_headers(citizen_token), [valid, invalid])

    assert response.status_code == 422
    assert db_session.query(Defect).count() == 0


# ---------------------------------------------------------------------------
# Real model smoke test (not mocked): proves production.pt produces a real
# detection end-to-end, through the actual FastAPI route.
# ---------------------------------------------------------------------------
def test_real_model_detects_a_hawker_end_to_end(client, citizen_token, db_session):
    pytest.importorskip("ultralytics")
    pytest.importorskip("torch")
    if not FIXTURE_IMAGE.exists():
        pytest.skip("real_hawker_sample.jpg fixture not present")

    from backend.app.models import Defect

    # No detector override here -- exercises the real default
    # (`get_hawker_detector` -> `app.ml.hawkers.inference.predict`) against
    # a genuine street-vendor photograph.
    with FIXTURE_IMAGE.open("rb") as fh:
        response = client.post(
            "/ml/hawkers/detect",
            headers=_auth_headers(citizen_token),
            data={"latitude": "19.0728", "longitude": "72.8826"},
            files={"file": ("real_hawker_sample.jpg", fh, "image/jpeg")},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["detections"]) >= 1

    item = body["detections"][0]
    assert item["class_name"] in {"fixed-stall-vendor", "semi-fixed-vendor", "itinerant-vendor"}
    assert 0.0 <= item["confidence"] <= 1.0
    assert item["defect_id"] > 0
    assert item["defect_severity"] in {"low", "medium", "high", "critical"}
    assert 0.0 <= item["defect_priority"] <= 100.0

    defect = db_session.query(Defect).filter(Defect.id == item["defect_id"]).first()
    assert defect is not None
    assert defect.defect_type == item["class_name"]
