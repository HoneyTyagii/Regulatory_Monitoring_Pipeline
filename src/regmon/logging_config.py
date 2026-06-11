"""Structured logging configuration for the pipeline.

Uses ``structlog`` layered on top of the standard library ``logging`` module so
that the same configuration produces human-friendly console output during
development and machine-parseable JSON in production.

Example
-------
>>> from regmon.logging_config import configure_logging, get_logger
>>> configure_logging(level="INFO", fmt="console")
>>> log = get_logger(__name__)
>>> log.info("crawler.started", source="RBI", urls=12)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Literal

import structlog

LogFormat = Literal["console", "json"]

_CONFIGURED = False


def _coerce_level(level: str | int) -> int:
    """Convert a level name or number into a stdlib logging level int."""
    if isinstance(level, int):
        return level
    resolved = logging.getLevelName(level.upper())
    if isinstance(resolved, int):
        return resolved
    return logging.INFO


def configure_logging(
    level: str | int | None = None,
    fmt: LogFormat | None = None,
    *,
    force: bool = False,
) -> None:
    """Configure process-wide structured logging.

    Parameters
    ----------
    level:
        Logging level name (``"INFO"``) or number. Falls back to the
        ``REGMON_LOG_LEVEL`` environment variable, then ``INFO``.
    fmt:
        Output renderer: ``"console"`` for colorized key-value output or
        ``"json"`` for line-delimited JSON. Falls back to
        ``REGMON_LOG_FORMAT``, then ``"console"``.
    force:
        Reconfigure even if logging was already configured. Useful in tests.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    resolved_level = _coerce_level(level or os.getenv("REGMON_LOG_LEVEL", "INFO"))
    resolved_fmt: LogFormat = fmt or os.getenv("REGMON_LOG_FORMAT", "console")  # type: ignore[assignment]

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if resolved_fmt == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=resolved_level,
        force=True,
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger, configuring logging on first use."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
