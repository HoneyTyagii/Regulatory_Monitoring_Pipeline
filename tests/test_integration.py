"""Integration test: full pipeline end-to-end with mock HTTP transport."""

from __future__ import annotations

import httpx
import pytest

from regmon.crawler import AsyncHttpFetcher, CrawlerAgent
from regmon.db import AuditLog
from regmon.models import Jurisdiction, RegulatorySource
from regmon.pipeline import PipelineOrchestrator

HTML_RBI = (
    "<html><body><h1>KYC Circular</h1>"
    "<p>RBI circular on KYC norms for scheduled commercial banks. "
    "All banks must implement video-KYC with immediate effect. "
    "Non-compliance attracts penalty of Rs. 5 crore under Banking Regulation Act.</p>"
    "</body></html>"
)


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/robots.txt":
        return httpx.Response(404)
    return httpx.Response(200, text=HTML_RBI, headers={"Content-Type": "text/html"})


@pytest.mark.integration
def test_full_pipeline_run(db, settings) -> None:
    """Run the pipeline end-to-end with a mock HTTP backend."""
    import asyncio

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(_handler),
        headers={"User-Agent": "regmon-bot/0.1"},
    )
    fetcher = AsyncHttpFetcher(settings.crawl, client=client)
    crawler = CrawlerAgent(settings, fetcher=fetcher)
    orchestrator = PipelineOrchestrator(settings, db, crawler=crawler)

    sources = [
        RegulatorySource(
            id="rbi-int-test",
            name="RBI Integration",
            jurisdiction=Jurisdiction.RBI,
            url="https://rbi.example/doc",
            source_type="html",
        ),
    ]

    result = asyncio.run(orchestrator.run(sources))
    assert result.processed_count == 1
    assert result.error_count == 0

    doc = result.documents[0]
    assert doc.is_processed
    assert doc.parsed is not None
    assert doc.classification is not None
    assert doc.risk_assessment is not None
    assert len(doc.action_items) > 0

    # Verify audit trail
    audit = AuditLog(db)
    events = audit.list(limit=50)
    event_types = {e.event_type for e in events}
    assert "document.fetched" in event_types
    assert "document.parsed" in event_types
    assert "risk.assessed" in event_types
    assert "action.created" in event_types

    # Verify memory: second run skips
    result2 = asyncio.run(orchestrator.run(sources))
    assert result2.processed_count == 0
    assert result2.duplicate_count == 1


@pytest.mark.integration
def test_pipeline_handles_parse_failure(db, settings) -> None:
    """A document with empty content should be marked as error, not crash."""
    import asyncio

    def empty_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="", headers={"Content-Type": "text/html"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(empty_handler),
        headers={"User-Agent": "regmon-bot/0.1"},
    )
    fetcher = AsyncHttpFetcher(settings.crawl, client=client)
    crawler = CrawlerAgent(settings, fetcher=fetcher)
    orchestrator = PipelineOrchestrator(settings, db, crawler=crawler)

    sources = [
        RegulatorySource(
            id="fail-test",
            name="Fail Test",
            jurisdiction=Jurisdiction.FDA,
            url="https://fail.example/doc",
            source_type="html",
        ),
    ]

    result = asyncio.run(orchestrator.run(sources))
    assert result.processed_count == 0
    assert result.error_count == 0  # parse failure is graceful (error in ctx)
    assert result.documents[0].error is not None
