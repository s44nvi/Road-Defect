"""
Road Health module: road segments -> severity-weighted active issue load ->
0-10 health score -> health band -> GeoJSON for the officer frontend.

This module is deliberately separate from `road_intelligence` (severity
estimation + AHP repair-priority scoring for a *single* detection). Road
Health answers a different question: "how degraded is this stretch of road
right now, given every defect currently sitting on it?"

Public entry points:
    from backend.app.road_health.router import router      # FastAPI routes
    from backend.app.road_health import service            # DB aggregation
    from backend.app.road_health import scoring, geo       # pure logic

`geo.py` and `scoring.py` have no SQLAlchemy/FastAPI dependency by design,
so they are independently unit-testable.
"""

__all__ = ["config", "geo", "scoring", "assignment", "service", "schemas", "router"]
