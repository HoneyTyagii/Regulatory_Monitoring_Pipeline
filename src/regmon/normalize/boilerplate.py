"""Line-based boilerplate stripping for regulatory documents.

Removes navigation chrome, cookie/consent banners, copyright lines, page
markers, and other non-content lines that survive HTML/PDF extraction. Two
strategies are combined:

* pattern matching against a curated list of boilerplate line shapes, and
* frequency-based removal of short lines that repeat many times (typical of
  running headers/footers).

The logic is deliberately conservative: only whole-line matches and clearly
repetitive short lines are dropped, so substantive content is preserved.
"""

from __future__ import annotations

import re
from collections import Counter

# Whole-line boilerplate patterns (matched case-insensitively against the
# stripped line). Anchored to avoid removing lines that merely contain a word.
_BOILERPLATE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^skip to (?:main )?content$",
        r"^back to top$",
        r"^©.*$",
        r"^(?:\(c\)|copyright)\b.*$",
        r"^all rights reserved\.?$",
        r"^page \d+(?: of \d+)?$",
        r"^\d+\s*/\s*\d+$",
        r"^privacy policy$",
        r"^terms (?:of use|and conditions)$",
        r"^cookie(?:s)? (?:policy|notice|settings)$",
        r"^(?:we use cookies|this (?:site|website) uses cookies)\b.*$",
        r"^accept(?: all)?(?: cookies)?$",
        r"^loading\.{0,3}$",
        r"^(?:home|menu|search|login|sign in|register)$",
        r"^print(?:ed)?(?: this page| from .*)?$",
        r"^download(?:ed)?(?: from .*)?$",
        r"^share (?:this|on) .*$",
        r"^last updated:?.*$",
    )
)

#: Lines at or below this length that repeat at least ``_REPEAT_THRESHOLD``
#: times are treated as running headers/footers.
_MAX_REPEAT_LINE_LEN = 80
_REPEAT_THRESHOLD = 3


def _is_pattern_boilerplate(line: str) -> bool:
    return any(pattern.match(line) for pattern in _BOILERPLATE_PATTERNS)


def _repeated_short_lines(lines: list[str]) -> set[str]:
    counts = Counter(line for line in lines if 0 < len(line) <= _MAX_REPEAT_LINE_LEN)
    return {line for line, count in counts.items() if count >= _REPEAT_THRESHOLD}


def strip_boilerplate(text: str) -> tuple[str, int]:
    """Remove boilerplate lines from ``text``.

    Returns the cleaned text and the number of lines removed.
    """
    lines = text.split("\n")
    repeated = _repeated_short_lines(lines)

    kept: list[str] = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if stripped and (_is_pattern_boilerplate(stripped) or stripped in repeated):
            removed += 1
            continue
        kept.append(line)

    # Collapse blank lines that may be left behind after removals.
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return result, removed


__all__ = ["strip_boilerplate"]
