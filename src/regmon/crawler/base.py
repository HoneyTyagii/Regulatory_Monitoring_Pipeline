"""Base crawler agent: discover URLs, fetch politely, persist raw documents.

:class:`CrawlerAgent` provides the reusable orchestration shared by all
source-specific crawlers. Concrete crawlers (RSS, HTML listing, sitemap, ...)
override :meth:`discover_urls` to enumerate the document URLs for a source; the
base class handles fetching, retries/robots (via the fetcher), persistence, and
error isolation so one bad URL never aborts a whole crawl.
"""

from __future__ import annotations

from regmon.config.settings import Settings
from regmon.crawler.adapters.registry import AdapterRegistry
from regmon.crawler.fetcher import AsyncHttpFetcher, FetchError
from regmon.crawler.storage import RawDocumentStore, StoredDocument
from regmon.logging_config import get_logger
from regmon.models import RegulatorySource

log = get_logger(__name__)


class CrawlerAgent:
    """Fetches and persists documents for regulatory sources."""

    def __init__(
        self,
        settings: Settings,
        *,
        fetcher: AsyncHttpFetcher | None = None,
        store: RawDocumentStore | None = None,
        adapters: AdapterRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._owns_fetcher = fetcher is None
        self._fetcher = fetcher or AsyncHttpFetcher(settings.crawl)
        self._store = store or RawDocumentStore(settings.storage.raw_storage_path)
        self._adapters = adapters

    async def __aenter__(self) -> CrawlerAgent:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Release the fetcher's client if this agent created it."""
        if self._owns_fetcher:
            await self._fetcher.aclose()

    async def discover_urls(self, source: RegulatorySource) -> list[str]:
        """Return the document URLs to fetch for ``source``.

        If an adapter is registered for the source's jurisdiction, it is used to
        parse the entry point (feed or listing page) into document URLs.
        Otherwise the source's entry-point URL is returned as-is. Subclasses may
        also override this directly.
        """
        if self._adapters is not None:
            adapter = self._adapters.for_source(source)
            if adapter is not None:
                return await adapter.discover_urls(source, self._fetcher)
        return [str(source.url)]

    async def crawl_source(self, source: RegulatorySource) -> list[StoredDocument]:
        """Crawl a single source, persisting each fetched document.

        Robots-disallowed and failed URLs are logged and skipped rather than
        raising, so a partial crawl still yields the documents it could fetch.
        """
        if not source.enabled:
            log.info("crawler.source_skipped", source_id=source.id, reason="disabled")
            return []

        try:
            urls = await self.discover_urls(source)
        except FetchError as exc:
            log.warning("crawler.discovery_failed", source_id=source.id, error=str(exc))
            return []
        log.info("crawler.source_started", source_id=source.id, url_count=len(urls))

        stored: list[StoredDocument] = []
        for url in urls:
            try:
                result = await self._fetcher.fetch(url)
            except FetchError as exc:
                log.warning("crawler.url_failed", source_id=source.id, url=url, error=str(exc))
                continue
            stored.append(self._store.save(source, result))

        log.info(
            "crawler.source_finished",
            source_id=source.id,
            fetched=len(stored),
            requested=len(urls),
        )
        return stored

    async def crawl(self, sources: list[RegulatorySource]) -> list[StoredDocument]:
        """Crawl multiple sources sequentially, aggregating stored documents."""
        results: list[StoredDocument] = []
        for source in sources:
            results.extend(await self.crawl_source(source))
        return results


__all__ = ["CrawlerAgent"]
