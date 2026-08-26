"""
Shared pytest fixtures for the backend test suite.

Tests run against a throwaway SQLite file (one per test, via the
`DATABASE_URL` override supported by `backend/app/database.py`) so the suite
never touches a development or production PostgreSQL database.

Note on schema creation: the tests build the schema with
`Base.metadata.create_all()`. That is a *test* convenience, not the schema
management strategy -- the real schema is owned by the Alembic migrations in
`backend/alembic/versions/`. SQLite cannot execute the existing baseline
migration (it adds a FOREIGN KEY to an existing table, which SQLite's ALTER
does not support), so the migrations are verified separately against a real
PostgreSQL instance.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    """A SQLAlchemy session bound to a fresh, isolated SQLite database."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    # Re-import the app modules so they pick up the patched DATABASE_URL.
    for module in [m for m in list(sys.modules) if m.startswith("backend.app")]:
        del sys.modules[module]

    from backend.app.database import Base, SessionLocal, engine
    from backend.app import models  # noqa: F401  (registers the tables)

    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """A FastAPI TestClient wired to the same session as `db_session`."""
    from fastapi.testclient import TestClient

    from backend.app.dependencies import get_db
    from backend.app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def dev_officer(db_session):
    """
    A single active officer row, for tests that need a real authenticated
    principal. Password is hashed exactly the way `seed_dev_officer.py` and
    `POST /auth/officer/login` do -- no plaintext ever touches the row.
    """
    from backend.app.auth.security import hash_password
    from backend.app.models import Officer

    officer = Officer(
        name="Test Officer",
        email="officer@example.com",
        password_hash=hash_password("correct-horse-battery-staple"),
        department="Test Municipality",
        is_active=True,
    )

    db_session.add(officer)
    db_session.commit()
    db_session.refresh(officer)

    return officer


@pytest.fixture()
def officer_token(dev_officer):
    """A valid access token for `dev_officer`."""
    from backend.app.auth.service import issue_officer_token

    return issue_officer_token(dev_officer)


@pytest.fixture()
def officer_client(client, officer_token):
    """
    The shared `client` fixture, pre-authenticated as `dev_officer` via a
    bearer token on every request. Existing tests that exercise officer-only
    routes (PATCH /defects/{id}, PATCH /defects/{id}/status) use this
    instead of the bare `client` fixture now that those routes require
    authentication; tests of public routes are unaffected.
    """
    client.headers.update({"Authorization": f"Bearer {officer_token}"})
    return client


@pytest.fixture()
def dev_citizen(db_session):
    """A single active citizen row, for citizen-auth tests."""
    from backend.app.auth.security import hash_password
    from backend.app.models import Citizen

    citizen = Citizen(
        name="Test Citizen",
        email="citizen@example.com",
        password_hash=hash_password("citizen-password-123"),
        is_active=True,
    )

    db_session.add(citizen)
    db_session.commit()
    db_session.refresh(citizen)

    return citizen


@pytest.fixture()
def citizen_token(dev_citizen):
    """A valid access token for `dev_citizen`."""
    from backend.app.auth.service import issue_citizen_token

    return issue_citizen_token(dev_citizen)


@pytest.fixture()
def corridors():
    """The bundled development corridor FeatureCollection."""
    path = (
        REPO_ROOT
        / "backend"
        / "app"
        / "road_health"
        / "data"
        / "mumbai_corridors.geojson"
    )

    with path.open() as handle:
        return json.load(handle)


@pytest.fixture()
def make_segment(db_session):
    """Factory for road segments with explicit geometry and length."""

    def _make(
        segment_id: str,
        coordinates: list[list[float]],
        length_km: float | None = None,
        road_name: str = "Test Road",
        segment_label: str | None = None,
        geometry_source: str = "dev_approximate_v1",
    ):
        from backend.app.models import RoadSegment
        from backend.app.road_health.geo import linestring, linestring_length_km

        segment = RoadSegment(
            segment_id=segment_id,
            road_name=road_name,
            segment_label=segment_label or f"{road_name} - {segment_id}",
            geometry=linestring(coordinates),
            length_km=(
                linestring_length_km(coordinates) if length_km is None else length_km
            ),
            geometry_source=geometry_source,
        )

        db_session.add(segment)
        db_session.commit()
        db_session.refresh(segment)

        return segment

    return _make


@pytest.fixture()
def make_defect(db_session):
    """Factory for defects, optionally attached to a segment."""

    def _make(
        latitude: float,
        longitude: float,
        severity: str = "medium",
        status: str = "reported",
        defect_type: str = "pothole",
        segment=None,
        is_test_data: bool = False,
    ):
        from backend.app.models import Defect

        defect = Defect(
            defect_type=defect_type,
            defect_status=status,
            defect_severity=severity,
            latitude=latitude,
            longitude=longitude,
            road_segment_id=segment.id if segment is not None else None,
            is_test_data=is_test_data,
        )

        db_session.add(defect)
        db_session.commit()
        db_session.refresh(defect)

        return defect

    return _make
