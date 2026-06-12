"""Deduplication: exact content hashing and near-duplicate detection.

>>> from regmon.dedup import DeduplicationEngine
>>> engine = DeduplicationEngine()
>>> engine.check_and_add("doc-1", "The bank shall comply with the regulation.")
>>> result = engine.check_and_add("doc-2", "The bank shall comply with the regulation!")
>>> result.kind, result.matched_doc_id
"""

from __future__ import annotations

from regmon.dedup.engine import (
    DEFAULT_MAX_HAMMING,
    DeduplicationEngine,
    DedupResult,
    DuplicateKind,
    Fingerprint,
    FingerprintIndex,
    InMemoryFingerprintIndex,
)
from regmon.dedup.hashing import (
    content_hash,
    hamming_distance,
    jaccard,
    shingles,
    simhash,
    simhash_similarity,
)
from regmon.dedup.store import DocumentFingerprintRecord, SqlFingerprintIndex

__all__ = [
    "DEFAULT_MAX_HAMMING",
    "DedupResult",
    "DeduplicationEngine",
    "DocumentFingerprintRecord",
    "DuplicateKind",
    "Fingerprint",
    "FingerprintIndex",
    "InMemoryFingerprintIndex",
    "SqlFingerprintIndex",
    "content_hash",
    "hamming_distance",
    "jaccard",
    "shingles",
    "simhash",
    "simhash_similarity",
]
