"""Content cleaning and normalization.

Boilerplate stripping, whitespace/encoding repair, and language detection,
exposed both as standalone functions and via the :class:`ContentCleaner`
orchestrator.

>>> from regmon.normalize import ContentCleaner
>>> cleaned = ContentCleaner().clean(raw_text)
"""

from __future__ import annotations

from regmon.normalize.boilerplate import strip_boilerplate
from regmon.normalize.cleaner import CleanedContent, ContentCleaner
from regmon.normalize.language import LanguageResult, detect_language
from regmon.normalize.text import fix_encoding, fix_mojibake, normalize_whitespace

__all__ = [
    "CleanedContent",
    "ContentCleaner",
    "LanguageResult",
    "detect_language",
    "fix_encoding",
    "fix_mojibake",
    "normalize_whitespace",
    "strip_boilerplate",
]
