"""In-memory token-bucket rate limiting per client (one process; see docs/SECURITY.md)."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable

SECONDS_PER_MINUTE = 60.0
MAX_BURST = 5
MAX_CLIENTS = 1000


class RateLimiter:
    """Allows ``per_minute`` requests per client on average, in bursts of up to five."""

    def __init__(
        self,
        per_minute: int,
        *,
        max_clients: int = MAX_CLIENTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rate = per_minute / SECONDS_PER_MINUTE
        self._capacity = float(min(MAX_BURST, per_minute))
        self._max_clients = max_clients
        self._clock = clock
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def acquire(self, client: str) -> float:
        """Take one token; returns 0 when allowed, otherwise the seconds until the next token."""
        now = self._clock()
        tokens, updated = self._buckets.pop(client, (self._capacity, now))
        tokens = min(self._capacity, tokens + (now - updated) * self._rate)
        wait = 0.0 if tokens >= 1 else (1 - tokens) / self._rate
        self._buckets[client] = (tokens - 1 if wait == 0 else tokens, now)
        while len(self._buckets) > self._max_clients:
            self._buckets.popitem(last=False)
        return wait
