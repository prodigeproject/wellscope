from __future__ import annotations

import pytest

from wellscope.api.ratelimit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_a_burst_is_allowed_then_requests_wait_for_the_refill() -> None:
    clock = Clock()
    limiter = RateLimiter(per_minute=6, clock=clock)
    assert [limiter.acquire("a") for _ in range(5)] == [0.0] * 5
    assert limiter.acquire("a") == pytest.approx(10.0)
    clock.now += 10.0
    assert limiter.acquire("a") == 0.0


def test_clients_have_separate_buckets_and_the_table_is_bounded() -> None:
    clock = Clock()
    limiter = RateLimiter(per_minute=1, max_clients=2, clock=clock)
    assert limiter.acquire("a") == 0.0
    assert limiter.acquire("a") > 0
    assert limiter.acquire("b") == 0.0
    assert limiter.acquire("c") == 0.0
    assert limiter.acquire("a") == 0.0
