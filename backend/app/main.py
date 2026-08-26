from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Callable
import uuid

from .auth.dependencies import get_current_citizen, get_current_officer
from .auth.schemas import (
    CitizenLoginRequest,
    CitizenLoginResponse,
    OfficerLoginRequest,
    OfficerLoginResponse,
)
from .auth.service import (
    InvalidCredentialsError,
    authenticate_citizen,
    authenticate_officer,
    issue_citizen_token,
    issue_officer_token,
)
from .dependencies import (
    get_db,
    get_dual_pothole_detector,
    get_hawker_detector,
    get_pothole_detector,
)
from .defect_workflow import (
    InvalidStatusError,
    InvalidTransitionError,
    apply_status_change,
    record_initial_status,
)
from .models import Citizen, Defect, Officer
from .schemas import (
    AnalyzeImageResponse,
    DefectDetailResponse,
    DefectResponse,
    DefectResponseWithPriority,
    DefectSeverityUpdate,
    DefectStatusChangeRequest,
    DefectStatusUpdate,
    HawkerDetectionResponse,
    ImageReportResponse,
    PublicIssueResponse,
    ReportCreate,
    SubmitReportRequest,
)
from .road_health import service as road_health_service
from .road_health.config import STATUS_CONFIRMED, STATUS_IN_PROGRESS, STATUS_RESOLVED
from .road_health.router import router as road_health_router
from .assets.router import router as assets_router
from .road_health.schemas import StatusHistoryEntry
from .road_intelligence.schemas import AnalyzeRequest, AnalyzeResponse, DetectionInput, RoadContext
from .road_intelligence import service as road_intelligence_service
from .road_intelligence.severity import InvalidDetectionError
from .road_intelligence.scoring import InvalidContextError
from .ml.potholes.adapter import to_detection_input
from .ml.potholes.detector import ModelUnavailableError, NormalizedDetection, PotholeDetector
from .timezone_utils import to_ist


UPLOAD_DIR = Path(__file__).resolve().parent / "uploads" / "reports"
ANALYZED_IMAGE_DIR = Path(__file__).resolve().parent / "uploads" / "analyzed"

app = FastAPI(title="Road-Defect Backend")

app.include_router(road_health_router)
app.include_router(assets_router)

# Serves persisted report/analyzed images at GET /uploads/<...> so
# `image_path`/`image_url` in officer responses point at something the
# frontend can actually fetch, instead of a bare filesystem path outside any
# served directory. Mirrors the existing on-disk layout under
# `app/uploads/` (see UPLOAD_DIR/ANALYZED_IMAGE_DIR above).
_UPLOADS_ROOT = Path(__file__).resolve().parent / "uploads"
_UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_UPLOADS_ROOT)), name="uploads")


def _image_url(image_path: str | None) -> str | None:
    """
    Map a stored filesystem `image_path` (always somewhere under
    `app/uploads/`, see UPLOAD_DIR/ANALYZED_IMAGE_DIR) to the API-servable
    `/uploads/...` URL the StaticFiles mount above serves.
    """
    if not image_path:
        return None
    try:
        relative = Path(image_path).resolve().relative_to(_UPLOADS_ROOT)
    except ValueError:
        return None
    return f"/uploads/{relative.as_posix()}"

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

    reporter = None
    if defect.citizen is not None:
        reporter = {
            "id": defect.citizen.id,
            "full_name": defect.citizen.name,
            "email": defect.citizen.email,
        }

    # The "reported" status-history row is always written by
    # record_initial_status at creation time (see defect_workflow.py); the
    # timeline is ordered oldest-first, so entry [0] is it.
    reported_at = to_ist(defect.status_history[0].changed_at) if defect.status_history else None

    image_url = _image_url(defect.image_path)

    return {
        "defect_id": defect.id,
        "defect_type": defect.defect_type,
        "defect_status": defect.defect_status,
        "defect_severity": defect.defect_severity,
        "latitude": defect.latitude,
        "longitude": defect.longitude,
        "road_segment_id": segment_id,
        "is_test_data": bool(defect.is_test_data),
        "reporter": reporter,
        "ai_confidence": defect.ai_confidence,
        "ai_bbox": defect.ai_bbox,
        "ai_severity_score": defect.ai_severity_score,
        "defect_priority": defect.defect_priority,
        "image_path": defect.image_path,
        "image_url": image_url,
        "reported_at": reported_at,
        "defectId": defect.id,
        "defectType": defect.defect_type,
        "defectStatus": defect.defect_status,
        "defectSeverity": defect.defect_severity,
        "roadSegmentId": segment_id,
        "aiConfidence": defect.ai_confidence,
        "aiBbox": defect.ai_bbox,
        "aiSeverityScore": defect.ai_severity_score,
        "defectPriority": defect.defect_priority,
        "imagePath": defect.image_path,
        "imageUrl": image_url,
        "reportedAt": reported_at,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/officer/login", response_model=OfficerLoginResponse)
def officer_login(
    request: OfficerLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Municipal officer login. Verifies against the `officers` table only.
    """
    try:
        officer = authenticate_officer(db, request.email, request.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

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
def citizen_login(
    request: CitizenLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Citizen login. Verifies against the `citizens` table only.
    """
    try:
        citizen = authenticate_citizen(db, request.email, request.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

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
def create_report(
    report: ReportCreate,
    db: Session = Depends(get_db),
):
    """
    Create a report.

    This endpoint intentionally remains public/unauthenticated for backwards
    compatibility with the existing reporting API and frontend.

    If the caller is authenticated as a citizen, ownership can be associated
    through the authenticated image-report path (`POST /reports/image`) and
    citizen-scoped reports are exposed through `GET /reports/mine`.

    The JSON report endpoint itself does not require a citizen token.
    """
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


@app.get(
    "/reports/mine",
    response_model=list[DefectResponseWithPriority],
)
def get_my_reports(
    db: Session = Depends(get_db),
    citizen: Citizen = Depends(get_current_citizen),
):
    """
    Return only reports submitted by the authenticated citizen.

    This is deliberately user-scoped in the database query rather than
    fetching all defects and filtering on the frontend.
    """
    defects = (
        db.query(Defect)
        .filter(Defect.citizen_id == citizen.id)
        .order_by(Defect.id.desc())
        .all()
    )

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


@app.post("/reports/image", response_model=ImageReportResponse)
async def create_report_from_image(
    latitude: float = Form(...),
    longitude: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    citizen: Citizen = Depends(get_current_citizen),
    detector: PotholeDetector = Depends(get_pothole_detector),
):
    """
    Image pipeline for authenticated citizen pothole reports:

        uploaded image
            -> persist image
            -> PotholeDetector.detect()
            -> NormalizedDetection
            -> DetectionInput
            -> existing Road Intelligence/AHP service
            -> severity + priority
            -> persisted Defect linked to citizen

    Until Harmeet's real detector is wired in, detector.detect() raises
    ModelUnavailableError and this route responds with 503.

    No fake inference result is ever returned or persisted.
    """
    suffix = Path(file.filename or "").suffix or ".jpg"
    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Empty image file",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    image_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    image_path.write_bytes(image_bytes)

    try:
        detections = detector.detect(image_path)
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    if not detections:
        raise HTTPException(
            status_code=422,
            detail="No pothole detected in the uploaded image.",
        )

    # One Defect per report: score the highest-confidence detection.
    primary = max(
        detections,
        key=lambda detection: detection.confidence,
    )

    try:
        analysis = road_intelligence_service.analyze(
            AnalyzeRequest(
                detection=to_detection_input(primary),
                context=RoadContext(
                    latitude=latitude,
                    longitude=longitude,
                ),
            )
        )
    except (InvalidDetectionError, InvalidContextError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    defect = Defect(
        defect_type=primary.class_name,
        defect_status="reported",
        defect_severity=analysis.severity.category.lower(),
        defect_priority=analysis.priority.score,
        latitude=latitude,
        longitude=longitude,
        image_path=str(image_path),
        citizen_id=citizen.id,
    )

    db.add(defect)
    db.flush()

    road_health_service.assign_defect_to_segment(db, defect)
    record_initial_status(db, defect)

    db.commit()
    db.refresh(defect)

    return _defect_detail(defect)


def _best_detection(
    pothole_detections: list[NormalizedDetection],
    hawker_detections: list[dict],
) -> tuple[str, float, list[float], int | None, dict | None] | None:
    """
    Pick the single best real detection across the (separate, never merged --
    see module docstring in `ml/potholes/arbitration.py`) pothole and hawker
    detector streams, for the analyze/submit endpoints.

    Returns `(class_name, confidence, bbox, image_width, hawker_raw_or_None)`
    or `None` if neither stream produced anything. `hawker_raw_or_None` is
    the raw hawker detection dict (needed for `DetectionInput` construction
    with real image dimensions) when the winner came from that stream.
    """
    candidates: list[tuple[str, float, list[float], int | None, int | None, dict | None]] = []

    for detection in pothole_detections:
        candidates.append(
            (
                detection.class_name,
                detection.confidence,
                list(detection.bbox_xyxy),
                detection.image_width,
                detection.image_height,
                None,
            )
        )

    for detection in hawker_detections:
        candidates.append(
            (
                detection["class_name"],
                detection["confidence"],
                detection["bbox"],
                detection.get("image_width"),
                detection.get("image_height"),
                detection,
            )
        )

    if not candidates:
        return None

    class_name, confidence, bbox, image_width, image_height, hawker_raw = max(
        candidates, key=lambda c: c[1]
    )
    return class_name, confidence, bbox, image_width, image_height, hawker_raw


def _run_detectors(
    image_path: Path,
    pothole_detector: PotholeDetector,
    hawker_detector: Callable[[str | Path], list[dict]],
) -> tuple[list[NormalizedDetection], list[dict]]:
    """
    Run both detector streams over the same persisted image. Kept as one
    small helper so `POST /reports/analyze` and `POST /reports/submit` share
    exactly the same inference logic instead of duplicating it.

    Streams stay separate (never merged) -- see `ml/potholes/arbitration.py`.
    A `ModelUnavailableError` from the pothole side is swallowed to an empty
    list here rather than raised, because a hawker-only image (or vice
    versa) is a legitimate "no pothole detected" outcome, not a failure --
    the caller decides what "nothing detected at all" means.
    """
    try:
        pothole_detections = pothole_detector.detect(image_path)
    except ModelUnavailableError:
        pothole_detections = []

    hawker_detections = hawker_detector(image_path)

    return pothole_detections, hawker_detections


@app.post("/reports/analyze", response_model=AnalyzeImageResponse)
async def analyze_report_image(
    file: UploadFile = File(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    db: Session = Depends(get_db),
    citizen: Citizen = Depends(get_current_citizen),
    pothole_detector: PotholeDetector = Depends(get_dual_pothole_detector),
    hawker_detector: Callable[[str | Path], list[dict]] = Depends(get_hawker_detector),
):
    """
    AI-analysis-only step of the citizen reporting flow.

        uploaded image
            -> persist image (reusable by POST /reports/submit via image_token)
            -> dual pothole detector (best.pt + best2.pt, arbitrated) +
               hawker detector, run separately and never merged
            -> best real detection across both streams (or none)
            -> (optional) Road Intelligence severity, if lat/lon given

    Deliberately does NOT create a `Defect` row -- see `POST /reports/submit`
    for that. Never defaults to "pothole" (or any category) when nothing was
    confidently detected: `category`/`confidence`/`bbox` come back `None`
    together in that case.
    """
    suffix = Path(file.filename or "").suffix or ".jpg"
    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file")

    ANALYZED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    image_path = ANALYZED_IMAGE_DIR / f"{token}{suffix}"
    image_path.write_bytes(image_bytes)

    pothole_detections, hawker_detections = _run_detectors(
        image_path, pothole_detector, hawker_detector
    )
    best = _best_detection(pothole_detections, hawker_detections)

    if best is None:
        return {
            "image_token": token,
            "imageToken": token,
            "category": None,
            "confidence": None,
            "bbox": None,
            "ai_severity": None,
            "ai_severity_score": None,
            "aiSeverity": None,
            "aiSeverityScore": None,
            "model_source": None,
            "modelSource": None,
        }

    class_name, confidence, bbox, image_width, image_height, hawker_raw = best

    model_source = (
        next(
            (d.model_source for d in pothole_detections if d.class_name == class_name and d.confidence == confidence),
            None,
        )
        if hawker_raw is None
        else "hawker-production.pt"
    )

    ai_severity = None
    ai_severity_score = None
    if latitude is not None and longitude is not None:
        try:
            analysis = road_intelligence_service.analyze(
                AnalyzeRequest(
                    detection=DetectionInput(
                        class_id=0,
                        class_name=class_name,
                        confidence=confidence,
                        bbox=bbox,
                        image_width=image_width,
                        image_height=image_height,
                    ),
                    context=RoadContext(latitude=latitude, longitude=longitude),
                )
            )
            ai_severity = analysis.severity.category.lower()
            ai_severity_score = analysis.severity.score
        except (InvalidDetectionError, InvalidContextError):
            pass  # AI severity is best-effort here; category/confidence/bbox still returned

    return {
        "image_token": token,
        "imageToken": token,
        "category": class_name,
        "confidence": confidence,
        "bbox": bbox,
        "ai_severity": ai_severity,
        "ai_severity_score": ai_severity_score,
        "aiSeverity": ai_severity,
        "aiSeverityScore": ai_severity_score,
        "model_source": model_source,
        "modelSource": model_source,
    }


def _resolve_analyzed_image(image_token: str) -> Path:
    """Find the image `POST /reports/analyze` persisted for this token."""
    if not image_token or "/" in image_token or ".." in image_token:
        raise HTTPException(status_code=422, detail="Invalid image_token")

    matches = sorted(ANALYZED_IMAGE_DIR.glob(f"{image_token}.*"))
    if not matches:
        raise HTTPException(
            status_code=404,
            detail="No analyzed image found for this image_token. Call POST /reports/analyze first.",
        )
    return matches[0]


@app.post("/reports/submit", response_model=ImageReportResponse)
def submit_report(
    request: SubmitReportRequest,
    db: Session = Depends(get_db),
    citizen: Citizen = Depends(get_current_citizen),
    pothole_detector: PotholeDetector = Depends(get_dual_pothole_detector),
    hawker_detector: Callable[[str | Path], list[dict]] = Depends(get_hawker_detector),
):
    """
    Final incident-creation step of the citizen reporting flow.

        image_token (from POST /reports/analyze) + citizen's final chosen
        category/severity + lat/lon
            -> re-run the same detector streams on the already-persisted
               image, to get AI metadata + a detection for AHP scoring
            -> existing Road Intelligence/AHP service (same pipeline as
               POST /reports/image)
            -> persisted Defect, owned by the authenticated citizen

    The citizen's chosen `defect_type`/`defect_severity` are always what get
    stored -- the AI result (if any) is stored as metadata (`ai_confidence`,
    `ai_bbox`, `ai_severity_score`) alongside it, never silently substituted.
    If Road Intelligence/AHP scoring is available for the re-detected image,
    `defect_priority` is populated exactly as `POST /reports/image` would;
    otherwise it stays `None`, same as `POST /reports` (no image/detection).
    """
    image_path = _resolve_analyzed_image(request.image_token)

    pothole_detections, hawker_detections = _run_detectors(
        image_path, pothole_detector, hawker_detector
    )
    best = _best_detection(pothole_detections, hawker_detections)

    ai_confidence = None
    ai_bbox = None
    ai_severity_score = None
    ai_model_source = None
    defect_priority = None

    if best is not None:
        class_name, confidence, bbox, image_width, image_height, hawker_raw = best
        ai_confidence = confidence
        ai_bbox = bbox
        ai_model_source = (
            next(
                (d.model_source for d in pothole_detections if d.class_name == class_name and d.confidence == confidence),
                None,
            )
            if hawker_raw is None
            else "hawker-production.pt"
        )

        try:
            analysis = road_intelligence_service.analyze(
                AnalyzeRequest(
                    detection=DetectionInput(
                        class_id=0,
                        class_name=class_name,
                        confidence=confidence,
                        bbox=bbox,
                        image_width=image_width,
                        image_height=image_height,
                    ),
                    context=RoadContext(latitude=request.latitude, longitude=request.longitude),
                )
            )
            ai_severity_score = analysis.severity.score
            defect_priority = analysis.priority.score
        except (InvalidDetectionError, InvalidContextError):
            pass  # citizen's own category/severity still gets stored below

    defect = Defect(
        defect_type=request.defect_type,
        defect_status="reported",
        defect_severity=request.defect_severity,
        defect_priority=defect_priority,
        latitude=request.latitude,
        longitude=request.longitude,
        image_path=str(image_path),
        citizen_id=citizen.id,
        ai_confidence=ai_confidence,
        ai_bbox=ai_bbox,
        ai_severity_score=ai_severity_score,
        ai_model_source=ai_model_source,
    )

    db.add(defect)
    db.flush()

    road_health_service.assign_defect_to_segment(db, defect)
    record_initial_status(db, defect)

    db.commit()
    db.refresh(defect)

    return _defect_detail(defect)


@app.get(
    "/defects",
    response_model=list[DefectResponseWithPriority],
)
def list_defects(
    db: Session = Depends(get_db),
):
    """
    Officer dashboard endpoint.

    Returns all persisted defects, including development/test rows where
    applicable.
    """
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


@app.get(
    "/defects/{defect_id}",
    response_model=DefectDetailResponse,
)
def get_defect_details(
    defect_id: int,
    db: Session = Depends(get_db),
    officer: Officer = Depends(get_current_officer),
):
    """
    Return details for one defect, including the reporting citizen's name
    (and email) via `reporter`.

    Officer-only: this response now carries citizen PII (see
    `schemas.ReporterPublic`), so unlike before it requires
    `Authorization: Bearer <officer access token>`. Public visibility
    filtering should use `GET /community/issues` instead, which never
    includes reporter identity.
    """
    defect = (
        db.query(Defect)
        .filter(Defect.id == defect_id)
        .first()
    )

    if defect is None:
        raise HTTPException(
            status_code=404,
            detail="Defect not found",
        )

    return _defect_detail(defect)


_PUBLIC_STATUSES = frozenset({STATUS_CONFIRMED, STATUS_IN_PROGRESS, STATUS_RESOLVED})


@app.get(
    "/community/issues",
    response_model=list[PublicIssueResponse],
)
def list_public_issues(db: Session = Depends(get_db)):
    """
    Citizen-facing community map: defects an officer has confirmed, are
    still being worked, or have been resolved.

    Deliberately excludes `reported` (not yet reviewed by an officer) and
    `rejected` (dismissed as not-a-defect) -- an unconfirmed or rejected
    report must never appear on the public map. See `GET /defects`
    (officer dashboard) for the unfiltered view.

    No authentication required -- this is the public read surface.
    """
    defects = (
        db.query(Defect)
        .filter(Defect.defect_status.in_(_PUBLIC_STATUSES))
        .order_by(Defect.id.desc())
        .all()
    )

    return [
        {
            "defect_id": defect.id,
            "defect_type": defect.defect_type,
            "defect_status": defect.defect_status,
            "defect_severity": defect.defect_severity,
            "latitude": defect.latitude,
            "longitude": defect.longitude,
            "road_segment_id": defect.road_segment.segment_id if defect.road_segment else None,
            "observation_count": 1,
            "defectId": defect.id,
            "defectType": defect.defect_type,
            "defectStatus": defect.defect_status,
            "defectSeverity": defect.defect_severity,
            "roadSegmentId": defect.road_segment.segment_id if defect.road_segment else None,
            "observationCount": 1,
        }
        for defect in defects
    ]


@app.post(
    "/road-intelligence/analyze",
    response_model=AnalyzeResponse,
)
def analyze_defect(
    request: AnalyzeRequest,
) -> AnalyzeResponse:
    try:
        return road_intelligence_service.analyze(request)
    except (InvalidDetectionError, InvalidContextError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )


@app.patch(
    "/defects/{defect_id}",
    response_model=DefectResponse,
)
def update_defect(
    defect_id: int,
    update: DefectStatusUpdate,
    db: Session = Depends(get_db),
    officer: Officer = Depends(get_current_officer),
):
    """
    Existing backwards-compatible status-update endpoint.
    """
    defect = (
        db.query(Defect)
        .filter(Defect.id == defect_id)
        .first()
    )

    if defect is None:
        raise HTTPException(
            status_code=404,
            detail="Defect not found",
        )

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


@app.patch(
    "/defects/{defect_id}/status",
    response_model=DefectDetailResponse,
)
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

        {
            "status": "confirmed",
            "note": "Verified by municipal officer"
        }

    The authenticated officer's id is always used for the audit record.
    """
    defect = (
        db.query(Defect)
        .filter(Defect.id == defect_id)
        .first()
    )

    if defect is None:
        raise HTTPException(
            status_code=404,
            detail="Defect not found",
        )

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


@app.patch(
    "/defects/{defect_id}/severity",
    response_model=DefectDetailResponse,
)
def update_defect_severity(
    defect_id: int,
    request: DefectSeverityUpdate,
    db: Session = Depends(get_db),
    officer: Officer = Depends(get_current_officer),
):
    """
    Officer-only severity update.

        PATCH /defects/12/severity
        Authorization: Bearer <officer access token>

        {"defect_severity": "critical"}

    Only `defect_severity` is changed; status and all other fields are
    left untouched.
    """
    defect = (
        db.query(Defect)
        .filter(Defect.id == defect_id)
        .first()
    )

    if defect is None:
        raise HTTPException(
            status_code=404,
            detail="Defect not found",
        )

    defect.defect_severity = request.defect_severity

    db.commit()
    db.refresh(defect)

    return _defect_detail(defect)


@app.get(
    "/defects/{defect_id}/status-history",
    response_model=list[StatusHistoryEntry],
)
def get_defect_status_history(
    defect_id: int,
    db: Session = Depends(get_db),
):
    """
    Full status timeline for a defect, oldest first.
    """
    defect = (
        db.query(Defect)
        .filter(Defect.id == defect_id)
        .first()
    )

    if defect is None:
        raise HTTPException(
            status_code=404,
            detail="Defect not found",
        )

    return [
        {
            "id": entry.id,
            "defect_id": entry.defect_id,
            "old_status": entry.old_status,
            "new_status": entry.new_status,
            "changed_by": entry.changed_by,
            "changed_at": to_ist(entry.changed_at),
            "note": entry.note,
            "defectId": entry.defect_id,
            "oldStatus": entry.old_status,
            "newStatus": entry.new_status,
            "changedBy": entry.changed_by,
            "changedAt": to_ist(entry.changed_at),
        }
        for entry in defect.status_history
    ]


@app.post("/ml/hawkers/detect", response_model=HawkerDetectionResponse)
async def detect_hawkers(
    latitude: float = Form(...),
    longitude: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    citizen: Citizen = Depends(get_current_citizen),
    detector: Callable[[str | Path], list[dict]] = Depends(get_hawker_detector),
):
    """
    Image pipeline for authenticated citizen hawker/street-vendor reports.

    Follows the same pattern as `POST /reports/image`
    (upload -> persist image -> YOLO detect -> DetectionInput -> existing
    Road Intelligence/AHP service -> severity + priority -> persisted
    Defect linked to citizen), except that EVERY detection in the image
    becomes its own Defect, not just the highest-confidence one -- a
    single hawker photo can legitimately show several vendors.

    Severity/priority is analyzed for every detection BEFORE any Defect is
    written, so an invalid detection (422) never leaves a partial batch of
    Defects committed. All Defects from one image are written in a single
    DB transaction: the whole batch commits together, or none of it does.
    """
    suffix = Path(file.filename or "").suffix or ".jpg"
    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Empty image file",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    image_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    image_path.write_bytes(image_bytes)

    detections = detector(image_path)

    if not detections:
        raise HTTPException(
            status_code=422,
            detail="No hawkers detected in the uploaded image.",
        )

    # Validate + score every detection up front, before touching the DB, so
    # one bad detection can never leave a partial batch of Defects behind.
    analyzed: list[tuple[dict, AnalyzeResponse]] = []
    for detection in detections:
        try:
            detection_input = DetectionInput(
                class_id=detection["class_id"],
                class_name=detection["class_name"],
                confidence=detection["confidence"],
                bbox=detection["bbox"],
                image_width=detection.get("image_width"),
                image_height=detection.get("image_height"),
            )
            analysis = road_intelligence_service.analyze(
                AnalyzeRequest(
                    detection=detection_input,
                    context=RoadContext(
                        latitude=latitude,
                        longitude=longitude,
                    ),
                )
            )
        except (ValidationError, InvalidDetectionError, InvalidContextError) as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            )
        analyzed.append((detection, analysis))

    response_items = []

    try:
        for detection, analysis in analyzed:
            defect = Defect(
                defect_type=detection["class_name"],
                defect_status="reported",
                defect_severity=analysis.severity.category.lower(),
                defect_priority=analysis.priority.score,
                latitude=latitude,
                longitude=longitude,
                image_path=str(image_path),
                citizen_id=citizen.id,
            )

            db.add(defect)
            db.flush()

            road_health_service.assign_defect_to_segment(db, defect)
            record_initial_status(db, defect)

            response_items.append((defect, detection, analysis))

        db.commit()
    except Exception:
        # One image can create several Defects (one per detection) -- if
        # persistence fails partway through, roll back the whole batch
        # rather than leaving some detections committed and others not.
        db.rollback()
        raise

    for defect, _, _ in response_items:
        db.refresh(defect)

    return {
        "filename": file.filename,
        "detections": [
            {
                "defect_id": defect.id,
                "class_name": detection["class_name"],
                "confidence": detection["confidence"],
                "bbox": detection["bbox"],
                "defect_severity": defect.defect_severity,
                "severity_score": analysis.severity.score,
                "defect_priority": defect.defect_priority,
                "latitude": defect.latitude,
                "longitude": defect.longitude,
                "road_segment_id": defect.road_segment.segment_id if defect.road_segment else None,
                "image_path": defect.image_path,
                "defectId": defect.id,
                "className": detection["class_name"],
                "defectSeverity": defect.defect_severity,
                "severityScore": analysis.severity.score,
                "defectPriority": defect.defect_priority,
                "roadSegmentId": defect.road_segment.segment_id if defect.road_segment else None,
                "imagePath": defect.image_path,
            }
            for defect, detection, analysis in response_items
        ],
    }