"""Embedding providers.

Two providers are available, selected by configuration:

* :class:`MockEmbeddingProvider` - deterministic, fully offline hashed
  bag-of-words embeddings. Documents that share vocabulary get similar vectors,
  which makes semantic-search behavior testable without any network or model.
* :class:`OpenAIEmbeddingProvider` - calls the OpenAI embeddings REST API via
  ``httpx`` (no extra SDK dependency). Requires an API key.

Both implement the :class:`EmbeddingProvider` protocol.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, runtime_checkable

import httpx

from regmon.config.secrets import require
from regmon.config.settings import Provider, Settings
from regmon.logging_config import get_logger

log = get_logger(__name__)

# Known output dimensions for common OpenAI embedding models.
_OPENAI_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_TOKEN_SPLIT = str.maketrans(dict.fromkeys("\t\n\r.,;:!?()[]{}\"'`/\\|<>@#$%^&*+=~", " "))


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Produces dense vector embeddings for text."""

    @property
    def dimension(self) -> int:
        """Dimensionality of the produced vectors."""
        ...

    def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        ...


class MockEmbeddingProvider:
    """Deterministic, offline hashed bag-of-words embeddings."""

    def __init__(self, dimension: int = 256) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in text.lower().translate(_TOKEN_SPLIT).split():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self._dimension
            sign = 1.0 if (value >> 63) & 1 else -1.0
            vector[index] += sign
        return _l2_normalize(vector)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class OpenAIEmbeddingProvider:
    """Embeddings via the OpenAI REST API (``httpx``-based, no SDK required)."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._dimension = _OPENAI_DIMS.get(model, 1536)

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "input": texts},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        items = sorted(payload["data"], key=lambda d: d["index"])
        vectors = [list(map(float, item["embedding"])) for item in items]
        if vectors:
            self._dimension = len(vectors[0])
        return vectors


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Build the configured embedding provider from settings."""
    if settings.llm.embedding_provider == Provider.OPENAI:
        api_key = require(settings.llm.openai_api_key, "OPENAI_API_KEY")
        log.info(
            "embeddings.provider", provider="openai", model=settings.llm.openai_embedding_model
        )
        return OpenAIEmbeddingProvider(api_key, settings.llm.openai_embedding_model)
    log.info("embeddings.provider", provider="mock")
    return MockEmbeddingProvider()


__all__ = [
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "create_embedding_provider",
]
