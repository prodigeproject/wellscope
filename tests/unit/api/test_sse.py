from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Sequence
from typing import Any

from wellscope.api.sse import Question, answer_events
from wellscope.qa.analyzer import Turn


class SlowService:
    """Reports one stage, waits until released, then reports the next stage."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.stopped_early = threading.Event()

    def ask(self, question: str, history: Sequence[Turn], on_stage: Callable[[str], None]) -> Any:
        on_stage("analyzing")
        self.release.wait(5)
        try:
            on_stage("retrieving")
        except Exception:
            self.stopped_early.set()
            raise
        raise AssertionError("answering should have been cancelled")


def test_a_closed_stream_keeps_its_slot_until_the_worker_stops_at_the_next_stage() -> None:
    async def scenario() -> None:
        slots = asyncio.Semaphore(1)
        service = SlowService()
        stream = answer_events(service, Question("q", (), "rid"), slots)  # type: ignore[arg-type]
        first = await anext(stream)
        assert '"analyzing"' in first
        await stream.aclose()
        assert slots.locked()
        service.release.set()
        for _ in range(100):
            if not slots.locked():
                break
            await asyncio.sleep(0.02)
        assert not slots.locked()
        assert service.stopped_early.is_set()

    asyncio.run(scenario())
