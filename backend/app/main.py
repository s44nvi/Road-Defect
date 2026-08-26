from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session
from pathlib import Path
import tempfile

from .dependencies import get_db
from .defect_workflow import (
    InvalidStatusError,
    InvalidTransitionError,
    apply_status_change,
    record_initial_status,
)
from .models import Defect
from .schemas import (
    DefectDetailResponse,
    DefectResponse,
    DefectStatusChangeRequest,
    DefectStatusUpdate,
    ReportCreate,
)
from .road_health import service as road_health_service
from .road_health.router import router as road_health_router
from .road_health.schemas import StatusHistoryEntry
from .road_intelligence.schemas import AnalyzeRequest, AnalyzeResponse
from .road_intelligence import service as road_intelligence_service
from .road_intelligence.severity import InvalidDetectionError
from .road_intelligence.scoring import InvalidContextError
from .ml.hawkers.inference import predict

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


@app.post("/reports", response_model=DefectResponse)
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
    }


@app.get("/defects", response_model=list[DefectResponse])
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
    x_officer_id: str | None = Header(default=None, alias="X-Officer-Id"),
):
    """
    Existing status-update endpoint, kept backwards compatible.

    Same path, same request field (`defect_status`), same response shape, so
    the officer UI's existing Confirm/Reject buttons keep working unchanged.
    What is new is that the change is now validated against the workflow and
    recorded in `defect_status_history` instead of silently overwriting the
    status.

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
        changed_by=update.changed_by or x_officer_id,
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
    x_officer_id: str | None = Header(default=None, alias="X-Officer-Id"),
):
    """
    Officer status update with full workflow validation.

        PATCH /defects/12/status
        {"status": "confirmed", "note": "Verified by municipal officer"}

    Validates the status against the allowed vocabulary, validates the
    transition against the workflow graph, records a `defect_status_history`
    row, updates the defect, and returns it. The status change and its history
    row are committed in one transaction.

    Road health is not recomputed here because it is never stored -- the
    road-health endpoints derive it from current defect rows on every request,
    so a status change is reflected immediately with no cache to invalidate.

    `changed_by` may come from the request body or an `X-Officer-Id` header.
    This project has no authentication layer, so it is nullable rather than
    derived from an authenticated identity; see `defect_workflow`.
    """
    defect = db.query(Defect).filter(Defect.id == defect_id).first()

    if defect is None:
        raise HTTPException(status_code=404, detail="Defect not found")

    _apply_status(
        db,
        defect,
        status=request.status,
        note=request.note,
        changed_by=request.changed_by or x_officer_id,
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
