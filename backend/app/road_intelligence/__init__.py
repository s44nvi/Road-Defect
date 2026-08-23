"""
Road Intelligence module: YOLO detection -> severity estimation -> AHP
priority scoring.

Public entry point for FastAPI:
    from road_intelligence.service import analyze
    from road_intelligence.schemas import AnalyzeRequest, AnalyzeResponse

Core logic (no pydantic dependency, independently testable):
    from road_intelligence import severity, ahp, scoring
"""

__all__ = ["severity", "ahp", "scoring", "service", "schemas", "config"]
