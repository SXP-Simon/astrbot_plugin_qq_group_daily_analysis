"""Typst 隔离编译进程的限时执行与回收。"""

from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

from ...shared.trace_context import TraceContext
from .render_trace import render_span

if TYPE_CHECKING:
    from .typst_worker import TypstWorkerMetrics


_compile_slots: WeakValueDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    WeakValueDictionary()
)


class TypstWorkerError(RuntimeError):
    """携带已退出编译进程的受限诊断与测量结果。

    Args:
        message: 已限制长度的编译诊断文本。
        metrics: 失败前产生并经过校验的可选测量结果。
    """

    def __init__(self, message: str, metrics: TypstWorkerMetrics | None) -> None:
        super().__init__(message)
        self.metrics = metrics


async def run_typst_worker(
    job_dir: Path, font_dir: Path, timeout_seconds: float
) -> TypstWorkerMetrics | None:
    """限时执行隔离编译，取消或超时后等待子进程退出再清理目录。

    Args:
        job_dir: 本次编译专用目录。
        font_dir: 受管理字体目录。
        timeout_seconds: 编译允许的最长秒数。

    Returns:
        遥测开启时返回隔离编译的阶段耗时和峰值工作集；缺失遥测不影响报告。

    Raises:
        TimeoutError: 排队或编译超时，已启动的进程已终止。
        RuntimeError: 编译器返回失败。
    """
    loop = asyncio.get_running_loop()
    slot = _compile_slots.get(loop)
    if slot is None:
        slot = asyncio.Semaphore(1)
        _compile_slots[loop] = slot
    # 活跃调用持有名额对象，空闲后自动移除，不留下已关闭事件循环的引用。
    deadline = loop.time() + timeout_seconds
    details: dict[str, object] = {"render_service": "typst", "scope": "native_compile"}
    trace = TraceContext.current()
    parent = (
        next(
            (
                span
                for span in reversed(trace._spans)
                if span["stage_name"] == "TYPST_COMPILE" and span["status"] == "running"
            ),
            None,
        )
        if trace
        else None
    )
    if parent:
        details["parent_span_id"] = parent["span_id"]
    async with asyncio.timeout_at(deadline):
        acquired = False
        try:
            async with render_span("IMAGE_RENDER_QUEUE", details):
                await slot.acquire()
                acquired = True
            return await _execute_typst_worker(
                job_dir, font_dir, deadline - loop.time()
            )
        finally:
            if acquired:
                slot.release()


async def _execute_typst_worker(
    job_dir: Path, font_dir: Path, timeout_seconds: float
) -> TypstWorkerMetrics | None:
    """持有当前事件循环的共享编译名额期间执行、回收隔离进程。

    Args:
        job_dir: 本次任务目录。
        font_dir: 插件受管理字体目录。
        timeout_seconds: 排队后剩余的执行时限。

    Returns:
        通过边界校验的可选编译测量值。

    Raises:
        TimeoutError: 进程超时并已回收。
        TypstWorkerError: 编译失败，保留失败前的可选测量值。
    """
    collect_metrics = (
        TraceContext.current() is not None and TraceContext.is_metrics_enabled()
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        str(Path(__file__).with_name("typst_worker.py")),
        str(job_dir),
        str(font_dir),
        *(["--metrics"] if collect_metrics else []),
        stdout=asyncio.subprocess.PIPE
        if collect_metrics
        else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    communication = asyncio.create_task(process.communicate())
    try:
        async with asyncio.timeout(timeout_seconds):
            stdout, stderr = await asyncio.shield(communication)
    except BaseException:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await asyncio.shield(asyncio.gather(communication, return_exceptions=True))
        raise
    metrics = _parse_worker_metrics(stdout) if collect_metrics else None
    if process.returncode:
        raise TypstWorkerError(
            (stderr or b"").decode("utf-8", errors="replace")[:1800], metrics
        )
    return metrics


def _parse_worker_metrics(stdout: bytes | None) -> TypstWorkerMetrics | None:
    """在进程边界校验可选遥测，异常数据不影响已完成的图片。

    Args:
        stdout: 隔离进程的标准输出。

    Returns:
        只含非负有限数值的已知指标；无效响应返回空。
    """
    if not stdout or len(stdout) > 4096:
        return None
    try:
        raw: object = json.loads(stdout)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    metrics: TypstWorkerMetrics = {}
    for key in (
        "font_setup_ms",
        "layout_ms",
        "raster_ms",
        "worker_peak_rss_mb",
        "worker_start_rss_mb",
        "worker_peak_delta_mb",
    ):
        value = raw.get(key)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        ):
            metrics[key] = float(value)
    source = raw.get("worker_rss_source")
    if isinstance(source, str) and source in (
        "linux_proc_status",
        "windows_working_set",
        "posix_getrusage",
    ):
        metrics["worker_rss_source"] = source
    return metrics
