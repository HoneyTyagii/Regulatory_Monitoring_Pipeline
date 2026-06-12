"""Encoding repair and whitespace normalization for extracted text.

These functions fix the two most common defects in text pulled from HTML and
PDF sources: mis-decoded bytes (mojibake such as ``â€™`` for ``'``) and noisy
whitespace (mixed line endings, non-breaking and zero-width spaces, runs of
blanks). They use only the standard library.
"""

from __future__ import annotations

import re
import unicodedata

# Characters that strongly suggest UTF-8 bytes were decoded as Latin-1/CP1252.
_MOJIBAKE_MARKERS = ("Ã", "â€", "Â", " Â", "ï»¿")

# Smart punctuation -> ASCII equivalents for consistent downstream tokenization.
_PUNCT_MAP = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2015": "-",
    "\u2026": "...",
    "\u00a0": " ",  # non-breaking space
    "\u2022": "-",  # bullet
    "\u00b7": "-",  # middle dot
}
_PUNCT_TABLE = {ord(k): v for k, v in _PUNCT_MAP.items()}

# Spaces that should collapse to a regular space.
_UNICODE_SPACES = "\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
# Zero-width and BOM characters to delete outright.
_ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE_RUN_RE = re.compile(r"[ \t\f\v]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def fix_mojibake(text: str) -> str:
    """Repair text whose UTF-8 bytes were decoded as Latin-1/CP1252.

    The round-trip is applied only when mojibake markers are present and the
    re-decode succeeds and actually reduces those markers, so correctly decoded
    text is never corrupted.
    """
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text
    before = sum(text.count(m) for m in _MOJIBAKE_MARKERS)
    for encoding in ("cp1252", "latin-1"):
        try:
            repaired = text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        after = sum(repaired.count(m) for m in _MOJIBAKE_MARKERS)
        if after < before:
            return repaired
    return text


def fix_encoding(text: str) -> str:
    """Apply mojibake repair, Unicode NFC normalization, and punctuation mapping."""
    text = fix_mojibake(text)
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_PUNCT_TABLE)
    return _CONTROL_RE.sub("", text)


def normalize_whitespace(text: str) -> str:
    """Normalize line endings and collapse noisy whitespace.

    Converts CRLF/CR to LF, removes zero-width characters, maps exotic spaces to
    regular spaces, trims each line, collapses intra-line space runs, and limits
    consecutive blank lines to one.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate({ord(c): None for c in _ZERO_WIDTH})
    text = text.translate({ord(c): " " for c in _UNICODE_SPACES})
    lines = [_SPACE_RUN_RE.sub(" ", line).strip() for line in text.split("\n")]
    collapsed = "\n".join(lines)
    return _BLANKLINES_RE.sub("\n\n", collapsed).strip()


__all__ = ["fix_encoding", "fix_mojibake", "normalize_whitespace"]
