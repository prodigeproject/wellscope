"""Server-sent events for a question: ``stage`` events while it is answered, then ``answer``.

The question-answering pipeline is synchronous; it runs in a worker thread (bounded by a
semaphore) and reports its stages back to the event loop, which streams them to the browser.
When the browser goes away, the worker stops at its next stage boundary and keeps its slot
until it has actually stopped, so the concurrency limit always holds. An answer that is not
ready by the deadline ends the stream with an ``answer_timeout`` error (the brief allows three
minutes); its worker then stops the same way.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from wellscope.api.schemas import AnswerEvent
from wellscope.qa.analyzer import Turn
from wellscope.qa.service import Answer, QAService, Stage, StageCancelled

logger = logging.getLogger(__name__)
KEEPALIVE_S = 15.0
ANSWER_DEADLINE_S = 170.0
MILLISECONDS = 1000
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
Event = tuple[str, dict[str, Any]]
Events = asyncio.Queue[Event | None]
# Producers outlive a closed stream until their worker stops; keep them referenced meanwhile.
_RUNNING: set[asyncio.Task[None]] = set()


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
    qa: QAService,
    question: Question,
    slots: asyncio.Semaphore,
    deadline_s: float = ANSWER_DEADLINE_S,
) -> AsyncIterator[str]:
    """Stream the stages of answering ``question``, then the answer (or an error)."""
    queue: Events = asyncio.Queue()
    cancelled = threading.Event()
    task = asyncio.create_task(_produce(qa, question, slots, queue, cancelled, deadline_s))
    _RUNNING.add(task)
    task.add_done_callback(_RUNNING.discard)
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
        cancelled.set()


async def _produce(
    qa: QAService,
    question: Question,
    slots: asyncio.Semaphore,
    queue: Events,
    cancelled: threading.Event,
    deadline_s: float,
) -> None:
    loop = asyncio.get_running_loop()
    started = perf_counter()

    def on_stage(stage: Stage) -> None:
        if cancelled.is_set():
            raise StageCancelled
        elapsed = int((perf_counter() - started) * MILLISECONDS)
        loop.call_soon_threadsafe(queue.put_nowait, ("stage", {"stage": stage, "t_ms": elapsed}))

    try:
        async with slots:
            worker = asyncio.ensure_future(
                asyncio.to_thread(qa.ask, question.text, question.history, on_stage)
            )
            try:
                answer = await asyncio.wait_for(asyncio.shield(worker), deadline_s)
            except TimeoutError:
                await _time_out(worker, question, queue, cancelled, deadline_s)
                return
        event = AnswerEvent.of(answer, question.request_id)
        outcome = {"status": answer.status, "reason": answer.reason, "verified": answer.verified}
        usage = {"latency_ms": answer.latency_ms, "cost_usd": event.meta.cost_usd}
        logger.info("question answered", extra=outcome | usage)
        payload = event.model_dump(mode="json")
        await queue.put(("answer", payload))
    except StageCancelled:
        logger.info("answering stopped: the client went away")
    except Exception:  # last-resort boundary: the stream must end with an event
        logger.exception("answering failed")
        error = {"code": "internal_error", "message": "Unexpected error."}
        await queue.put(("error", error | {"request_id": question.request_id}))
    finally:
        await queue.put(None)


async def _time_out(
    worker: asyncio.Future[Answer],
    question: Question,
    queue: Events,
    cancelled: threading.Event,
    deadline_s: float,
) -> None:
    """End the stream with a timeout error, then wait (holding the slot) for the worker to stop."""
    cancelled.set()
    logger.warning("answering timed out", extra={"deadline_s": deadline_s})
    error = {"code": "answer_timeout", "message": "The answer took too long. Please try again."}
    await queue.put(("error", error | {"request_id": question.request_id}))
    await queue.put(None)
    with contextlib.suppress(Exception):
        await worker
