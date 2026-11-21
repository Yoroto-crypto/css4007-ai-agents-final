"""Strict ISO date handling shared by tools, validation, and plans."""

from __future__ import annotations

import datetime
import re
from typing import Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_iso_date(value: Any) -> bool:
    """True only for real calendar dates written exactly as YYYY-MM-DD.

    Python's `date.fromisoformat` also accepts compact forms such as "20261210";
    the regex keeps the accepted format to a single, unambiguous spelling.
    """
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:  # e.g. 2026-02-30 or 2026-13-01
        return False
    return True
