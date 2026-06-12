"""Document parser agent: HTML cleaning, PDF text extraction, metadata.

>>> from regmon.parser import DocumentParserAgent
>>> parsed = DocumentParserAgent().parse(raw_document, content_bytes)
"""

from __future__ import annotations

from regmon.parser.agent import DocumentParserAgent, ParseError
from regmon.parser.html import HtmlExtraction, clean_html
from regmon.parser.metadata import extract_date, extract_reference_number
from regmon.parser.pdf import PdfExtraction, extract_pdf

__all__ = [
    "DocumentParserAgent",
    "HtmlExtraction",
    "ParseError",
    "PdfExtraction",
    "clean_html",
    "extract_date",
    "extract_pdf",
    "extract_reference_number",
]
