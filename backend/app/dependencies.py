"""
dependencies.py
===============
Shared FastAPI dependencies.

`get_db` lives here rather than in `main.py` so routers (e.g.
`road_health.router`) can depend on it without importing the application
module and creating an import cycle. `main.py` re-exports it, so any existing
`from .main import get_db` keeps working.
"""

from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from .database import SessionLocal
from .ml.potholes.detector import PotholeDetector, get_default_detector


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_pothole_detector() -> PotholeDetector:
    """
    FastAPI dependency for the pothole detector integration boundary.

    Returns the placeholder (`UnavailablePotholeDetector`) until Harmeet's
    real model is wired into `app.ml.potholes.detector.get_default_detector`.
    Tests override this dependency with a mock to exercise the pipeline
    without a real model artifact.
    """
    return get_default_detector()
