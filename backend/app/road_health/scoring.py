"""
scoring.py
==========
Pure-Python road health scoring. No SQLAlchemy, no FastAPI, no pydantic --
it takes plain `(status, severity)` pairs plus a segment length and returns a
health score, band, and issue counts.

Every constant lives in `config.py`; this file only applies them.

The formula
-----------
    active_load  = sum of SEVERITY_WEIGHTS[severity] over ACTIVE defects
    density      = active_load / max(length_km, MIN_NORMALIZATION_LENGTH_KM)
    penalty      = MAX_HEALTH_SCORE * density / (density + HALF_HEALTH_LOAD_DENSITY)
    score        = round(MAX_HEALTH_SCORE - penalty, HEALTH_SCORE_DECIMALS)

Properties this buys us, all of which are asserted in the test suite:

  * The score is severity-weighted and length-normalized, so it is NOT
    `10 - number_of_defects`.
  * It is strictly decreasing in active load: adding any active defect can
    only lower the score, and a critical one lowers it more than a low one.
  * Resolved and rejected defects carry zero weight, so repairing a road
    always improves its score.
  * The saturating (rational) shape keeps the result inside (0, 10] for any
    load, however extreme -- no clamping cliff where every bad road collapses
    onto the same number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from . import config


@dataclass(frozen=True)
class DefectLoad:
    """The only two defect attributes health scoring cares about."""

    status: str
    severity: str


@dataclass(frozen=True)
class HealthResult:
    """Outcome of scoring one road segment."""

    health_score: float
    health_status: str
    health_color: str
    active_load: float
    load_density: float
    total_issues: int
    active_issues: int
    resolved_issues: int
    rejected_issues: int
    critical_issues: int
    medium_issues: int
    low_issues: int
    severity_breakdown: dict[str, float] = field(default_factory=dict)


def normalize_status(status: str | None) -> str:
    """Lowercase/strip a status for comparison. Never raises."""
    return (status or "").strip().lower()


def normalize_severity(severity: str | None) -> str:
    """Lowercase/strip a severity for comparison. Never raises."""
    return (severity or "").strip().lower()


def is_active(status: str | None) -> bool:
    """True when the defect still degrades the road right now."""
    return normalize_status(status) in config.ACTIVE_STATUSES


def severity_weight(severity: str | None) -> float:
    """Severity -> issue-load weight (critical 3, medium 2, low 1)."""
    return config.SEVERITY_WEIGHTS.get(
        normalize_severity(severity),
        config.UNKNOWN_SEVERITY_WEIGHT,
    )


def severity_bucket(severity: str | None) -> str:
    """Severity -> reported count bucket ('critical' | 'medium' | 'low')."""
    return config.SEVERITY_BUCKETS.get(
        normalize_severity(severity),
        config.UNKNOWN_SEVERITY_BUCKET,
    )


def active_issue_load(defects: Iterable[DefectLoad]) -> float:
    """Severity-weighted load of the ACTIVE defects only."""
    return sum(severity_weight(d.severity) for d in defects if is_active(d.status))


def calculate_health_score(active_load: float, length_km: float) -> float:
    """
    Severity-weighted active load + segment length -> health score in (0, 10].

    Length normalization is what turns a raw load into a comparable density:
    the same six active critical defects mean something very different on a
    2 km segment than on a 20 km one.
    """
    if active_load < 0.0:
        raise ValueError("active_load cannot be negative")

    effective_length = max(float(length_km), config.MIN_NORMALIZATION_LENGTH_KM)
    density = active_load / effective_length

    penalty = (
        config.MAX_HEALTH_SCORE
        * density
        / (density + config.HALF_HEALTH_LOAD_DENSITY)
    )

    return round(config.MAX_HEALTH_SCORE - penalty, config.HEALTH_SCORE_DECIMALS)


def classify_health(health_score: float) -> str:
    """
    Health score -> band, applied to the ROUNDED score so boundaries are exact.

        score > 7.0          -> healthy          (GREEN)
        4.0 <= score <= 7.0  -> needs_attention  (ORANGE)
        score < 4.0          -> critical         (RED)
    """
    if health_score > config.HEALTHY_THRESHOLD:
        return config.HEALTH_STATUS_HEALTHY

    if health_score >= config.NEEDS_ATTENTION_THRESHOLD:
        return config.HEALTH_STATUS_NEEDS_ATTENTION

    return config.HEALTH_STATUS_CRITICAL


def health_color(health_status: str) -> str:
    """Band -> display colour ('green' | 'orange' | 'red')."""
    return config.HEALTH_STATUS_COLORS.get(health_status, "")


def evaluate_segment(
    defects: Iterable[DefectLoad],
    length_km: float,
) -> HealthResult:
    """
    Score one road segment from its defects.

    Counting conventions (chosen to match the officer frontend contract, where
    `critical + medium + low == active_issues`):

      * `total_issues`     -- every defect on the segment, whatever its status.
      * `active_issues`    -- defects in an ACTIVE status (still degrading).
      * `resolved_issues`  -- defects repaired.
      * `rejected_issues`  -- reports dismissed as not-a-defect.
      * `critical/medium/low_issues` -- severity split of the ACTIVE defects
        only, since those are the ones an officer can still act on.

    So `total == active + resolved + rejected` and
    `critical + medium + low == active`.
    """
    defects = list(defects)

    active = [d for d in defects if is_active(d.status)]

    resolved_count = sum(
        1 for d in defects if normalize_status(d.status) in config.RESOLVED_STATUSES
    )
    rejected_count = sum(
        1 for d in defects if normalize_status(d.status) in config.REJECTED_STATUSES
    )

    buckets = {"critical": 0, "medium": 0, "low": 0}
    breakdown: dict[str, float] = {}

    for defect in active:
        bucket = severity_bucket(defect.severity)
        buckets[bucket] = buckets.get(bucket, 0) + 1
        breakdown[bucket] = breakdown.get(bucket, 0.0) + severity_weight(defect.severity)

    load = active_issue_load(active)
    effective_length = max(float(length_km), config.MIN_NORMALIZATION_LENGTH_KM)
    score = calculate_health_score(load, length_km)
    status = classify_health(score)

    return HealthResult(
        health_score=score,
        health_status=status,
        health_color=health_color(status),
        active_load=round(load, 4),
        load_density=round(load / effective_length, 4),
        total_issues=len(defects),
        active_issues=len(active),
        resolved_issues=resolved_count,
        rejected_issues=rejected_count,
        critical_issues=buckets["critical"],
        medium_issues=buckets["medium"],
        low_issues=buckets["low"],
        severity_breakdown={k: round(v, 4) for k, v in sorted(breakdown.items())},
    )
