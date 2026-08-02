"""Context-bound progress events for the hosted functional workflow."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TypeVar

TResult = TypeVar("TResult")


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """A truthful workflow event emitted at an actual execution boundary."""

    event: str
    payload: dict[str, object]


_events = ContextVar("orchestrator_progress_events", default=None)


@asynccontextmanager
async def report_progress(queue: asyncio.Queue[ProgressEvent]) -> AsyncIterator[None]:
    """Route progress events from the current workflow task into a caller queue."""
    token = _events.set(queue)
    try:
        yield
    finally:
        _events.reset(token)


async def emit_progress(event: str, **payload: object) -> None:
    """Emit one event when the current host requested progress reporting."""
    queue = _events.get()
    if queue is not None:
        await queue.put(ProgressEvent(event=event, payload=dict(payload)))


async def run_stage[TResult](stage: str, operation: Awaitable[TResult]) -> TResult:
    """Run one operation and report transitions at its actual await boundary."""
    await emit_progress("stage", stage=stage, status="started")
    try:
        result = await operation
    except BaseException:
        await emit_progress("stage", stage=stage, status="failed")
        raise
    await emit_progress("stage", stage=stage, status="completed")
    return result
