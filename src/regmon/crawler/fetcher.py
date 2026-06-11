"""Asynchronous HTTP fetch layer for the crawler.

Provides :class:`AsyncHttpFetcher`, which wraps an ``httpx.AsyncClient`` with:

* per-host rate limiting (politeness),
* exponential backoff with jitter on transient failures and retryable status
  codes (honoring ``Retry-After`` when present),
* optional ``robots.txt`` enforcement, and
* a normalized :class:`FetchResult` carrying raw bytes plus metadata.

The transport is fully injectable, so tests can supply an ``httpx.MockTransport``
and exercise the retry/limit logic without touching the network.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import TracebackType
from urllib.parse import urlsplit

import httpx

from regmon.config.settings import CrawlSettings
from regmon.crawler.rate_limiter import AsyncRateLimiter
from regmon.crawler.robots import RobotsChecker
from regmon.logging_config import get_logger
from regmon.models import DocumentFormat

log = get_logger(__name__)

#: HTTP status codes that justify a retry.
RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})

#: Magic byte prefix identifying a PDF payload.
_PDF_MAGIC = b"%PDF-"


class FetchError(Exception):
    """Raised when a URL cannot be fetched after exhausting all retries."""

    def __init__(self, url: str, message: str) -> None:
        self.url = url
        super().__init__(f"failed to fetch {url}: {message}")


class RobotsDisallowedError(FetchError):
    """Raised when ``robots.txt`` forbids fetching the requested URL."""

    def __init__(self, url: str) -> None:
        super().__init__(url, "disallowed by robots.txt")


@dataclass(frozen=True)
class FetchResult:
    """Normalized result of a successful HTTP fetch."""

    url: str
    status_code: int
    content: bytes
    content_type: str | None
    encoding: str | None
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ok(self) -> bool:
        """True for 2xx responses."""
        return 200 <= self.status_code < 300

    def detect_format(self) -> DocumentFormat:
        """Infer the :class:`DocumentFormat` from content type and magic bytes."""
        ctype = (self.content_type or "").split(";", 1)[0].strip().lower()
        if ctype == "application/pdf" or self.content.startswith(_PDF_MAGIC):
            return DocumentFormat.PDF
        if ctype in {"text/html", "application/xhtml+xml"}:
            return DocumentFormat.HTML
        if ctype in {"application/json", "text/json"}:
            return DocumentFormat.JSON
        if ctype in {"application/xml", "text/xml"} or ctype.endswith("+xml"):
            return DocumentFormat.XML
        return DocumentFormat.TEXT

    def text(self) -> str:
        """Decode the payload to text using the response encoding (lenient)."""
        return self.content.decode(self.encoding or "utf-8", errors="replace")


class AsyncHttpFetcher:
    """Polite, resilient async HTTP fetcher.

    May be used as an async context manager so the underlying client is closed
    automatically::

        async with AsyncHttpFetcher(settings) as fetcher:
            result = await fetcher.fetch(url)
    """

    def __init__(
        self,
        settings: CrawlSettings,
        *,
        client: httpx.AsyncClient | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
        robots: RobotsChecker | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent},
            timeout=settings.timeout_seconds,
            follow_redirects=True,
        )
        self._rate_limiter = rate_limiter or AsyncRateLimiter(settings.rate_limit_per_sec)
        if robots is not None:
            self._robots: RobotsChecker | None = robots
        elif settings.respect_robots:
            self._robots = RobotsChecker(self._client, settings.user_agent)
        else:
            self._robots = None

    async def __aenter__(self) -> AsyncHttpFetcher:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying client if this fetcher created it."""
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _host_of(url: str) -> str:
        return urlsplit(url).netloc

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None  # HTTP-date form is intentionally not parsed here.

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter for the given retry attempt."""
        base = self._settings.backoff_factor * (2**attempt)
        return random.uniform(0, base) if base > 0 else 0.0

    async def fetch(self, url: str) -> FetchResult:
        """Fetch ``url`` politely with retries, returning a :class:`FetchResult`.

        Raises
        ------
        RobotsDisallowedError
            If ``robots.txt`` forbids the URL.
        FetchError
            If the request fails after exhausting all retries.
        """
        if self._robots is not None and not await self._robots.allowed(url):
            log.info("crawler.robots_disallowed", url=url)
            raise RobotsDisallowedError(url)

        host = self._host_of(url)
        last_error: str = "unknown error"

        for attempt in range(self._settings.max_retries + 1):
            await self._rate_limiter.acquire(host)
            try:
                response = await self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.warning("crawler.fetch_error", url=url, attempt=attempt, error=last_error)
            else:
                if response.status_code in RETRYABLE_STATUS:
                    last_error = f"HTTP {response.status_code}"
                    retry_after = self._retry_after_seconds(response)
                    log.warning(
                        "crawler.retryable_status",
                        url=url,
                        attempt=attempt,
                        status=response.status_code,
                    )
                    if attempt < self._settings.max_retries:
                        await asyncio.sleep(
                            retry_after if retry_after is not None else self._backoff_delay(attempt)
                        )
                    continue
                return self._to_result(url, response)

            if attempt < self._settings.max_retries:
                await asyncio.sleep(self._backoff_delay(attempt))

        raise FetchError(url, last_error)

    @staticmethod
    def _to_result(url: str, response: httpx.Response) -> FetchResult:
        try:
            elapsed = response.elapsed.total_seconds()
        except RuntimeError:
            elapsed = 0.0
        return FetchResult(
            url=str(response.url) or url,
            status_code=response.status_code,
            content=response.content,
            content_type=response.headers.get("Content-Type"),
            encoding=response.encoding,
            headers=dict(response.headers),
            elapsed_seconds=elapsed,
        )


__all__ = [
    "RETRYABLE_STATUS",
    "AsyncHttpFetcher",
    "FetchError",
    "FetchResult",
    "RobotsDisallowedError",
]
