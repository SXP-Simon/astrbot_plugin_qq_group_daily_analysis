"""图片渲染适配器共用的父子阶段记录。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ...shared.trace_context import SpanRecord, TraceContext
from .render_diagnostics import summarize_render_error

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def render_span(
    stage: str, payload: dict[str, object] | None = None
) -> AsyncIterator[SpanRecord | None]:
    """启用追踪时，将渲染步骤记录到当前尝试或明确指定的父阶段。

    Args:
        stage: 任务面板使用的阶段标识。
        payload: 不包含报告正文或凭据的诊断字段，可明确指定父阶段。

    Yields:
        可写的阶段记录；离线渲染时返回 None。

    Raises:
        asyncio.CancelledError: 记录取消状态后继续传播取消请求。
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
        details.setdefault("parent_span_id", parent["span_id"])
    span = None
    try:
        async with trace.span_async(stage, details) as span:
            try:
                yield span
            except asyncio.CancelledError:
                span["status"] = "cancelled"
                span["payload"]["cancelled"] = True
                raise
    except Exception as error:
        if span:
            span["payload"]["error"] = (
                summarize_render_error(str(error)) or type(error).__name__
            )
        raise
