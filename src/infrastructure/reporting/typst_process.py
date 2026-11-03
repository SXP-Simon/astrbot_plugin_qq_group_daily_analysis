"""Typst 隔离编译进程的限时执行与回收。"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path


async def run_typst_worker(
    job_dir: Path, font_dir: Path, timeout_seconds: float
) -> None:
    """限时执行隔离编译，取消或超时后等待子进程退出再清理目录。

    Args:
        job_dir: 本次编译专用目录。
        font_dir: 受管理字体目录。
        timeout_seconds: 编译允许的最长秒数。

    Raises:
        TimeoutError: 编译超时且进程已终止。
        RuntimeError: 编译器返回失败。
    """
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        str(Path(__file__).with_name("typst_worker.py")),
        str(job_dir),
        str(font_dir),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    communication = asyncio.create_task(process.communicate())
    try:
        async with asyncio.timeout(timeout_seconds):
            _, stderr = await asyncio.shield(communication)
    except BaseException:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await asyncio.shield(communication)
        raise
    if process.returncode:
        raise RuntimeError((stderr or b"").decode("utf-8", errors="replace")[:1800])
