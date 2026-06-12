"""Hashing primitives for exact and near-duplicate detection.

Provides:

* :func:`content_hash` - a normalized SHA-256 so trivial whitespace/case
  differences hash identically (exact-duplicate detection).
* :func:`simhash` - a 64-bit Charikar SimHash fingerprint whose Hamming
  distance approximates document dissimilarity (near-duplicate detection).
* :func:`shingles` / :func:`jaccard` - token shingling and set similarity used
  to verify near-duplicate candidates and reduce false positives.

All functions use only the standard library.
"""

from __future__ import annotations

import hashlib
import re

_SIMHASH_BITS = 64
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_for_hashing(text: str) -> str:
    """Lowercase and collapse whitespace so cosmetic differences are ignored."""
    return _WS_RE.sub(" ", text.lower()).strip()


def content_hash(text: str) -> str:
    """Return the SHA-256 hex digest of the normalized text."""
    return hashlib.sha256(normalize_for_hashing(text).encode("utf-8")).hexdigest()


def tokens(text: str) -> list[str]:
    """Tokenize into lowercased word tokens."""
    return _TOKEN_RE.findall(text.lower())


def shingles(text: str, k: int = 3) -> set[str]:
    """Return the set of ``k``-word shingles for ``text``.

    Falls back to single tokens when the document is shorter than ``k`` words.
    """
    toks = tokens(text)
    if len(toks) < k:
        return set(toks)
    return {" ".join(toks[i : i + k]) for i in range(len(toks) - k + 1)}


def _hash64(value: str) -> int:
    """Stable 64-bit hash of a string via BLAKE2b."""
    return int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest(), "big")


def simhash(text: str, k: int = 3) -> int:
    """Compute a 64-bit Charikar SimHash fingerprint of ``text``.

    Returns ``0`` for empty input. Similar documents yield fingerprints with a
    small Hamming distance.
    """
    feature_shingles = shingles(text, k)
    if not feature_shingles:
        return 0

    vector = [0] * _SIMHASH_BITS
    for shingle in feature_shingles:
        h = _hash64(shingle)
        for bit in range(_SIMHASH_BITS):
            if h & (1 << bit):
                vector[bit] += 1
            else:
                vector[bit] -= 1

    fingerprint = 0
    for bit in range(_SIMHASH_BITS):
        if vector[bit] > 0:
            fingerprint |= 1 << bit
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """Return the number of differing bits between two fingerprints."""
    return (a ^ b).bit_count()


def jaccard(a: set[str], b: set[str]) -> float:
    """Return the Jaccard similarity of two sets in ``[0.0, 1.0]``."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


def simhash_similarity(a: int, b: int) -> float:
    """Return a ``[0.0, 1.0]`` similarity derived from Hamming distance."""
    return 1.0 - hamming_distance(a, b) / _SIMHASH_BITS


__all__ = [
    "content_hash",
    "hamming_distance",
    "jaccard",
    "normalize_for_hashing",
    "shingles",
    "simhash",
    "simhash_similarity",
    "tokens",
]
