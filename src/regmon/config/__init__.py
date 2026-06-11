"""Configuration, settings, and source-registry management for regmon.

Typical usage:

>>> from regmon.config import get_settings, SourceRegistry
>>> settings = get_settings()
>>> registry = SourceRegistry.default()
>>> rbi_sources = registry.for_jurisdiction(Jurisdiction.RBI)
"""

from __future__ import annotations

from regmon.config.secrets import mask, require, reveal
from regmon.config.settings import (
    AppSettings,
    CrawlSettings,
    Environment,
    LLMSettings,
    NotificationSettings,
    Provider,
    Settings,
    StorageSettings,
    get_settings,
    load_settings,
    reload_settings,
)
from regmon.config.sources import SourceRegistry

__all__ = [
    "AppSettings",
    "CrawlSettings",
    "Environment",
    "LLMSettings",
    "NotificationSettings",
    "Provider",
    "Settings",
    "SourceRegistry",
    "StorageSettings",
    "get_settings",
    "load_settings",
    "mask",
    "reload_settings",
    "require",
    "reveal",
]
