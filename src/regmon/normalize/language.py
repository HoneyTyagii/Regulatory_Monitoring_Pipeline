"""Lightweight, dependency-free language detection.

Detection runs in two stages:

1. **Script detection** - if most letters belong to a non-Latin Unicode block
   (Devanagari, Cyrillic, Arabic, CJK, ...), the language is inferred directly.
2. **Stopword scoring** - for Latin-script text, the share of common stopwords
   per supported language is compared; the best-scoring language wins.

This is intentionally simple and explainable rather than ML-based. Regulatory
text in this pipeline is predominantly English, so the detector defaults to
``en`` with low confidence when no strong signal is present.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[a-zà-öø-ÿ]+", re.IGNORECASE)

# Compact stopword sets per ISO 639-1 code. Small but discriminative.
_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        [
            "the",
            "of",
            "and",
            "to",
            "in",
            "is",
            "are",
            "for",
            "that",
            "this",
            "with",
            "as",
            "be",
            "by",
            "on",
            "or",
            "an",
            "it",
            "shall",
            "not",
        ]
    ),
    "fr": frozenset(
        [
            "le",
            "la",
            "les",
            "de",
            "des",
            "et",
            "un",
            "une",
            "est",
            "pour",
            "que",
            "dans",
            "sur",
            "par",
            "au",
            "aux",
            "ce",
            "ne",
            "pas",
        ]
    ),
    "de": frozenset(
        [
            "der",
            "die",
            "das",
            "und",
            "ist",
            "den",
            "von",
            "zu",
            "im",
            "mit",
            "dem",
            "ein",
            "eine",
            "nicht",
            "auch",
            "auf",
            "für",
        ]
    ),
    "es": frozenset(
        [
            "el",
            "la",
            "los",
            "las",
            "de",
            "y",
            "un",
            "una",
            "es",
            "que",
            "en",
            "para",
            "por",
            "con",
            "no",
            "se",
            "su",
            "del",
            "al",
        ]
    ),
    "it": frozenset(
        [
            "il",
            "la",
            "di",
            "e",
            "che",
            "un",
            "una",
            "per",
            "non",
            "con",
            "sono",
            "come",
            "del",
            "le",
            "gli",
            "nella",
            "alla",
        ]
    ),
    "pt": frozenset(
        [
            "o",
            "a",
            "os",
            "de",
            "e",
            "que",
            "do",
            "da",
            "em",
            "um",
            "uma",
            "para",
            "com",
            "não",
            "se",
            "na",
            "no",
            "por",
            "dos",
        ]
    ),
    "nl": frozenset(
        [
            "de",
            "het",
            "een",
            "en",
            "van",
            "is",
            "op",
            "te",
            "dat",
            "met",
            "voor",
            "zijn",
            "niet",
            "aan",
            "door",
            "ook",
            "als",
        ]
    ),
}

# (Unicode block ranges -> language) for non-Latin scripts.
_SCRIPT_RANGES: tuple[tuple[int, int, str], ...] = (
    (0x0900, 0x097F, "hi"),  # Devanagari
    (0x0400, 0x04FF, "ru"),  # Cyrillic
    (0x0600, 0x06FF, "ar"),  # Arabic
    (0x0590, 0x05FF, "he"),  # Hebrew
    (0x0370, 0x03FF, "el"),  # Greek
    (0x3040, 0x30FF, "ja"),  # Hiragana/Katakana
    (0xAC00, 0xD7A3, "ko"),  # Hangul
    (0x4E00, 0x9FFF, "zh"),  # CJK Unified Ideographs
)


@dataclass(frozen=True)
class LanguageResult:
    """Detected language code plus a confidence score in ``[0.0, 1.0]``."""

    language: str
    confidence: float


def _detect_script(text: str) -> str | None:
    counts: dict[str, int] = {}
    letters = 0
    for ch in text:
        if not ch.isalpha():
            continue
        letters += 1
        code = ord(ch)
        for low, high, lang in _SCRIPT_RANGES:
            if low <= code <= high:
                counts[lang] = counts.get(lang, 0) + 1
                break
    if letters == 0 or not counts:
        return None
    lang, count = max(counts.items(), key=lambda kv: kv[1])
    return lang if count / letters >= 0.3 else None


def detect_language(text: str) -> LanguageResult:
    """Return the most likely language of ``text`` with a confidence score."""
    script_lang = _detect_script(text)
    if script_lang is not None:
        return LanguageResult(script_lang, 0.9)

    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    if not tokens:
        return LanguageResult("en", 0.0)

    total = len(tokens)
    scores = {
        lang: sum(token in words for token in tokens) / total for lang, words in _STOPWORDS.items()
    }
    best_lang, best_score = max(scores.items(), key=lambda kv: kv[1])
    if best_score == 0.0:
        return LanguageResult("en", 0.0)
    return LanguageResult(best_lang, round(min(best_score * 4.0, 1.0), 3))


__all__ = ["LanguageResult", "detect_language"]
