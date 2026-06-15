"""Tests for domain models and enums."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from regmon.models import (
    Jurisdiction,
    ParsedDocument,
    RegulatorySource,
    RiskLevel,
    SourceType,
)


class TestEnums:
    def test_jurisdiction_labels(self) -> None:
        assert Jurisdiction.RBI.label == "Reserve Bank of India"
        assert Jurisdiction.EU_AI_ACT.label == "European Union AI Act"

    def test_risk_level_from_score(self) -> None:
        assert RiskLevel.from_score(0.1) == RiskLevel.LOW
        assert RiskLevel.from_score(0.3) == RiskLevel.MEDIUM
        assert RiskLevel.from_score(0.6) == RiskLevel.HIGH
        assert RiskLevel.from_score(0.9) == RiskLevel.CRITICAL

    def test_risk_level_from_score_bounds(self) -> None:
        with pytest.raises(ValueError):
            RiskLevel.from_score(-0.1)
        with pytest.raises(ValueError):
            RiskLevel.from_score(1.1)

    def test_risk_severity_ordering(self) -> None:
        assert RiskLevel.LOW.severity < RiskLevel.MEDIUM.severity
        assert RiskLevel.MEDIUM.severity < RiskLevel.HIGH.severity
        assert RiskLevel.HIGH.severity < RiskLevel.CRITICAL.severity


class TestRegulatorySource:
    def test_slug_normalization(self) -> None:
        src = RegulatorySource(
            id="RBI-Notify",
            name="Test",
            jurisdiction=Jurisdiction.RBI,
            url="https://example.com",
            source_type=SourceType.HTML,
        )
        assert src.id == "rbi-notify"

    def test_invalid_slug_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RegulatorySource(
                id="bad slug!",
                name="Test",
                jurisdiction=Jurisdiction.RBI,
                url="https://example.com",
                source_type=SourceType.HTML,
            )


class TestRawDocument:
    def test_content_hash_deterministic(self, raw_document) -> None:
        assert raw_document.content_hash == raw_document.content_hash
        assert len(raw_document.content_hash) == 64


class TestParsedDocument:
    def test_word_count(self, parsed_document) -> None:
        assert parsed_document.word_count > 10

    def test_empty_text_rejected(self) -> None:
        import uuid

        with pytest.raises(ValidationError):
            ParsedDocument(
                raw_document_id=uuid.uuid4(),
                source_id="x",
                jurisdiction=Jurisdiction.RBI,
                title="T",
                clean_text="",
            )
