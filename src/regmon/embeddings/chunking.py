"""Text chunking for embedding.

Splits long documents into overlapping, word-boundary-aligned chunks so each
chunk fits comfortably within an embedding model's context window while
preserving local context across chunk boundaries via overlap.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """A contiguous slice of a document."""

    index: int
    text: str
    start: int
    end: int


class TextChunker:
    """Splits text into overlapping chunks on word boundaries.

    Parameters
    ----------
    chunk_size:
        Target maximum chunk length in characters.
    overlap:
        Number of characters of overlap between consecutive chunks, to preserve
        context. Must be smaller than ``chunk_size``.
    """

    def __init__(self, chunk_size: int = 1000, overlap: int = 150) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= overlap < chunk_size:
            raise ValueError("overlap must be in [0, chunk_size)")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def split(self, text: str) -> list[Chunk]:
        """Split ``text`` into a list of :class:`Chunk` objects."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= self._chunk_size:
            return [Chunk(index=0, text=text, start=0, end=len(text))]

        chunks: list[Chunk] = []
        start = 0
        index = 0
        length = len(text)
        while start < length:
            end = min(start + self._chunk_size, length)
            if end < length:
                end = self._snap_to_boundary(text, start, end)
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(index=index, text=piece, start=start, end=end))
                index += 1
            if end >= length:
                break
            start = max(end - self._overlap, start + 1)
        return chunks

    @staticmethod
    def _snap_to_boundary(text: str, start: int, end: int) -> int:
        """Move ``end`` back to the last whitespace so words are not split."""
        boundary = text.rfind(" ", start, end)
        newline = text.rfind("\n", start, end)
        boundary = max(boundary, newline)
        # Only snap if it leaves a reasonably sized chunk (avoid tiny pieces).
        if boundary > start and boundary - start >= (end - start) // 2:
            return boundary
        return end


__all__ = ["Chunk", "TextChunker"]
