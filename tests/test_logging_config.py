"""Smoke tests for logging configuration and package metadata."""

from __future__ import annotations

import logging

import regmon
from regmon.logging_config import configure_logging, get_logger


def test_package_exposes_version() -> None:
    assert isinstance(regmon.__version__, str)
    assert regmon.__version__.count(".") >= 2


def test_configure_logging_is_idempotent() -> None:
    configure_logging(level="DEBUG", fmt="json", force=True)
    # A second call without force should not raise and should be a no-op.
    configure_logging(level="ERROR")
    log = get_logger("test")
    # Logger should be usable without raising.
    log.info("test.event", value=1)


def test_get_logger_configures_on_first_use() -> None:
    log = get_logger(__name__)
    assert log is not None
    log.warning("test.warning", reason="smoke")


def test_console_format_configures(caplog) -> None:
    configure_logging(level="INFO", fmt="console", force=True)
    log = get_logger("console-test")
    with caplog.at_level(logging.INFO):
        log.info("console.event", k="v")
