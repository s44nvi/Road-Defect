"""
defect_workflow.py
==================
The controlled defect status workflow: which statuses exist, which transitions
are legal, and how a status change is applied so that it is always recorded in
`defect_status_history`.

Every status change in the application goes through `apply_status_change()`.
Nothing else should assign to `Defect.defect_status` directly -- that is what
guarantees the officer timeline has no gaps.

Where the status vocabulary lives
---------------------------------
The status constants themselves live in `road_health/config.py`, next to
`ACTIVE_STATUSES`, because road health scoring is what gives "active" its
meaning. `road_health.config` imports nothing, so there is no import cycle.

Authentication
--------------
Officer authentication lives in `app/auth/` (JWT issued by
`POST /auth/officer/login`, verified by `Depends(get_current_officer)`).
`main.py` derives `changed_by` from that authenticated officer's id -- never
from a client-supplied `X-Officer-Id` header or request body field, which
would let one officer impersonate another. `changed_by` stays nullable at
the model/function level only because it is also used by
`record_initial_status` for system-generated rows (e.g. a citizen's initial
"reported" entry, which has no officer to attribute).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .models import Defect, DefectStatusHistory
from .road_health.config import (
    ALL_STATUSES,
    STATUS_CONFIRMED,
    STATUS_IN_PROGRESS,
    STATUS_REJECTED,
    STATUS_REPORTED,
    STATUS_RESOLVED,
)

# ---------------------------------------------------------------------------
# Transition graph
# ---------------------------------------------------------------------------
# Normal officer workflow:
#
#   reported -> under_review -> confirmed -> assigned -> repair_in_progress
#            -> resolved
#
# plus early dismissal: reported | under_review -> rejected.
#
# `resolved` and `rejected` are terminal: a defect that has been repaired or
# dismissed is closed. Re-opening would need a new report, which keeps the
# status history of a single defect a straight line.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_REPORTED: frozenset({STATUS_CONFIRMED, STATUS_REJECTED}),
    STATUS_CONFIRMED: frozenset({STATUS_IN_PROGRESS}),
    STATUS_IN_PROGRESS: frozenset({STATUS_RESOLVED}),
    STATUS_RESOLVED: frozenset(),
    STATUS_REJECTED: frozenset(),
}

# Backwards compatibility for the pre-existing `PATCH /defects/{id}` endpoint.
#
# That endpoint is what the officer UI's existing Confirm button calls, and it
# confirms a freshly reported defect in one step (reported -> confirmed)
# without an intermediate `under_review`. Removing that would break shipped
# behaviour, so the legacy endpoint -- and only the legacy endpoint -- also
# permits these transitions. The new `PATCH /defects/{id}/status` endpoint
# enforces the strict graph above.
LEGACY_EXTRA_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_REPORTED: frozenset({STATUS_CONFIRMED}),
}


class InvalidStatusError(ValueError):
    """The requested status is not part of the allowed vocabulary."""


class InvalidTransitionError(ValueError):
    """The requested status is valid, but not reachable from the current one."""


def normalize_status(status: str | None) -> str:
    """Trim/lowercase a status string. Does not validate."""
    return (status or "").strip().lower()


def validate_status(status: str | None) -> str:
    """
    Normalize and validate a status against the closed vocabulary.

    Raises `InvalidStatusError` for anything else -- arbitrary status strings
    can never reach the database.
    """
    normalized = normalize_status(status)

    if normalized not in ALL_STATUSES:
        raise InvalidStatusError(
            f"Invalid status '{status}'. Allowed statuses: {', '.join(ALL_STATUSES)}"
        )

    return normalized


def allowed_next_statuses(current_status: str | None, legacy: bool = False) -> frozenset[str]:
    """Statuses reachable from `current_status`."""
    current = normalize_status(current_status)

    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())

    if legacy:
        allowed = allowed | LEGACY_EXTRA_TRANSITIONS.get(current, frozenset())

    return allowed


def validate_transition(
    current_status: str | None,
    new_status: str | None,
    legacy: bool = False,
) -> str:
    """
    Validate a status change and return the normalized target status.

    Setting a defect to the status it already has is accepted as an idempotent
    no-op (a double-clicked Confirm button must not 400), and
    `apply_status_change` writes no history row for it.
    """
    target = validate_status(new_status)
    current = normalize_status(current_status)

    if target == current:
        return target

    if target not in allowed_next_statuses(current, legacy=legacy):
        allowed = sorted(allowed_next_statuses(current, legacy=legacy))

        raise InvalidTransitionError(
            f"Cannot change status from '{current}' to '{target}'. "
            + (
                f"Allowed next statuses: {', '.join(allowed)}."
                if allowed
                else f"'{current}' is a terminal status."
            )
        )

    return target


def record_status_history(
    db: Session,
    defect: Defect,
    old_status: str | None,
    new_status: str,
    changed_by: str | None = None,
    note: str | None = None,
) -> DefectStatusHistory:
    """Append one row to `defect_status_history`. Does not commit."""
    history = DefectStatusHistory(
        defect=defect,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        changed_at=datetime.utcnow(),
        note=note,
    )

    db.add(history)

    return history


def apply_status_change(
    db: Session,
    defect: Defect,
    new_status: str | None,
    note: str | None = None,
    changed_by: str | None = None,
    legacy: bool = False,
) -> DefectStatusHistory | None:
    """
    Validate, record, and apply a defect status change.

    Returns the history row that was written, or `None` when the change was a
    no-op (the defect was already in the requested status). Does not commit --
    the caller owns the transaction so the status update and its history row
    land together or not at all.

    Raises `InvalidStatusError` / `InvalidTransitionError` on rejection, in
    which case nothing is modified.
    """
    old_status = normalize_status(defect.defect_status)
    target = validate_transition(old_status, new_status, legacy=legacy)

    if target == old_status:
        return None

    history = record_status_history(
        db,
        defect,
        old_status=defect.defect_status,
        new_status=target,
        changed_by=changed_by,
        note=note,
    )

    defect.defect_status = target

    return history


def record_initial_status(
    db: Session,
    defect: Defect,
    changed_by: str | None = None,
    note: str | None = "Defect reported",
) -> DefectStatusHistory:
    """
    Seed the timeline for a newly created defect (`old_status = NULL`).

    Called from `POST /reports` so the officer timeline starts at the report
    itself rather than at the first officer action.
    """
    return record_status_history(
        db,
        defect,
        old_status=None,
        new_status=normalize_status(defect.defect_status) or STATUS_REPORTED,
        changed_by=changed_by,
        note=note,
    )
