"""Deduplication engine: exact and near-duplicate detection.

The engine checks a document's text against a :class:`FingerprintIndex` of
previously seen documents and reports whether it is an exact duplicate (same
normalized content hash), a near-duplicate (SimHash within a Hamming threshold,
optionally confirmed by Jaccard shingle overlap), or unique.

The index is pluggable: :class:`InMemoryFingerprintIndex` is handy for tests and
single-run dedup, while a persistent index (see :mod:`regmon.dedup.store`) lets
deduplication span multiple crawl runs.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from regmon.dedup.hashing import (
    content_hash,
    hamming_distance,
    simhash,
    simhash_similarity,
)
from regmon.logging_config import get_logger

log = get_logger(__name__)

#: Default maximum Hamming distance (out of 64 bits) to treat as a near-match.
#: Deliberately conservative: in a compliance pipeline a false "duplicate" would
#: suppress a genuine regulatory change, so precision is favored over recall.
#: The exact content-hash layer still catches identical/whitespace/case variants.
DEFAULT_MAX_HAMMING = 6


class DuplicateKind(str, Enum):
    """Classification of a deduplication check."""

    EXACT = "exact"
    NEAR = "near"
    UNIQUE = "unique"


@dataclass(frozen=True)
class Fingerprint:
    """A document's dedup fingerprint."""

    doc_id: str
    content_hash: str
    simhash: int


@dataclass(frozen=True)
class DedupResult:
    """Outcome of a deduplication check."""

    kind: DuplicateKind
    content_hash: str
    simhash: int
    matched_doc_id: str | None = None
    similarity: float = 0.0

    @property
    def is_duplicate(self) -> bool:
        return self.kind is not DuplicateKind.UNIQUE


class FingerprintIndex(Protocol):
    """Storage protocol for document fingerprints."""

    def find_by_hash(self, content_hash: str) -> str | None:
        """Return the doc id for an exact content-hash match, or ``None``."""
        ...

    def iter_fingerprints(self) -> Iterable[Fingerprint]:
        """Iterate all stored fingerprints (for near-duplicate scanning)."""
        ...

    def add(self, fingerprint: Fingerprint) -> None:
        """Persist a fingerprint."""
        ...


class InMemoryFingerprintIndex:
    """A simple in-process fingerprint index."""

    def __init__(self) -> None:
        self._by_hash: dict[str, str] = {}
        self._fingerprints: list[Fingerprint] = []

    def find_by_hash(self, content_hash: str) -> str | None:
        return self._by_hash.get(content_hash)

    def iter_fingerprints(self) -> Iterable[Fingerprint]:
        return list(self._fingerprints)

    def add(self, fingerprint: Fingerprint) -> None:
        self._by_hash.setdefault(fingerprint.content_hash, fingerprint.doc_id)
        self._fingerprints.append(fingerprint)

    def __len__(self) -> int:
        return len(self._fingerprints)


class DeduplicationEngine:
    """Detects exact and near-duplicate documents against a fingerprint index."""

    def __init__(
        self,
        index: FingerprintIndex | None = None,
        *,
        max_hamming: int = DEFAULT_MAX_HAMMING,
        shingle_size: int = 2,
    ) -> None:
        self._index: FingerprintIndex = index or InMemoryFingerprintIndex()
        self._max_hamming = max_hamming
        self._shingle_size = shingle_size

    def fingerprint(self, doc_id: str, text: str) -> Fingerprint:
        """Compute the fingerprint for a document without storing it."""
        return Fingerprint(
            doc_id=doc_id,
            content_hash=content_hash(text),
            simhash=simhash(text, self._shingle_size),
        )

    def check(self, text: str) -> DedupResult:
        """Check ``text`` against the index without adding it."""
        chash = content_hash(text)
        sh = simhash(text, self._shingle_size)

        exact = self._index.find_by_hash(chash)
        if exact is not None:
            return DedupResult(DuplicateKind.EXACT, chash, sh, matched_doc_id=exact, similarity=1.0)

        near = self._nearest(sh)
        if near is not None:
            matched_id, similarity = near
            return DedupResult(
                DuplicateKind.NEAR, chash, sh, matched_doc_id=matched_id, similarity=similarity
            )
        return DedupResult(DuplicateKind.UNIQUE, chash, sh)

    def add(self, doc_id: str, text: str) -> Fingerprint:
        """Add a document's fingerprint to the index and return it."""
        fp = self.fingerprint(doc_id, text)
        self._index.add(fp)
        return fp

    def check_and_add(self, doc_id: str, text: str) -> DedupResult:
        """Check ``text`` and, if unique, add it to the index.

        Duplicates are reported but not added, so the index keeps a single
        canonical fingerprint per distinct document.
        """
        result = self.check(text)
        if not result.is_duplicate:
            self._index.add(Fingerprint(doc_id, result.content_hash, result.simhash))
        log.info(
            "dedup.checked",
            doc_id=doc_id,
            kind=result.kind.value,
            matched=result.matched_doc_id,
            similarity=round(result.similarity, 3),
        )
        return result

    def _nearest(self, sh: int) -> tuple[str, float] | None:
        """Find the most similar near-duplicate within the Hamming threshold."""
        best: tuple[str, float] | None = None
        for fp in self._index.iter_fingerprints():
            if hamming_distance(sh, fp.simhash) > self._max_hamming:
                continue
            similarity = simhash_similarity(sh, fp.simhash)
            if best is None or similarity > best[1]:
                best = (fp.doc_id, similarity)
        return best


__all__ = [
    "DEFAULT_MAX_HAMMING",
    "DedupResult",
    "DeduplicationEngine",
    "DuplicateKind",
    "Fingerprint",
    "FingerprintIndex",
    "InMemoryFingerprintIndex",
]
