"""HTML-to-text cleaning using the standard library ``html.parser``.

Extracts readable text, the document ``<title>``, and heading texts (used as
section markers) while discarding scripts, styles, and other non-content
elements. Whitespace is normalized so downstream tokenization and summarization
see clean, compact text. No third-party HTML library is required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
_BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "li",
    "tr",
    "section",
    "article",
    "header",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

_WS_RUN = re.compile(r"[ \t\f\v]+")
_BLANKLINES = re.compile(r"\n\s*\n\s*\n+")


@dataclass
class HtmlExtraction:
    """Result of cleaning an HTML document."""

    text: str
    title: str | None = None
    headings: list[str] = field(default_factory=list)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._in_heading = False
        self._title_parts: list[str] = []
        self._heading_parts: list[str] = []
        self.title: str | None = None
        self.headings: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _HEADING_TAGS:
            self._in_heading = True
            self._heading_parts = []
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
            self.title = " ".join("".join(self._title_parts).split()) or None
        elif tag in _HEADING_TAGS:
            self._in_heading = False
            heading = " ".join("".join(self._heading_parts).split())
            if heading:
                self.headings.append(heading)
        if tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_title:
            self._title_parts.append(data)
            return  # Title belongs to metadata, not body text.
        if self._in_heading:
            self._heading_parts.append(data)
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def _normalize_whitespace(text: str) -> str:
    lines = [_WS_RUN.sub(" ", line).strip() for line in text.splitlines()]
    collapsed = "\n".join(lines)
    return _BLANKLINES.sub("\n\n", collapsed).strip()


def clean_html(html: str) -> HtmlExtraction:
    """Strip markup from ``html`` and return normalized text plus metadata."""
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    return HtmlExtraction(
        text=_normalize_whitespace(extractor.get_text()),
        title=extractor.title,
        headings=extractor.headings,
    )


__all__ = ["HtmlExtraction", "clean_html"]
