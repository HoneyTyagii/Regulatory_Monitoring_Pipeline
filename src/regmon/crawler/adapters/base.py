"""Base class and shared parsing helpers for per-regulator source adapters.

A :class:`SourceAdapter` turns a source's entry point (an HTML listing page or
an RSS/Atom feed) into the concrete list of document URLs the crawler should
fetch. Parsing relies only on the standard library (``html.parser`` for HTML
anchors and ``xml.etree`` for feeds), so adapters add no third-party
dependencies.

Subclasses typically only declare a :attr:`jurisdiction` and a tuple of
:attr:`link_patterns`; the base class handles fetching the entry point,
choosing feed-vs-HTML parsing from the source type, and normalizing the
resulting URLs (absolutizing, de-duplicating, filtering, and capping).
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET

from regmon.crawler.fetcher import AsyncHttpFetcher
from regmon.logging_config import get_logger
from regmon.models import DocumentFormat, Jurisdiction, RegulatorySource, SourceType

log = get_logger(__name__)

_SKIP_PREFIXES = ("mailto:", "javascript:", "tel:", "#")


class _AnchorCollector(HTMLParser):
    """Collects ``href`` values from anchor (``<a>``) tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value.strip())


class SourceAdapter:
    """Discovers document URLs for a regulator from its entry point."""

    #: Jurisdiction this adapter serves. Required on concrete subclasses.
    jurisdiction: ClassVar[Jurisdiction]

    #: Case-insensitive substrings; an HTML anchor is kept only if its href
    #: contains at least one. Empty means "keep all links".
    link_patterns: ClassVar[tuple[str, ...]] = ()

    #: When True, only links on the same host as the entry point are kept.
    same_host_only: ClassVar[bool] = True

    #: Upper bound on the number of discovered URLs per crawl.
    max_links: ClassVar[int] = 100

    async def discover_urls(self, source: RegulatorySource, fetcher: AsyncHttpFetcher) -> list[str]:
        """Fetch the source entry point and return discovered document URLs."""
        entry = str(source.url)
        result = await fetcher.fetch(entry)
        text = result.text()

        if self._is_feed(source, result.detect_format()):
            raw_links = self.parse_feed(text)
            filter_patterns = False
        else:
            raw_links = self.extract_anchors(text, entry)
            filter_patterns = True

        urls = self._normalize(raw_links, entry, apply_patterns=filter_patterns)
        log.info(
            "crawler.adapter.discovered",
            jurisdiction=self.jurisdiction.value,
            source_id=source.id,
            count=len(urls),
        )
        return urls

    # -- parsing helpers ----------------------------------------------------

    @staticmethod
    def _is_feed(source: RegulatorySource, fmt: DocumentFormat) -> bool:
        return source.source_type == SourceType.RSS or fmt == DocumentFormat.XML

    @staticmethod
    def extract_anchors(html: str, base_url: str) -> list[str]:
        """Return absolutized hrefs from every anchor in ``html``."""
        parser = _AnchorCollector()
        parser.feed(html)
        return [urljoin(base_url, href) for href in parser.hrefs]

    @staticmethod
    def parse_feed(xml_text: str) -> list[str]:
        """Return item/entry links from an RSS or Atom feed.

        Malformed XML yields an empty list rather than raising, so a single bad
        feed never aborts a crawl.
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            log.warning("crawler.adapter.feed_parse_error", error=str(exc))
            return []

        links: list[str] = []
        # RSS 2.0: channel/item/link (text content).
        for item in root.iter("item"):
            link_el = item.find("link")
            if link_el is not None and link_el.text:
                links.append(link_el.text.strip())

        # Atom: entry/link[@href], preferring rel="alternate" or no rel.
        atom_ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.iter(f"{atom_ns}entry"):
            chosen: str | None = None
            for link_el in entry.findall(f"{atom_ns}link"):
                href = link_el.get("href")
                if not href:
                    continue
                rel = link_el.get("rel", "alternate")
                if rel == "alternate":
                    chosen = href
                    break
                chosen = chosen or href
            if chosen:
                links.append(chosen.strip())
        return links

    # -- normalization ------------------------------------------------------

    def _normalize(self, links: list[str], base_url: str, *, apply_patterns: bool) -> list[str]:
        base_host = urlsplit(base_url).netloc
        patterns = tuple(p.lower() for p in self.link_patterns)

        seen: set[str] = set()
        out: list[str] = []
        for raw in links:
            if not raw or raw.lower().startswith(_SKIP_PREFIXES):
                continue
            url = urljoin(base_url, raw).split("#", 1)[0]
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https"):
                continue
            if self.same_host_only and parts.netloc != base_host:
                continue
            if apply_patterns and patterns and not any(p in url.lower() for p in patterns):
                continue
            if url == base_url or url in seen:
                continue
            seen.add(url)
            out.append(url)
            if len(out) >= self.max_links:
                break
        return out


__all__ = ["SourceAdapter"]
