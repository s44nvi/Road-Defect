"""
Regression test: recurrence must influence priority/AHP scoring, but must
NEVER retroactively change the independently-computed severity score.

This guards against conflating "number of citizen reports for the same
defect" with "how bad the defect is" — the two are deliberately separate
inputs into the system (see road_intelligence/scoring.py and severity.py).
"""

from backend.app.road_intelligence.scoring import ContextData, calculate_priority
from backend.app.road_intelligence.severity import DetectionData, compute_bbox_geometry, estimate_severity


def _detection() -> DetectionData:
    return DetectionData(
        class_id=0,
        class_name="pothole",
        confidence=0.85,
        bbox=(10.0, 10.0, 60.0, 60.0),
        image_width=640,
        image_height=480,
    )


def test_higher_recurrence_count_increases_priority_contribution():
    detection = _detection()
    severity = estimate_severity(detection)
    geometry = compute_bbox_geometry(detection)

    base_ctx = ContextData(recurrence_count=0)
    high_ctx = ContextData(recurrence_count=10)

    base_result = calculate_priority(severity, geometry, base_ctx)
    high_result = calculate_priority(severity, geometry, high_ctx)

    # Recurrence criterion's own contribution must strictly increase.
    assert high_result.breakdown.recurrence.contribution > base_result.breakdown.recurrence.contribution
    assert high_result.breakdown.recurrence.raw_value == 10.0
    assert base_result.breakdown.recurrence.raw_value == 0.0

    # Overall priority score must not decrease as recurrence rises (all
    # other criteria held constant), and should increase since recurrence
    # carries a positive AHP weight.
    assert high_result.score > base_result.score


def test_recurrence_count_does_not_change_severity_score():
    detection = _detection()
    severity = estimate_severity(detection)

    # Severity is computed purely from the detection (class, confidence,
    # bbox geometry) with NO knowledge of recurrence_count at all -- the
    # function signature doesn't even accept it. Prove that varying
    # recurrence_count in the priority layer never touches the severity
    # result object computed upstream.
    geometry = compute_bbox_geometry(detection)

    for recurrence_count in (0, 1, 5, 50):
        ctx = ContextData(recurrence_count=recurrence_count)
        result = calculate_priority(severity, geometry, ctx)
        # The severity criterion inside the priority breakdown is derived
        # solely from `severity.score`, unaffected by recurrence_count.
        assert result.breakdown.severity.raw_value == severity.score
        assert result.breakdown.severity.normalized_value == round(severity.score / 100.0, 4)

    # And the SeverityResult object itself is never mutated/recomputed.
    assert severity.score == estimate_severity(detection).score
