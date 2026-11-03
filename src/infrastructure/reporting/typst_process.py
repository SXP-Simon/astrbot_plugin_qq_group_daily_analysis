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

from ...shared.trace_context import TraceContext

if TYPE_CHECKING:
    from .typst_worker import TypstWorkerMetrics


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
        TimeoutError: 编译超时且进程已终止。
        RuntimeError: 编译器返回失败。
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
    if process.returncode:
        raise RuntimeError((stderr or b"").decode("utf-8", errors="replace")[:1800])
    return _parse_worker_metrics(stdout) if collect_metrics else None


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
    for key in ("font_setup_ms", "layout_ms", "raster_ms", "worker_peak_rss_mb"):
        value = raw.get(key)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        ):
            metrics[key] = float(value)
    return metrics
