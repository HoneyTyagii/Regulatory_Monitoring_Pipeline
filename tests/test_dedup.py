"""Tests for deduplication engine."""

from __future__ import annotations

from regmon.dedup import (
    DeduplicationEngine,
    DuplicateKind,
    SqlFingerprintIndex,
    content_hash,
    hamming_distance,
    jaccard,
    shingles,
    simhash,
)


class TestHashing:
    def test_content_hash_ignores_case_whitespace(self) -> None:
        assert content_hash("Hello World") == content_hash("  hello   world  ")

    def test_simhash_similar_docs_close(self) -> None:
        base = "The Reserve Bank of India hereby directs all scheduled commercial banks to comply with the revised KYC norms effective April 2024."
        variant = "The Reserve Bank of India hereby directs all scheduled commercial banks to comply with the revised KYC norms effective from April 2024 onwards."
        assert hamming_distance(simhash(base, k=2), simhash(variant, k=2)) < 10

    def test_simhash_different_docs_far(self) -> None:
        a = simhash(
            "The Reserve Bank of India hereby directs all scheduled commercial banks to comply with the revised KYC norms effective April 2024.",
            k=2,
        )
        b = simhash(
            "The FDA requires medical device manufacturers to submit clinical trial data demonstrating safety and efficacy under 21 CFR Part 812.",
            k=2,
        )
        assert hamming_distance(a, b) > 20

    def test_jaccard(self) -> None:
        a = shingles("one two three four five")
        b = shingles("one two three four six")
        assert 0.3 < jaccard(a, b) < 1.0


class TestDeduplicationEngine:
    def test_exact_duplicate(self) -> None:
        engine = DeduplicationEngine()
        engine.check_and_add("doc-1", "The regulation text.")
        result = engine.check_and_add("doc-2", "  the regulation   text.  ")
        assert result.kind == DuplicateKind.EXACT
        assert result.matched_doc_id == "doc-1"

    def test_unique_document(self) -> None:
        engine = DeduplicationEngine()
        engine.check_and_add("doc-1", "Capital adequacy requirements for banks.")
        result = engine.check_and_add("doc-2", "Medical device clinical trial approval.")
        assert result.kind == DuplicateKind.UNIQUE

    def test_near_duplicate(self) -> None:
        engine = DeduplicationEngine()
        engine.check_and_add(
            "doc-1",
            "The Reserve Bank of India hereby directs all scheduled commercial banks to comply with the revised KYC norms effective April 2024.",
        )
        result = engine.check_and_add(
            "doc-2",
            "The Reserve Bank of India hereby directs all scheduled commercial banks to comply with the revised KYC norms effective from April 2024 onwards.",
        )
        assert result.kind == DuplicateKind.NEAR


class TestSqlFingerprintIndex:
    def test_cross_run_persistence(self, db) -> None:
        idx1 = SqlFingerprintIndex(db)
        engine1 = DeduplicationEngine(idx1)
        engine1.check_and_add("d1", "Unique text about banking regulation.")

        idx2 = SqlFingerprintIndex(db)
        engine2 = DeduplicationEngine(idx2)
        result = engine2.check("Unique text about banking regulation.")
        assert result.kind == DuplicateKind.EXACT
