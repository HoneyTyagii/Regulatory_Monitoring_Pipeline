"""Document parser agent: turn a :class:`RawDocument` into a :class:`ParsedDocument`.

The agent dispatches on the raw document's format (HTML/XML vs PDF vs plain
text), extracts clean text plus metadata (title, headings, publication date,
reference number), and assembles a normalized :class:`ParsedDocument` for the
downstream classification and risk stages.
"""

from __future__ import annotations

from pathlib import Path

from regmon.crawler.storage import StoredDocument
from regmon.logging_config import get_logger
from regmon.models import DocumentFormat, ParsedDocument, RawDocument
from regmon.parser.html import clean_html
from regmon.parser.metadata import extract_date, extract_reference_number
from regmon.parser.pdf import extract_pdf

log = get_logger(__name__)

_MAX_TITLE = 512
_MAX_SECTIONS = 50
_TEXT_FORMATS = {DocumentFormat.HTML, DocumentFormat.XML}


class ParseError(Exception):
    """Raised when a document yields no extractable text."""

    def __init__(self, raw_document_id: object, message: str) -> None:
        self.raw_document_id = raw_document_id
        super().__init__(f"failed to parse document {raw_document_id}: {message}")


class DocumentParserAgent:
    """Parses raw fetched documents into clean, structured documents."""

    def parse(self, raw: RawDocument, content: bytes | None = None) -> ParsedDocument:
        """Parse a :class:`RawDocument` into a :class:`ParsedDocument`.

        Parameters
        ----------
        raw:
            The fetched document metadata. For text formats, ``raw.content``
            is used directly when populated.
        content:
            Raw bytes of the payload. Required for PDFs (whose text is not
            stored on ``raw.content``); optional for text formats.

        Raises
        ------
        ParseError
            If no usable text can be extracted.
        """
        title: str | None = raw.title
        headings: list[str] = []

        if raw.content_format == DocumentFormat.PDF:
            if content is None:
                raise ParseError(raw.id, "PDF parsing requires raw content bytes")
            extraction = extract_pdf(content)
            clean_text = extraction.text
            title = title or extraction.title
        elif raw.content_format in _TEXT_FORMATS:
            html = raw.content or (content.decode("utf-8", "replace") if content else "")
            result = clean_html(html)
            clean_text = result.text
            title = title or result.title
            headings = result.headings
        else:  # JSON / TEXT and any other textual payloads
            clean_text = raw.content or (content.decode("utf-8", "replace") if content else "")
            clean_text = clean_text.strip()

        if not clean_text:
            log.warning(
                "parser.empty", raw_document_id=str(raw.id), format=raw.content_format.value
            )
            raise ParseError(raw.id, "no extractable text")

        resolved_title = self._resolve_title(title, clean_text, raw)
        reference_number = extract_reference_number(clean_text)
        published_at = extract_date(clean_text)

        parsed = ParsedDocument(
            raw_document_id=raw.id,
            source_id=raw.source_id,
            jurisdiction=raw.jurisdiction,
            title=resolved_title,
            clean_text=clean_text,
            reference_number=reference_number[:256] if reference_number else None,
            sections=headings[:_MAX_SECTIONS],
            published_at=published_at,
        )
        log.info(
            "parser.parsed",
            raw_document_id=str(raw.id),
            format=raw.content_format.value,
            words=parsed.word_count,
            has_reference=reference_number is not None,
            has_date=published_at is not None,
        )
        return parsed

    def parse_stored(self, stored: StoredDocument) -> ParsedDocument:
        """Parse a persisted document, reading its bytes from disk."""
        content = Path(stored.content_path).read_bytes()
        return self.parse(stored.document, content)

    @staticmethod
    def _resolve_title(title: str | None, clean_text: str, raw: RawDocument) -> str:
        """Pick the best available title, guaranteeing a non-empty result."""
        candidate = (title or "").strip()
        if not candidate:
            for line in clean_text.splitlines():
                stripped = line.strip()
                if stripped:
                    candidate = stripped
                    break
        if not candidate:
            candidate = f"{raw.jurisdiction.label} document"
        return candidate[:_MAX_TITLE]


__all__ = ["DocumentParserAgent", "ParseError"]
