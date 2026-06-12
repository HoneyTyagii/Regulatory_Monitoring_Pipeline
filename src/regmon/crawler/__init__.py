"""Crawler agent and async HTTP fetch layer.

>>> from regmon.crawler import CrawlerAgent, AsyncHttpFetcher, RawDocumentStore
"""

from __future__ import annotations

from regmon.crawler.adapters import (
    AdapterRegistry,
    EUAIActAdapter,
    FDAAdapter,
    RBIAdapter,
    SEBIAdapter,
    SourceAdapter,
    default_registry,
)
from regmon.crawler.base import CrawlerAgent
from regmon.crawler.fetcher import (
    AsyncHttpFetcher,
    FetchError,
    FetchResult,
    RobotsDisallowedError,
)
from regmon.crawler.rate_limiter import AsyncRateLimiter
from regmon.crawler.robots import RobotsChecker
from regmon.crawler.storage import RawDocumentStore, StoredDocument

__all__ = [
    "AdapterRegistry",
    "AsyncHttpFetcher",
    "AsyncRateLimiter",
    "CrawlerAgent",
    "EUAIActAdapter",
    "FDAAdapter",
    "FetchError",
    "FetchResult",
    "RBIAdapter",
    "RawDocumentStore",
    "RobotsChecker",
    "RobotsDisallowedError",
    "SEBIAdapter",
    "SourceAdapter",
    "StoredDocument",
    "default_registry",
]
