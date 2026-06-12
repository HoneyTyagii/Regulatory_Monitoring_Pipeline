"""Registry mapping jurisdictions to their :class:`SourceAdapter`.

The crawler consults an :class:`AdapterRegistry` to pick the right discovery
logic for each source. :func:`default_registry` wires up the built-in adapters
for RBI, SEBI, FDA, and the EU AI Act.
"""

from __future__ import annotations

from regmon.crawler.adapters.base import SourceAdapter
from regmon.crawler.adapters.eu import EUAIActAdapter
from regmon.crawler.adapters.fda import FDAAdapter
from regmon.crawler.adapters.rbi import RBIAdapter
from regmon.crawler.adapters.sebi import SEBIAdapter
from regmon.models import Jurisdiction, RegulatorySource


class AdapterRegistry:
    """Resolves the :class:`SourceAdapter` responsible for a given source."""

    def __init__(self, adapters: list[SourceAdapter] | None = None) -> None:
        self._by_jurisdiction: dict[Jurisdiction, SourceAdapter] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: SourceAdapter) -> None:
        """Register (or replace) the adapter for its jurisdiction."""
        self._by_jurisdiction[adapter.jurisdiction] = adapter

    def get(self, jurisdiction: Jurisdiction) -> SourceAdapter | None:
        """Return the adapter for a jurisdiction, or ``None`` if unregistered."""
        return self._by_jurisdiction.get(jurisdiction)

    def for_source(self, source: RegulatorySource) -> SourceAdapter | None:
        """Return the adapter responsible for ``source`` (by jurisdiction)."""
        return self.get(source.jurisdiction)

    def __contains__(self, jurisdiction: object) -> bool:
        return jurisdiction in self._by_jurisdiction

    def __len__(self) -> int:
        return len(self._by_jurisdiction)


def default_registry() -> AdapterRegistry:
    """Build a registry containing all built-in regulator adapters."""
    return AdapterRegistry([RBIAdapter(), SEBIAdapter(), FDAAdapter(), EUAIActAdapter()])


__all__ = ["AdapterRegistry", "default_registry"]
