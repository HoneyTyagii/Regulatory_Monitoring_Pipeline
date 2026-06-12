"""Content cleaner: orchestrates normalization, boilerplate stripping, and
language detection, and applies the result to a :class:`ParsedDocument`.
"""

from __future__ import annotations

from dataclasses import dataclass

from regmon.logging_config import get_logger
from regmon.models import ParsedDocument
from regmon.normalize.boilerplate import strip_boilerplate
from regmon.normalize.language import LanguageResult, detect_language
from regmon.normalize.text import fix_encoding, normalize_whitespace

log = get_logger(__name__)


@dataclass(frozen=True)
class CleanedContent:
    """Result of cleaning a block of text."""

    text: str
    language: str
    language_confidence: float
    original_chars: int
    cleaned_chars: int
    removed_boilerplate_lines: int


class ContentCleaner:
    """Cleans and normalizes extracted document text."""

    def __init__(self, *, strip_boilerplate_lines: bool = True) -> None:
        self._strip_boilerplate = strip_boilerplate_lines

    def clean(self, text: str) -> CleanedContent:
        """Run the full cleaning pipeline over ``text``."""
        original_chars = len(text)
        normalized = normalize_whitespace(fix_encoding(text))

        removed = 0
        if self._strip_boilerplate:
            normalized, removed = strip_boilerplate(normalized)

        lang: LanguageResult = detect_language(normalized)
        return CleanedContent(
            text=normalized,
            language=lang.language,
            language_confidence=lang.confidence,
            original_chars=original_chars,
            cleaned_chars=len(normalized),
            removed_boilerplate_lines=removed,
        )

    def normalize_document(self, parsed: ParsedDocument) -> ParsedDocument:
        """Return a copy of ``parsed`` with cleaned text and detected language.

        If cleaning would empty the text, the original ``clean_text`` is kept so
        the (non-empty) document invariant is never violated.
        """
        cleaned = self.clean(parsed.clean_text)
        text = cleaned.text or parsed.clean_text
        log.info(
            "normalize.document",
            raw_document_id=str(parsed.raw_document_id),
            language=cleaned.language,
            removed_lines=cleaned.removed_boilerplate_lines,
            original_chars=cleaned.original_chars,
            cleaned_chars=len(text),
        )
        return parsed.model_copy(update={"clean_text": text, "language": cleaned.language})


__all__ = ["CleanedContent", "ContentCleaner"]
