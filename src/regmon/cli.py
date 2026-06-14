"""Command-line interface for the regulatory monitoring pipeline.

Entry point defined in ``pyproject.toml`` as ``regmon``.

Usage::

    regmon run              # one-shot pipeline run
    regmon run --loop       # continuous scheduled loop
    regmon backfill         # re-process all sources ignoring dedup
    regmon status           # show pipeline state summary
    regmon sources          # list configured sources
"""

from __future__ import annotations

import asyncio
import sys

import click

from regmon.config import SourceRegistry
from regmon.config.settings import Settings
from regmon.db import create_database
from regmon.db.engine import Database
from regmon.logging_config import configure_logging, get_logger
from regmon.pipeline import PipelineMemory, PipelineOrchestrator, PipelineStage

log = get_logger(__name__)


def _get_db(settings: Settings) -> Database:
    # Ensure all ORM models are loaded before create_all
    import regmon.approval.store
    import regmon.dedup.store
    import regmon.notifications.service
    import regmon.pipeline.state  # noqa: F401

    # Ensure SQLite parent directory exists
    url = settings.storage.database_url
    if url.startswith("sqlite:///") and ":memory:" not in url:
        from pathlib import Path

        db_path = url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = create_database(url)
    db.create_all()
    return db


@click.group()
@click.option("--env-file", default=".env", help="Path to .env file.")
@click.option("--log-level", default=None, help="Override log level.")
@click.option("--log-format", default=None, type=click.Choice(["console", "json"]))
@click.pass_context
def cli(ctx: click.Context, env_file: str, log_level: str | None, log_format: str | None) -> None:
    """regmon - Regulatory Monitoring Pipeline CLI."""
    from regmon.config.settings import load_settings
    from regmon.logging_config import LogFormat

    settings = load_settings(env_file=env_file)
    fmt: LogFormat = log_format or settings.app.log_format  # type: ignore[assignment]
    if log_level:
        configure_logging(level=log_level, fmt=fmt, force=True)
    else:
        configure_logging(level=settings.app.log_level, fmt=fmt, force=True)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings


@cli.command()
@click.option("--loop", is_flag=True, help="Run continuously at scheduled intervals.")
@click.option("--interval", default=60, type=int, help="Interval in minutes (loop mode).")
@click.option("--source", multiple=True, help="Limit to specific source ids.")
@click.pass_context
def run(ctx: click.Context, loop: bool, interval: int, source: tuple[str, ...]) -> None:
    """Execute a pipeline run (one-shot or continuous)."""
    settings: Settings = ctx.obj["settings"]

    if loop:
        from regmon.scheduler import run_scheduler

        run_scheduler(once=False, interval_minutes=interval)
    else:
        db = _get_db(settings)
        registry = SourceRegistry.default()
        sources = registry.enabled()
        if source:
            sources = [s for s in sources if s.id in source]
        if not sources:
            click.echo("No matching sources found.")
            sys.exit(1)

        click.echo(f"Running pipeline for {len(sources)} source(s)...")
        orchestrator = PipelineOrchestrator(settings, db)
        result = asyncio.run(orchestrator.run(sources))
        click.echo(
            f"Done: {result.processed_count} processed, "
            f"{result.duplicate_count} duplicates, "
            f"{result.error_count} errors."
        )
        db.dispose()


@cli.command()
@click.option("--source", multiple=True, help="Limit to specific source ids.")
@click.pass_context
def backfill(ctx: click.Context, source: tuple[str, ...]) -> None:
    """Re-process all sources, ignoring prior pipeline state (no dedup skip)."""
    settings: Settings = ctx.obj["settings"]
    db = _get_db(settings)
    registry = SourceRegistry.default()
    sources = registry.enabled()
    if source:
        sources = [s for s in sources if s.id in source]

    click.echo(f"Backfilling {len(sources)} source(s) (dedup memory ignored)...")
    from regmon.dedup import DeduplicationEngine, InMemoryFingerprintIndex

    # Fresh in-memory index = no prior fingerprints -> nothing is "duplicate"
    orchestrator = PipelineOrchestrator(
        settings, db, dedup=DeduplicationEngine(InMemoryFingerprintIndex())
    )
    result = asyncio.run(orchestrator.run(sources))
    click.echo(
        f"Backfill done: {result.processed_count} processed, " f"{result.error_count} errors."
    )
    db.dispose()


@cli.command()
@click.option("--run-id", default=None, help="Filter by run id.")
@click.pass_context
def status(ctx: click.Context, run_id: str | None) -> None:
    """Show pipeline state summary."""
    settings: Settings = ctx.obj["settings"]
    db = _get_db(settings)
    memory = PipelineMemory(db)

    last_run = memory.last_run_id()
    target_run = run_id or last_run
    click.echo(f"Last run: {last_run or '(none)'}")
    if target_run:
        click.echo(f"Showing stats for run: {target_run}")
        for stage in PipelineStage:
            docs = memory.documents_at_stage(stage, run_id=target_run)
            click.echo(f"  {stage.value:20s}: {len(docs)} document(s)")
    else:
        click.echo("No pipeline runs recorded yet.")

    # Pending approvals
    from regmon.approval import ApprovalGate

    gate = ApprovalGate(db)
    pending = gate.get_pending()
    if pending:
        click.echo(f"\nPending approvals: {len(pending)}")
        for req in pending[:5]:
            click.echo(f"  [{req.risk_level}] {req.title[:50]} (id: {str(req.id)[:8]})")

    db.dispose()


@cli.command()
@click.pass_context
def sources(ctx: click.Context) -> None:
    """List all configured regulatory sources."""
    registry = SourceRegistry.default()
    click.echo(f"{'ID':<25} {'Jurisdiction':<12} {'Type':<8} {'Enabled':<8} Name")
    click.echo("-" * 80)
    for src in registry.all():
        enabled = "yes" if src.enabled else "no"
        click.echo(
            f"{src.id:<25} {src.jurisdiction.value:<12} {src.source_type.value:<8} {enabled:<8} {src.name}"
        )


def main() -> None:
    """Entry point for the ``regmon`` console script."""
    cli()


__all__ = ["cli", "main"]
