"""
timezone_utils.py
==================
Presentation-layer timezone conversion.

Storage stays UTC (naive `datetime.utcnow()`, as already used throughout
`models.py`/`defect_workflow.py`) -- that is correct and untouched. This
module only converts a stored UTC timestamp to `Asia/Kolkata` (IST) for
JSON responses, using a real `zoneinfo` conversion (never a hand-added
`timedelta(hours=5, minutes=30)` hack, which silently breaks around DST
edge cases / is easy to get wrong and impossible to audit).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def to_ist(value: datetime | None) -> datetime | None:
    """
    Convert a stored timestamp to a timezone-aware IST `datetime`.

    Naive datetimes (the storage convention here: `datetime.utcnow()`) are
    assumed to be UTC, per the existing model/workflow code. Already
    tz-aware datetimes are converted from whatever zone they carry.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(IST)
