"""Tests for content cleaning and normalization."""

from __future__ import annotations

from regmon.normalize import (
    ContentCleaner,
    detect_language,
    fix_mojibake,
    normalize_whitespace,
    strip_boilerplate,
)


class TestTextNormalization:
    def test_fix_mojibake(self) -> None:
        broken = "the bank\u00e2\u20ac\u2122s policy"
        assert "\u2019" in fix_mojibake(broken)  # restored right single quote

    def test_normalize_whitespace(self) -> None:
        text = "a\u00a0b\r\n\r\n\r\nc\u200bd   e"
        result = normalize_whitespace(text)
        assert "\u200b" not in result
        assert "\u00a0" not in result
        assert "\r" not in result


class TestBoilerplate:
    def test_strips_common_patterns(self) -> None:
        text = "Skip to main content\nImportant regulation text.\nAll rights reserved"
        cleaned, removed = strip_boilerplate(text)
        assert "Skip to main" not in cleaned
        assert "Important regulation" in cleaned
        assert removed >= 2

    def test_preserves_short_unique_lines(self) -> None:
        text = "Short line\nAnother unique line"
        _cleaned, removed = strip_boilerplate(text)
        assert removed == 0


class TestLanguageDetection:
    def test_english(self) -> None:
        result = detect_language("the bank shall comply with this regulation")
        assert result.language == "en"

    def test_hindi_script(self) -> None:
        result = detect_language("\u092f\u0939 \u090f\u0915 \u0928\u093f\u092f\u092e \u0939\u0948")
        assert result.language == "hi"

    def test_french(self) -> None:
        result = detect_language("la banque doit se conformer a cette reglementation et que les")
        assert result.language == "fr"


class TestContentCleaner:
    def test_normalize_document(self, parsed_document) -> None:
        cleaner = ContentCleaner()
        result = cleaner.normalize_document(parsed_document)
        assert result.language == "en"
        assert len(result.clean_text) > 0
