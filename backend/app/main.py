from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pathlib import Path
import tempfile

from .database import SessionLocal
from .models import Defect
from .schemas import ReportCreate, DefectResponse, DefectStatusUpdate
from .road_intelligence.schemas import AnalyzeRequest, AnalyzeResponse
from .road_intelligence import service as road_intelligence_service
from .road_intelligence.severity import InvalidDetectionError
from .road_intelligence.scoring import InvalidContextError
from .ml.hawkers.inference import predict

app = FastAPI(title="Road-Defect Backend")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
):
    defect = db.query(Defect).filter(Defect.id == defect_id).first()

    if defect is None:
        raise HTTPException(status_code=404, detail="Defect not found")

    defect.defect_status = update.defect_status

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
