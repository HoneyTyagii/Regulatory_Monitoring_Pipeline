"""Per-jurisdiction registry of regulatory sources, loaded from YAML.

The registry is the authoritative list of feeds/sites the crawler monitors.
It is defined declaratively in YAML so non-developers can add or disable a
source without touching code:

.. code-block:: yaml

    sources:
      - id: rbi-notifications
        name: RBI Notifications
        jurisdiction: RBI
        url: https://www.rbi.org.in/Scripts/NotificationUser.aspx
        source_type: html
        crawl_frequency_minutes: 720

A bundled ``default_sources.yaml`` ships with the package; callers may also
load a custom file via :meth:`SourceRegistry.from_yaml`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from regmon.models import Jurisdiction, RegulatorySource

_DEFAULT_RESOURCE = "default_sources.yaml"


class SourceRegistry:
    """An immutable, queryable collection of :class:`RegulatorySource` objects."""

    def __init__(self, sources: list[RegulatorySource]) -> None:
        seen: set[str] = set()
        by_id: dict[str, RegulatorySource] = {}
        by_jurisdiction: dict[Jurisdiction, list[RegulatorySource]] = defaultdict(list)
        for source in sources:
            if source.id in seen:
                raise ValueError(f"duplicate source id in registry: {source.id!r}")
            seen.add(source.id)
            by_id[source.id] = source
            by_jurisdiction[source.jurisdiction].append(source)
        self._by_id = by_id
        self._by_jurisdiction = dict(by_jurisdiction)

    # -- constructors -------------------------------------------------------

    @classmethod
    def from_dicts(cls, raw_sources: list[dict[str, Any]]) -> SourceRegistry:
        """Build a registry from a list of raw mapping records."""
        return cls([RegulatorySource(**record) for record in raw_sources])

    @classmethod
    def from_yaml(cls, path: str | Path) -> SourceRegistry:
        """Load a registry from a YAML file with a top-level ``sources`` list."""
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"source registry not found: {file_path}")
        with file_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return cls._from_loaded(data, origin=str(file_path))

    @classmethod
    def default(cls) -> SourceRegistry:
        """Load the registry bundled with the package."""
        resource = resources.files("regmon.config").joinpath(_DEFAULT_RESOURCE)
        data = yaml.safe_load(resource.read_text(encoding="utf-8")) or {}
        return cls._from_loaded(data, origin=_DEFAULT_RESOURCE)

    @classmethod
    def _from_loaded(cls, data: Any, *, origin: str) -> SourceRegistry:
        if not isinstance(data, dict) or "sources" not in data:
            raise ValueError(f"registry must contain a top-level 'sources' list: {origin}")
        raw_sources = data["sources"]
        if not isinstance(raw_sources, list):
            raise ValueError(f"'sources' must be a list: {origin}")
        return cls.from_dicts(raw_sources)

    # -- queries ------------------------------------------------------------

    def all(self) -> list[RegulatorySource]:
        """Return every registered source."""
        return list(self._by_id.values())

    def enabled(self) -> list[RegulatorySource]:
        """Return only sources that are currently enabled for crawling."""
        return [s for s in self._by_id.values() if s.enabled]

    def get(self, source_id: str) -> RegulatorySource:
        """Return a source by id, raising :class:`KeyError` if absent."""
        try:
            return self._by_id[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source id: {source_id!r}") from exc

    def for_jurisdiction(self, jurisdiction: Jurisdiction) -> list[RegulatorySource]:
        """Return all sources registered under a given jurisdiction."""
        return list(self._by_jurisdiction.get(jurisdiction, []))

    def jurisdictions(self) -> list[Jurisdiction]:
        """Return the jurisdictions that have at least one registered source."""
        return list(self._by_jurisdiction.keys())

    def __len__(self) -> int:
        return len(self._by_id)

    def __iter__(self) -> Iterator[RegulatorySource]:
        return iter(self._by_id.values())

    def __contains__(self, source_id: object) -> bool:
        return source_id in self._by_id


__all__ = ["SourceRegistry"]
