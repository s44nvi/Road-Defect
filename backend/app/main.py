from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pathlib import Path
import tempfile
import uuid

from .auth.dependencies import get_current_officer
from .auth.schemas import (
    CitizenLoginRequest,
    CitizenLoginResponse,
    OfficerLoginRequest,
    OfficerLoginResponse,
)
from .auth.service import InvalidCredentialsError, authenticate_citizen, authenticate_officer, issue_citizen_token, issue_officer_token
from .dependencies import get_db, get_pothole_detector
from .defect_workflow import (
    InvalidStatusError,
    InvalidTransitionError,
    apply_status_change,
    record_initial_status,
)
from .models import Defect, Officer
from .schemas import (
    DefectDetailResponse,
    DefectResponse,
    DefectResponseWithPriority,
    DefectStatusChangeRequest,
    DefectStatusUpdate,
    ImageReportResponse,
    ReportCreate,
)
from .road_health import service as road_health_service
from .road_health.router import router as road_health_router
from .road_health.schemas import StatusHistoryEntry
from .road_intelligence.schemas import AnalyzeRequest, AnalyzeResponse, RoadContext
from .road_intelligence import service as road_intelligence_service
from .road_intelligence.severity import InvalidDetectionError
from .road_intelligence.scoring import InvalidContextError
from .ml.hawkers.inference import predict
from .ml.potholes.adapter import to_detection_input
from .ml.potholes.detector import ModelUnavailableError, PotholeDetector

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads" / "reports"

app = FastAPI(title="Road-Defect Backend")

app.include_router(road_health_router)

# `get_db` now lives in `dependencies.py` so routers can use it without
# importing this module. Re-exported here so existing
# `from .main import get_db` imports (and test overrides) keep working.
__all__ = ["app", "get_db"]


def _apply_status(
    db: Session,
    defect: Defect,
    status: str | None,
    note: str | None,
    changed_by: str | None,
    legacy: bool,
) -> None:
    """
    Run a status change through the workflow, translating its errors into HTTP.

        422 -- the status string is not in the allowed vocabulary
        409 -- the status is valid but not reachable from the current one

    On rejection nothing is written; the caller's transaction is left clean.
    """
    try:
        apply_status_change(
            db,
            defect,
            new_status=status,
            note=note,
            changed_by=changed_by,
            legacy=legacy,
        )
    except InvalidStatusError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


def _defect_detail(defect: Defect) -> dict:
    """Defect payload for the officer workflow endpoints (both key styles)."""
    segment_id = defect.road_segment.segment_id if defect.road_segment else None

    return {
        "defect_id": defect.id,
        "defect_type": defect.defect_type,
        "defect_status": defect.defect_status,
        "defect_severity": defect.defect_severity,
        "latitude": defect.latitude,
        "longitude": defect.longitude,
        "road_segment_id": segment_id,
        "is_test_data": bool(defect.is_test_data),
        "defectId": defect.id,
        "defectType": defect.defect_type,
        "defectStatus": defect.defect_status,
        "defectSeverity": defect.defect_severity,
        "roadSegmentId": segment_id,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/officer/login", response_model=OfficerLoginResponse)
def officer_login(request: OfficerLoginRequest, db: Session = Depends(get_db)):
    """
    Municipal officer login. Verifies against the `officers` table only --
    citizen credentials can never authenticate here (see
    `auth.service.authenticate_officer`, which queries `Officer` and nothing
    else). Returns 401 for unknown email, wrong password, or an inactive
    officer alike, so the response never reveals which case occurred.
    """
    try:
        officer = authenticate_officer(db, request.email, request.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "access_token": issue_officer_token(officer),
        "token_type": "bearer",
        "officer": {
            "officer_id": officer.id,
            "name": officer.name,
            "email": officer.email,
            "department": officer.department,
        },
    }


@app.post("/auth/citizen/login", response_model=CitizenLoginResponse)
def citizen_login(request: CitizenLoginRequest, db: Session = Depends(get_db)):
    """
    Citizen login. Verifies against the `citizens` table only -- mirrors
    `officer_login` but is backed by a completely separate identity space
    (see `auth.service.authenticate_citizen`), so officer credentials can
    never authenticate here.
    """
    try:
        citizen = authenticate_citizen(db, request.email, request.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "access_token": issue_citizen_token(citizen),
        "token_type": "bearer",
        "citizen": {
            "citizen_id": citizen.id,
            "name": citizen.name,
            "email": citizen.email,
        },
    }


@app.post("/reports", response_model=DefectResponseWithPriority)
def create_report(report: ReportCreate, db: Session = Depends(get_db)):
    defect = Defect(
        defect_type=report.defect_type,
        defect_status="reported",
        defect_severity=report.defect_severity,
        latitude=report.latitude,
        longitude=report.longitude,
    )

    db.add(defect)
    db.flush()

    # Snap the new report onto its canonical road segment, and open its status
    # timeline at "reported" so the officer view has a complete history.
    road_health_service.assign_defect_to_segment(db, defect)
    record_initial_status(db, defect)

    db.commit()
    db.refresh(defect)

    return {
        "defect_id": defect.id,
        "defect_type": defect.defect_type,
        "defect_status": defect.defect_status,
        "defect_severity": defect.defect_severity,
        "latitude": defect.latitude,
        "longitude": defect.longitude,
        "defect_priority": defect.defect_priority,
    }


@app.post("/reports/image", response_model=ImageReportResponse)
async def create_report_from_image(
    latitude: float = Form(...),
    longitude: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    detector: PotholeDetector = Depends(get_pothole_detector),
):
    """
    Image pipeline for pothole reports:

        uploaded image -> persist image -> PotholeDetector.detect()
            -> NormalizedDetection -> DetectionInput
            -> existing Road Intelligence/AHP service -> severity + priority
            -> persisted Defect

    This is additive: the pre-existing JSON `POST /reports` above is
    unchanged and still works for callers that already have a
    type/severity/lat/lon payload with no image.

    Until Harmeet's real detector is wired into
    `app.ml.potholes.detector.get_default_detector`, `detector.detect()`
    raises `ModelUnavailableError` and this route responds 503 rather than
    fabricating a detection. No fake inference output is ever persisted.
    """
    suffix = Path(file.filename or "").suffix or ".jpg"
    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    image_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    image_path.write_bytes(image_bytes)

    try:
        detections = detector.detect(image_path)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not detections:
        raise HTTPException(
            status_code=422,
            detail="No pothole detected in the uploaded image.",
        )

    # One Defect per report: score the highest-confidence detection, same as
    # a single manual report describes a single defect.
    primary = max(detections, key=lambda d: d.confidence)

    try:
        analysis = road_intelligence_service.analyze(
            AnalyzeRequest(
                detection=to_detection_input(primary),
                context=RoadContext(latitude=latitude, longitude=longitude),
            )
        )
    except (InvalidDetectionError, InvalidContextError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    defect = Defect(
        defect_type=primary.class_name,
        defect_status="reported",
        defect_severity=analysis.severity.category.lower(),
        defect_priority=analysis.priority.score,
        latitude=latitude,
        longitude=longitude,
        image_path=str(image_path),
    )

    db.add(defect)
    db.flush()

    road_health_service.assign_defect_to_segment(db, defect)
    record_initial_status(db, defect)

    db.commit()
    db.refresh(defect)

    detail = _defect_detail(defect)
    detail["defect_priority"] = defect.defect_priority
    detail["image_path"] = defect.image_path
    detail["defectPriority"] = defect.defect_priority
    detail["imagePath"] = defect.image_path

    return detail


@app.get("/defects", response_model=list[DefectResponseWithPriority])
def list_defects(db: Session = Depends(get_db)):
    defects = db.query(Defect).all()

    return [
        {
            "defect_id": defect.id,
            "defect_type": defect.defect_type,
            "defect_status": defect.defect_status,
            "defect_severity": defect.defect_severity,
            "latitude": defect.latitude,
            "longitude": defect.longitude,
            "defect_priority": defect.defect_priority,
        }
        for defect in defects
    ]


@app.post("/road-intelligence/analyze", response_model=AnalyzeResponse)
def analyze_defect(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return road_intelligence_service.analyze(request)
    except (InvalidDetectionError, InvalidContextError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.patch("/defects/{defect_id}", response_model=DefectResponse)
def update_defect(
    defect_id: int,
    update: DefectStatusUpdate,
    db: Session = Depends(get_db),
    officer: Officer = Depends(get_current_officer),
):
    """
    Existing status-update endpoint, kept backwards compatible.

    Same path, same request field (`defect_status`), same response shape, so
    the officer UI's existing Confirm/Reject buttons keep working unchanged.
    What is new is that the change is now validated against the workflow,
    requires an authenticated officer, and is recorded in
    `defect_status_history` instead of silently overwriting the status.

    This endpoint runs in `legacy` mode, which additionally permits the
    one-step `reported -> confirmed` transition the existing Confirm button
    relies on (see `defect_workflow.LEGACY_EXTRA_TRANSITIONS`). Prefer
    `PATCH /defects/{defect_id}/status` for new officer workflow code.
    """
    defect = db.query(Defect).filter(Defect.id == defect_id).first()

    if defect is None:
        raise HTTPException(status_code=404, detail="Defect not found")

    _apply_status(
        db,
        defect,
        status=update.defect_status,
        note=update.note,
        changed_by=str(officer.id),
        legacy=True,
    )

    db.commit()
    db.refresh(defect)

    return {
        "defect_id": defect.id,
        "defect_type": defect.defect_type,
        "defect_status": defect.defect_status,
        "defect_severity": defect.defect_severity,
        "latitude": defect.latitude,
        "longitude": defect.longitude,
    }


@app.patch("/defects/{defect_id}/status", response_model=DefectDetailResponse)
def update_defect_status(
    defect_id: int,
    request: DefectStatusChangeRequest,
    db: Session = Depends(get_db),
    officer: Officer = Depends(get_current_officer),
):
    """
    Officer status update with full workflow validation.

        PATCH /defects/12/status
        Authorization: Bearer <officer access token>
        {"status": "confirmed", "note": "Verified by municipal officer"}

    Validates the status against the allowed vocabulary, validates the
    transition against the workflow graph, records a `defect_status_history`
    row, updates the defect, and returns it. The status change and its history
    row are committed in one transaction.

    Road health is not recomputed here because it is never stored -- the
    road-health endpoints derive it from current defect rows on every request,
    so a status change is reflected immediately with no cache to invalidate.

    `changed_by` is always the authenticated officer's id (see
    `Depends(get_current_officer)` above) -- never a client-supplied header
    or body field. A request body may still include a `changed_by` field for
    backwards compatibility with older clients, but its value is ignored;
    trusting it would let one officer impersonate another.
    """
    defect = db.query(Defect).filter(Defect.id == defect_id).first()

    if defect is None:
        raise HTTPException(status_code=404, detail="Defect not found")

    _apply_status(
        db,
        defect,
        status=request.status,
        note=request.note,
        changed_by=str(officer.id),
        legacy=False,
    )

    db.commit()
    db.refresh(defect)

    return _defect_detail(defect)


@app.get(
    "/defects/{defect_id}/status-history",
    response_model=list[StatusHistoryEntry],
)
def get_defect_status_history(defect_id: int, db: Session = Depends(get_db)):
    """
    Full status timeline for a defect, oldest first.

    Powers the officer frontend's timeline view. The first entry of a defect
    created through `POST /reports` has `old_status = null`.
    """
    defect = db.query(Defect).filter(Defect.id == defect_id).first()

    if defect is None:
        raise HTTPException(status_code=404, detail="Defect not found")

    return [
        {
            "id": entry.id,
            "defect_id": entry.defect_id,
            "old_status": entry.old_status,
            "new_status": entry.new_status,
            "changed_by": entry.changed_by,
            "changed_at": entry.changed_at,
            "note": entry.note,
            "defectId": entry.defect_id,
            "oldStatus": entry.old_status,
            "newStatus": entry.new_status,
            "changedBy": entry.changed_by,
            "changedAt": entry.changed_at,
        }
        for entry in defect.status_history
    ]


@app.post("/ml/hawkers/detect")
async def detect_hawkers(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix or ".jpg"

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(image_bytes)
            temp_path = Path(temp_file.name)

        detections = predict(temp_path)

        return {
            "filename": file.filename,
            "detections": detections,
        }

    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
