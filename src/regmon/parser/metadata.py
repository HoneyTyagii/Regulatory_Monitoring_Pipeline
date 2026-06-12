"""Heuristic extraction of dates and reference numbers from document text.

Regulators format reference numbers and dates in predictable but varied ways.
These helpers apply ordered regular expressions and return the first confident
match, falling back to ``None`` when nothing is found. They are intentionally
conservative: a wrong guess is worse than no guess for downstream risk scoring.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Reference-number patterns, tried in order. Each must expose the full
# reference in group 0 or a named group ``ref``.
_REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # RBI: RBI/2023-24/123 optionally followed by a department code.
    re.compile(r"\bRBI/\d{4}-\d{2,4}/\d+[A-Z0-9./-]*", re.IGNORECASE),
    # SEBI: SEBI/HO/DEPT/.../2023/123
    re.compile(r"\bSEBI/[A-Z0-9]+(?:/[A-Z0-9.-]+)+/\d{4}/\d+", re.IGNORECASE),
    # EU regulation: Regulation (EU) 2024/1689
    re.compile(r"\bRegulation\s*\(EU\)\s*\d{4}/\d+", re.IGNORECASE),
    # Generic: "Circular No. 12/2023" / "Notification No: X-1/2023"
    re.compile(
        r"\b(?:Circular|Notification|Ref(?:erence)?|Document)\s*"
        r"(?:No\.?|Number|#)\s*[:.-]?\s*(?P<ref>[A-Z0-9][A-Z0-9./-]{2,})",
        re.IGNORECASE,
    ),
)

# Date patterns, tried in order. Named groups drive parsing.
_DMY_NUMERIC = re.compile(r"\b(?P<d>\d{1,2})[/-](?P<m>\d{1,2})[/-](?P<y>\d{4})\b")
_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b")
_DAY_MONTH_YEAR = re.compile(
    r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<mon>[A-Za-z]+),?\s+(?P<y>\d{4})\b"
)
_MONTH_DAY_YEAR = re.compile(
    r"\b(?P<mon>[A-Za-z]+)\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>\d{4})\b"
)


def extract_reference_number(text: str) -> str | None:
    """Return the first regulator reference/circular number found, if any."""
    for pattern in _REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        ref = match.groupdict().get("ref") or match.group(0)
        return ref.strip().rstrip(".,;")
    return None


def _safe_date(year: int, month: int, day: int) -> datetime | None:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_date(text: str) -> datetime | None:
    """Return the first plausible publication date found in ``text``.

    Recognizes ISO (``2024-01-31``), day/month/year numeric (``31/01/2024``),
    and spelled-month forms (``31 January 2024`` / ``January 31, 2024``). Dates
    are returned as timezone-aware UTC ``datetime`` at midnight.
    """
    iso = _ISO.search(text)
    if iso is not None:
        result = _safe_date(int(iso["y"]), int(iso["m"]), int(iso["d"]))
        if result is not None:
            return result

    dmy = _DMY_NUMERIC.search(text)
    if dmy is not None:
        result = _safe_date(int(dmy["y"]), int(dmy["m"]), int(dmy["d"]))
        if result is not None:
            return result

    for pattern in (_DAY_MONTH_YEAR, _MONTH_DAY_YEAR):
        match = pattern.search(text)
        if match is None:
            continue
        month = _MONTHS.get(match["mon"].lower())
        if month is None:
            continue
        result = _safe_date(int(match["y"]), month, int(match["d"]))
        if result is not None:
            return result
    return None


__all__ = ["extract_date", "extract_reference_number"]
