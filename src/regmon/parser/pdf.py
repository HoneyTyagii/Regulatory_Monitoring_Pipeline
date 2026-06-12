"""PDF text extraction built on :mod:`pypdf`.

Extracts page text from PDF bytes and normalizes whitespace. Encrypted PDFs are
handled with an empty-password decrypt attempt; pages that fail to extract are
skipped so a single corrupt page does not abort the whole document.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from regmon.logging_config import get_logger

log = get_logger(__name__)

_WS_RUN = re.compile(r"[ \t\f\v]+")
_BLANKLINES = re.compile(r"\n\s*\n\s*\n+")


@dataclass
class PdfExtraction:
    """Result of extracting text from a PDF."""

    text: str
    page_count: int
    title: str | None = None
    headings: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    lines = [_WS_RUN.sub(" ", line).strip() for line in text.splitlines()]
    return _BLANKLINES.sub("\n\n", "\n".join(lines)).strip()


def extract_pdf(content: bytes) -> PdfExtraction:
    """Extract normalized text and metadata from PDF ``content`` bytes.

    Returns an empty extraction (rather than raising) when the document cannot
    be read at all, so the parser can mark the document failed and move on.
    """
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except (PyPdfError, NotImplementedError) as exc:
                log.warning("parser.pdf_encrypted", error=str(exc))
                return PdfExtraction(text="", page_count=0)

        pages: list[str] = []
        for index, page in enumerate(reader.pages):
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:  # isolate per-page extraction failures
                log.warning("parser.pdf_page_failed", page=index, error=str(exc))

        title: str | None = None
        if reader.metadata and reader.metadata.title:
            title = str(reader.metadata.title).strip() or None

        return PdfExtraction(
            text=_normalize("\n\n".join(pages)),
            page_count=len(reader.pages),
            title=title,
        )
    except (PyPdfError, OSError, ValueError) as exc:
        log.warning("parser.pdf_read_failed", error=str(exc))
        return PdfExtraction(text="", page_count=0)


__all__ = ["PdfExtraction", "extract_pdf"]
