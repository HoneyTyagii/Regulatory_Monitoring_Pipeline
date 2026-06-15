"""Tests for the document parser agent."""

from __future__ import annotations

import pytest

from regmon.parser import (
    DocumentParserAgent,
    ParseError,
    clean_html,
    extract_date,
    extract_reference_number,
)


class TestHtmlCleaner:
    def test_strips_scripts_and_styles(self) -> None:
        html = "<html><script>bad()</script><style>x{}</style><body>Hello</body></html>"
        result = clean_html(html)
        assert "bad" not in result.text
        assert "Hello" in result.text

    def test_extracts_title(self) -> None:
        html = "<html><head><title>My Title</title></head><body>Body</body></html>"
        result = clean_html(html)
        assert result.title == "My Title"

    def test_extracts_headings(self) -> None:
        html = "<html><body><h1>First</h1><h2>Second</h2><p>text</p></body></html>"
        result = clean_html(html)
        assert result.headings == ["First", "Second"]


class TestMetadata:
    def test_rbi_reference(self) -> None:
        assert extract_reference_number("Circular RBI/2023-24/115 issued") == "RBI/2023-24/115"

    def test_sebi_reference(self) -> None:
        ref = extract_reference_number("Ref: SEBI/HO/MIRSD/DOP/P/CIR/2023/0099")
        assert ref and "SEBI" in ref

    def test_iso_date(self) -> None:
        dt = extract_date("Issued on 2024-01-31 by the board")
        assert dt is not None
        assert dt.day == 31 and dt.month == 1 and dt.year == 2024

    def test_spelled_date(self) -> None:
        dt = extract_date("effective from 5th April 2024")
        assert dt is not None
        assert dt.month == 4 and dt.year == 2024


class TestDocumentParserAgent:
    def test_parses_html(self, raw_document) -> None:
        agent = DocumentParserAgent()
        parsed = agent.parse(raw_document)
        assert "KYC" in parsed.title or "KYC" in parsed.clean_text
        assert parsed.word_count > 0

    def test_empty_content_raises(self) -> None:
        from regmon.models import DocumentFormat, Jurisdiction, RawDocument

        raw = RawDocument(
            source_id="x",
            jurisdiction=Jurisdiction.RBI,
            url="https://x.com",
            content="",
            content_format=DocumentFormat.HTML,
        )
        with pytest.raises(ParseError):
            DocumentParserAgent().parse(raw)
