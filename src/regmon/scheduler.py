"""Lightweight asyncio-based scheduler for periodic pipeline runs.

Uses ``asyncio.sleep`` in a loop rather than pulling in APScheduler as a hard
dependency. The scheduler:

* Runs the pipeline at a configurable interval (default: every source's
  ``crawl_frequency_minutes``).
* Supports one-shot mode (run once and exit) for cron-based deployments.
* Gracefully handles shutdown via cancellation.

For production deployments that need cron expressions or persistence, drop in
APScheduler as an optional backend; this module provides the minimal always-
available entrypoint.
"""

from __future__ import annotations

import asyncio
import signal

from regmon.config import SourceRegistry, get_settings
from regmon.config.settings import Settings
from regmon.db import create_database
from regmon.db.engine import Database
from regmon.logging_config import get_logger
from regmon.pipeline import PipelineOrchestrator, PipelineRunContext

log = get_logger(__name__)


class PipelineScheduler:
    """Schedules periodic pipeline runs."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        db: Database | None = None,
        registry: SourceRegistry | None = None,
        interval_minutes: int | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._db = db or create_database(self._settings.storage.database_url)
        self._db.create_all()
        self._registry = registry or SourceRegistry.default()
        self._interval = (interval_minutes or 60) * 60  # seconds
        self._running = False

    async def run_once(self) -> PipelineRunContext:
        """Execute a single pipeline run and return the result."""
        sources = self._registry.enabled()
        log.info("scheduler.run_once", sources=len(sources))
        orchestrator = PipelineOrchestrator(self._settings, self._db)
        return await orchestrator.run(sources)

    async def run_loop(self) -> None:
        """Run the pipeline repeatedly at the configured interval until stopped."""
        self._running = True
        log.info("scheduler.started", interval_seconds=self._interval)
        while self._running:
            try:
                result = await self.run_once()
                log.info(
                    "scheduler.run_completed",
                    processed=result.processed_count,
                    duplicates=result.duplicate_count,
                    errors=result.error_count,
                )
            except Exception as exc:
                log.error("scheduler.run_failed", error=str(exc))
            if not self._running:
                break
            await asyncio.sleep(self._interval)

    def stop(self) -> None:
        """Signal the loop to exit after the current run."""
        self._running = False
        log.info("scheduler.stopping")

    def dispose(self) -> None:
        """Release database connections."""
        self._db.dispose()


def run_scheduler(*, once: bool = False, interval_minutes: int | None = None) -> None:
    """Entrypoint for the scheduler (blocks until shutdown)."""
    scheduler = PipelineScheduler(interval_minutes=interval_minutes)

    if once:
        asyncio.run(scheduler.run_once())
        scheduler.dispose()
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown() -> None:
        scheduler.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda *_: _shutdown())

    try:
        loop.run_until_complete(scheduler.run_loop())
    finally:
        scheduler.dispose()
        loop.close()


__all__ = ["PipelineScheduler", "run_scheduler"]
