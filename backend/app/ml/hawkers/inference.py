from pathlib import Path

from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "weights" / "production.pt"

_model = None


def get_model() -> YOLO:
    """
    Load the hawker model once and reuse it.
    """
    global _model

    if _model is None:
        _model = YOLO(MODEL_PATH)

    return _model


def predict(image_path: str | Path) -> list[dict]:
    """
    Run hawker detection on an image.

    Returns:
        A list of detections containing:
        - class_id
        - class_name
        - confidence
        - bbox [x1, y1, x2, y2]
    """
    model = get_model()

    results = model(str(image_path))

    detections = []

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append(
                {
                    "class_id": class_id,
                    "class_name": model.names[class_id],
                    "confidence": round(confidence, 4),
                    "bbox": [
                        round(x1, 2),
                        round(y1, 2),
                        round(x2, 2),
                        round(y2, 2),
                    ],
                }
            )

    return detections
