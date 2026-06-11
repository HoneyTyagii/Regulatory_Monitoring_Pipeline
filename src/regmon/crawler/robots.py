"""robots.txt fetching, parsing, and per-host caching.

Implements a conservative-but-standard policy: a host's ``robots.txt`` is
fetched once and cached. A missing file (HTTP 404) means everything is
allowed; a file that cannot be retrieved (network error, 5xx) is treated as
*allow* but logged, matching common crawler behavior while keeping the
pipeline running. Explicit ``Disallow`` rules are always honored.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from regmon.logging_config import get_logger

log = get_logger(__name__)


class RobotsChecker:
    """Fetches and caches ``robots.txt`` and answers fetch-permission queries."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        user_agent: str,
        *,
        timeout: float = 10.0,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._timeout = timeout
        self._cache: dict[str, RobotFileParser | None] = {}

    @staticmethod
    def _robots_url(url: str) -> tuple[str, str]:
        """Return ``(host_key, robots_txt_url)`` for the host owning ``url``."""
        parts = urlsplit(url)
        host_key = f"{parts.scheme}://{parts.netloc}"
        robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
        return host_key, robots_url

    async def _load(self, host_key: str, robots_url: str) -> RobotFileParser | None:
        parser = RobotFileParser()
        try:
            response = await self._client.get(
                robots_url,
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
            )
        except httpx.HTTPError as exc:
            log.warning("robots.fetch_failed", url=robots_url, error=str(exc))
            return None

        if response.status_code == 404:
            parser.parse([])  # No robots.txt -> everything allowed.
            return parser
        if response.status_code >= 400:
            log.warning("robots.unavailable", url=robots_url, status=response.status_code)
            return None

        parser.parse(response.text.splitlines())
        return parser

    async def allowed(self, url: str) -> bool:
        """Return whether ``url`` may be fetched under the configured user agent."""
        host_key, robots_url = self._robots_url(url)
        if host_key not in self._cache:
            self._cache[host_key] = await self._load(host_key, robots_url)

        parser = self._cache[host_key]
        if parser is None:
            # Could not determine rules; allow but the failure was already logged.
            return True
        return parser.can_fetch(self._user_agent, url)

    def clear_cache(self) -> None:
        """Forget all cached robots.txt rules."""
        self._cache.clear()


__all__ = ["RobotsChecker"]
