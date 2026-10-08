"""Server-sent events for a question: ``stage`` events while it is answered, then ``answer``.

The question-answering pipeline is synchronous; it runs in a worker thread (bounded by a
semaphore) and reports its stages back to the event loop, which streams them to the browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from wellscope.api.schemas import AnswerEvent
from wellscope.qa.analyzer import Turn
from wellscope.qa.service import QAService, Stage

logger = logging.getLogger(__name__)
KEEPALIVE_S = 15.0
MILLISECONDS = 1000
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
Event = tuple[str, dict[str, Any]]
Events = asyncio.Queue[Event | None]


@dataclass(frozen=True)
class Question:
    """A question to stream an answer for."""

    text: str
    history: Sequence[Turn]
    request_id: str


def format_event(name: str, data: dict[str, Any]) -> str:
    """One server-sent event; JSON keeps the data on a single line."""
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def answer_events(
    qa: QAService, question: Question, slots: asyncio.Semaphore
) -> AsyncIterator[str]:
    """Stream the stages of answering ``question``, then the answer (or an error)."""
    queue: Events = asyncio.Queue()
    task = asyncio.create_task(_produce(qa, question, slots, queue))
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if item is None:
                return
            yield format_event(*item)
    finally:
        if not task.done():
            task.cancel()


async def _produce(
    qa: QAService, question: Question, slots: asyncio.Semaphore, queue: Events
) -> None:
    loop = asyncio.get_running_loop()
    started = perf_counter()

    def on_stage(stage: Stage) -> None:
        elapsed = int((perf_counter() - started) * MILLISECONDS)
        loop.call_soon_threadsafe(queue.put_nowait, ("stage", {"stage": stage, "t_ms": elapsed}))

    try:
        async with slots:
            answer = await asyncio.to_thread(qa.ask, question.text, question.history, on_stage)
        outcome = {"status": answer.status, "reason": answer.reason, "verified": answer.verified}
        logger.info("question answered", extra=outcome | {"latency_ms": answer.latency_ms})
        payload = AnswerEvent.of(answer, question.request_id).model_dump(mode="json")
        await queue.put(("answer", payload))
    except Exception:  # last-resort boundary: the stream must end with an event
        logger.exception("answering failed")
        error = {"code": "internal_error", "message": "Unexpected error."}
        await queue.put(("error", error | {"request_id": question.request_id}))
    finally:
        await queue.put(None)
