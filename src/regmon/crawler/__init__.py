"""Crawler agent and async HTTP fetch layer.

>>> from regmon.crawler import CrawlerAgent, AsyncHttpFetcher, RawDocumentStore
"""

from __future__ import annotations

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
    "AsyncHttpFetcher",
    "AsyncRateLimiter",
    "CrawlerAgent",
    "FetchError",
    "FetchResult",
    "RawDocumentStore",
    "RobotsChecker",
    "RobotsDisallowedError",
    "StoredDocument",
]
