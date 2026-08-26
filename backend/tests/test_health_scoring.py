"""
Health scoring: the formula, the band boundaries, and the rule that resolved
issues stop contributing to current degradation.
"""

from __future__ import annotations

import pytest

from backend.app.road_health import config
from backend.app.road_health.scoring import (
    DefectLoad,
    active_issue_load,
    calculate_health_score,
    classify_health,
    evaluate_segment,
    severity_weight,
)


# ---------------------------------------------------------------------------
# Severity weighting
# ---------------------------------------------------------------------------
def test_severity_weights_match_the_specified_scale():
    assert severity_weight("critical") == 3.0
    assert severity_weight("medium") == 2.0
    assert severity_weight("low") == 1.0


def test_severity_weighting_is_case_insensitive():
    assert severity_weight("CRITICAL") == severity_weight("critical")
    assert severity_weight("  Medium ") == severity_weight("medium")


def test_unknown_severity_uses_the_documented_fallback():
    assert severity_weight("banana") == config.UNKNOWN_SEVERITY_WEIGHT


# ---------------------------------------------------------------------------
# D. Active issues degrade health; resolved ones do not
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "status",
    ["reported", "confirmed", "confirmed", "in_progress", "in_progress"],
)
def test_every_active_status_contributes_to_the_load(status):
    assert active_issue_load([DefectLoad(status=status, severity="critical")]) == 3.0


@pytest.mark.parametrize("status", ["resolved", "rejected"])
def test_resolved_and_rejected_defects_contribute_nothing(status):
    assert active_issue_load([DefectLoad(status=status, severity="critical")]) == 0.0


def test_resolving_a_defect_improves_the_score():
    length_km = 10.0
    defects = [DefectLoad(status="confirmed", severity="critical") for _ in range(3)]

    before = evaluate_segment(defects, length_km)

    defects[0] = DefectLoad(status="resolved", severity="critical")
    after = evaluate_segment(defects, length_km)

    assert after.health_score > before.health_score
    assert after.active_issues == before.active_issues - 1
    assert after.resolved_issues == 1
    assert after.total_issues == before.total_issues  # nothing was deleted


def test_a_segment_of_only_resolved_defects_scores_a_perfect_ten():
    result = evaluate_segment(
        [DefectLoad(status="resolved", severity="critical") for _ in range(20)],
        10.0,
    )

    assert result.health_score == 10.0
    assert result.health_status == config.HEALTH_STATUS_HEALTHY
    assert result.active_issues == 0
    assert result.resolved_issues == 20


# ---------------------------------------------------------------------------
# The formula is severity-weighted and length-normalized
# ---------------------------------------------------------------------------
def test_score_is_not_ten_minus_the_defect_count():
    # Four active low-severity defects: `10 - count` would give 6.0.
    result = evaluate_segment(
        [DefectLoad(status="reported", severity="low") for _ in range(4)],
        10.0,
    )

    assert result.health_score != 6.0
    assert result.health_score == pytest.approx(7.1, abs=0.05)


def test_a_critical_defect_hurts_more_than_a_low_one():
    critical = evaluate_segment([DefectLoad("reported", "critical")], 10.0)
    low = evaluate_segment([DefectLoad("reported", "low")], 10.0)

    assert critical.health_score < low.health_score


def test_the_same_load_spread_over_a_longer_road_scores_better():
    defects = [DefectLoad("reported", "critical") for _ in range(6)]

    short = evaluate_segment(defects, 2.0)
    long = evaluate_segment(defects, 20.0)

    assert long.health_score > short.health_score


def test_score_decreases_monotonically_as_active_load_grows():
    scores = [calculate_health_score(load, 10.0) for load in range(0, 40, 2)]

    assert scores == sorted(scores, reverse=True)


def test_score_never_leaves_the_zero_to_ten_range():
    for load in [0.0, 1.0, 50.0, 5_000.0, 1_000_000.0]:
        score = calculate_health_score(load, 1.0)
        assert 0.0 <= score <= 10.0


# ---------------------------------------------------------------------------
# E. Band boundaries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "score,expected",
    [
        (10.0, config.HEALTH_STATUS_HEALTHY),
        (7.2, config.HEALTH_STATUS_HEALTHY),
        (7.1, config.HEALTH_STATUS_HEALTHY),
        (7.0, config.HEALTH_STATUS_NEEDS_ATTENTION),
        (6.9, config.HEALTH_STATUS_NEEDS_ATTENTION),
        (4.1, config.HEALTH_STATUS_NEEDS_ATTENTION),
        (4.0, config.HEALTH_STATUS_NEEDS_ATTENTION),
        (3.9, config.HEALTH_STATUS_CRITICAL),
        (0.0, config.HEALTH_STATUS_CRITICAL),
    ],
)
def test_band_boundaries(score, expected):
    assert classify_health(score) == expected


@pytest.mark.parametrize(
    "load,length_km,expected_score,expected_band",
    [
        # Chosen so the formula lands exactly on each boundary value.
        (3.0, 7.0, 7.0, config.HEALTH_STATUS_NEEDS_ATTENTION),
        (3.0, 7.3448, 7.1, config.HEALTH_STATUS_HEALTHY),
        (6.0, 4.0, 4.0, config.HEALTH_STATUS_NEEDS_ATTENTION),
        (6.0, 3.836, 3.9, config.HEALTH_STATUS_CRITICAL),
    ],
)
def test_boundaries_are_reachable_through_the_real_formula(
    load, length_km, expected_score, expected_band
):
    score = calculate_health_score(load, length_km)

    assert score == expected_score
    assert classify_health(score) == expected_band


# ---------------------------------------------------------------------------
# Counting conventions
# ---------------------------------------------------------------------------
def test_issue_counts_add_up():
    result = evaluate_segment(
        [
            DefectLoad("reported", "critical"),
            DefectLoad("confirmed", "medium"),
            DefectLoad("in_progress", "low"),
            DefectLoad("resolved", "critical"),
            DefectLoad("rejected", "medium"),
        ],
        10.0,
    )

    assert result.total_issues == 5
    assert result.active_issues == 3
    assert result.resolved_issues == 1
    assert result.rejected_issues == 1
    assert result.total_issues == (
        result.active_issues + result.resolved_issues + result.rejected_issues
    )

    # The frontend contract: the severity split covers the ACTIVE issues.
    assert result.critical_issues == 1
    assert result.medium_issues == 1
    assert result.low_issues == 1
    assert (
        result.critical_issues + result.medium_issues + result.low_issues
        == result.active_issues
    )


def test_high_severity_is_counted_as_critical():
    result = evaluate_segment([DefectLoad("reported", "high")], 10.0)

    assert result.critical_issues == 1
    assert result.active_load == 3.0


def test_the_formula_is_configurable(monkeypatch):
    baseline = calculate_health_score(3.0, 10.0)

    # Halving the half-health constant makes the scoring twice as harsh
    # without a line of logic changing.
    monkeypatch.setattr(config, "HALF_HEALTH_LOAD_DENSITY", 0.5)
    harsher = calculate_health_score(3.0, 10.0)

    assert harsher < baseline

    monkeypatch.setattr(config, "SEVERITY_WEIGHTS", {"critical": 10.0, "medium": 2.0, "low": 1.0})
    assert severity_weight("critical") == 10.0
