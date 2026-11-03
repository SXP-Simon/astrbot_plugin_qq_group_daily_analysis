"""Parent-aware spans shared by image rendering adapters."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ...shared.trace_context import SpanRecord, TraceContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def render_span(
    stage: str, payload: dict[str, object] | None = None
) -> AsyncIterator[SpanRecord | None]:
    """Record a rendering step under the current attempt, if tracing is active.

    Args:
        stage: Stage identifier shown in the task panel.
        payload: Diagnostic fields without report text or credentials.

    Yields:
        Mutable span record, or None for offline rendering.

    Raises:
        asyncio.CancelledError: Preserve cancellation after recording the stage.
    """
    trace = TraceContext.current()
    if not trace:
        yield None
        return
    details = dict(payload or {})
    parent = next(
        (
            span
            for span in reversed(trace._spans)
            if span["stage_name"] in ("IMAGE_RENDER_ATTEMPT", "RENDER_REPORT")
            and span["status"] == "running"
        ),
        None,
    )
    if parent:
        details["parent_span_id"] = parent["span_id"]
    async with trace.span_async(stage, details) as span:
        try:
            yield span
        except asyncio.CancelledError:
            span["status"] = "cancelled"
            span["payload"]["cancelled"] = True
            raise
