"""Per-regulator source adapters for document URL discovery.

>>> from regmon.crawler.adapters import default_registry
>>> registry = default_registry()
>>> adapter = registry.get(Jurisdiction.RBI)
"""

from __future__ import annotations

from regmon.crawler.adapters.base import SourceAdapter
from regmon.crawler.adapters.eu import EUAIActAdapter
from regmon.crawler.adapters.fda import FDAAdapter
from regmon.crawler.adapters.rbi import RBIAdapter
from regmon.crawler.adapters.registry import AdapterRegistry, default_registry
from regmon.crawler.adapters.sebi import SEBIAdapter

__all__ = [
    "AdapterRegistry",
    "EUAIActAdapter",
    "FDAAdapter",
    "RBIAdapter",
    "SEBIAdapter",
    "SourceAdapter",
    "default_registry",
]
