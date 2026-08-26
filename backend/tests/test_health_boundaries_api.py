"""
API-level verification of the exact health-band boundaries, using real
segments/defects through GET /road-health/segments and
GET /road-health/segments/{segment_id} rather than calling the scoring
function directly (that is already covered in test_health_scoring.py).

Required boundary behaviour:
    score == 7.0  -> needs_attention (ORANGE)
    score == 7.1  -> healthy         (GREEN)
    score == 4.0  -> needs_attention (ORANGE)
    score == 3.9  -> critical        (RED)

Each case uses one active 'critical' defect (weight 3) on a segment whose
`length_km` is chosen so the formula lands exactly on the target score --
the same load/length pairs already proven analytically in
test_health_scoring.py::test_boundaries_are_reachable_through_the_real_formula.
"""

from __future__ import annotations

LINE = [[72.80, 19.00], [72.81, 19.00], [72.82, 19.00]]


def _segment_properties(client, segment_id):
    body = client.get("/road-health/segments").json()
    return next(f["properties"] for f in body["features"] if f["properties"]["segment_id"] == segment_id)


def test_score_of_exactly_7_point_0_is_orange_needs_attention(client, make_segment, make_defect):
    segment = make_segment("SEG-70", LINE, length_km=7.0)
    make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)

    result = _segment_properties(client, "SEG-70")

    assert result["health_score"] == 7.0
    assert result["health_status"] == "needs_attention"
    assert result["health_color"] == "orange"


def test_score_of_exactly_7_point_1_is_green_healthy(client, make_segment, make_defect):
    segment = make_segment("SEG-71", LINE, length_km=7.3448)
    make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)

    result = _segment_properties(client, "SEG-71")

    assert result["health_score"] == 7.1
    assert result["health_status"] == "healthy"
    assert result["health_color"] == "green"


def test_score_of_exactly_4_point_0_is_orange_needs_attention(client, make_segment, make_defect):
    segment = make_segment("SEG-40", LINE, length_km=4.0)
    make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)
    make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)

    result = _segment_properties(client, "SEG-40")

    assert result["health_score"] == 4.0
    assert result["health_status"] == "needs_attention"
    assert result["health_color"] == "orange"


def test_score_of_exactly_3_point_9_is_red_critical(client, make_segment, make_defect):
    segment = make_segment("SEG-39", LINE, length_km=3.836)
    make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)
    make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)

    result = _segment_properties(client, "SEG-39")

    assert result["health_score"] == 3.9
    assert result["health_status"] == "critical"
    assert result["health_color"] == "red"


def test_boundaries_hold_on_the_segment_detail_endpoint_too(client, make_segment, make_defect):
    segment = make_segment("SEG-70D", LINE, length_km=7.0)
    make_defect(19.0, 72.805, severity="critical", status="reported", segment=segment)

    detail = client.get("/road-health/segments/SEG-70D").json()

    assert detail["health_score"] == 7.0
    assert detail["health_status"] == "needs_attention"
