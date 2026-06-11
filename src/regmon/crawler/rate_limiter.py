"""Asynchronous, per-host rate limiting for polite crawling.

The limiter enforces a minimum spacing between requests so the crawler never
exceeds a configured number of requests per second against any single host.
Spacing is tracked independently per key (host), so unrelated regulators are
not throttled against one another.
"""

from __future__ import annotations

import asyncio


class AsyncRateLimiter:
    """Spacing-based async rate limiter keyed by an arbitrary string (host).

    Parameters
    ----------
    rate_per_sec:
        Maximum sustained requests per second per key. Must be positive.
    """

    def __init__(self, rate_per_sec: float) -> None:
        if rate_per_sec <= 0:
            raise ValueError(f"rate_per_sec must be positive, got {rate_per_sec!r}")
        self._min_interval = 1.0 / rate_per_sec
        self._locks: dict[str, asyncio.Lock] = {}
        self._next_allowed: dict[str, float] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def acquire(self, key: str = "") -> None:
        """Block until a request against ``key`` is permitted by the rate limit."""
        async with self._lock_for(key):
            loop = asyncio.get_running_loop()
            now = loop.time()
            next_allowed = self._next_allowed.get(key, 0.0)
            wait = next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = loop.time()
            self._next_allowed[key] = max(now, next_allowed) + self._min_interval


__all__ = ["AsyncRateLimiter"]
