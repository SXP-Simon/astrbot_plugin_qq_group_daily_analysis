"""图片渲染适配器共用的父子阶段记录。"""

from __future__ import annotations

import asyncio
import math
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
    finally:
        if stage in ("TYPST_COMPILE", "TYPST_RECOVERY"):
            publish_typst_memory(span)


def publish_typst_memory(span: SpanRecord | None) -> None:
    """把串行 Typst 编译的最大峰值与增长量传递给真实父阶段。

    Args:
        span: 已填充子进程测量值的编译阶段；不修改宿主 RSS 口径。
    """
    trace = TraceContext.current()
    if not trace or not span:
        return
    payload = span["payload"]
    measurements = {}
    for source, target in (
        ("worker_peak_rss_mb", "typst_peak_rss_mb"),
        ("worker_peak_delta_mb", "typst_peak_delta_mb"),
    ):
        value = payload.get(source)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        ):
            measurements[target] = value
    if not measurements:
        return
    by_id = {record["span_id"]: record for record in trace._spans}
    parent_id = payload.get("parent_span_id")
    visited = {span["span_id"]}
    while isinstance(parent_id, str) and parent_id not in visited:
        parent = by_id.get(parent_id)
        if parent is None:
            break
        visited.add(parent_id)
        parent_payload = parent["payload"]
        for key, value in measurements.items():
            previous = parent_payload.get(key)
            if (
                not isinstance(previous, (int, float))
                or not math.isfinite(previous)
                or value >= previous
            ):
                parent_payload[key] = value
                if key == "typst_peak_rss_mb":
                    parent_payload["typst_rss_source"] = payload.get(
                        "worker_rss_source", "unknown"
                    )
        if payload.get("worker_metrics_partial") is True:
            parent_payload["typst_metrics_partial"] = True
        parent_id = parent_payload.get("parent_span_id")
