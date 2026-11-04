"""按请求标识取消 WebUI 下载，不影响报告渲染或其他页面的任务。"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ..reporting.typst_fonts import FontDownloadProgress

from .web_compat import WebApiResponse, error_response, json_response, request


class DownloadCancelled(Exception):
    """用户主动停止下载，网络会话及临时文件已经清理。"""


class DownloadControl:
    """只跟踪正在运行的请求，短期保留取消标记以处理请求乱序。"""

    def __init__(self) -> None:
        self._active: dict[str, asyncio.Task[object]] = {}
        self._cancelled: dict[str, float] = {}
        self._progress: dict[str, tuple[FontDownloadProgress, float, float]] = {}

    def update_progress(
        self, download_id: object, progress: FontDownloadProgress
    ) -> None:
        """记录受控下载的最新进度，不保留已结束请求。

        Args:
            download_id: 已进入 track 的页面请求标识。
            progress: 固定来源与当前读取字节数。
        """
        if isinstance(download_id, str) and download_id in self._active:
            now = time.monotonic()
            previous = self._progress.get(download_id)
            self._progress[download_id] = (
                progress.copy(),
                previous[1] if previous else now,
                now,
            )

    async def api_progress(self) -> WebApiResponse:
        """读取一个下载的真实进度与等待时长。

        Returns:
            进行中的字节进度；尚未启动或已经结束时为 null。
        """
        try:
            body = await request.json()
            download_id = body.get("download_id") if type(body) is dict else None
            if (
                not isinstance(download_id, str)
                or str(uuid.UUID(download_id)) != download_id
            ):
                raise ValueError("下载标识无效")
        except (ValueError, TypeError):
            return error_response("下载标识无效，请刷新页面重试", status_code=400)
        snapshot = self._progress.get(download_id)
        data = None
        if snapshot:
            progress, started, updated = snapshot
            now = time.monotonic()
            data = {
                **progress,
                "elapsed_seconds": round(now - started, 1),
                "idle_seconds": round(now - updated, 1),
            }
        return json_response({"status": "ok", "data": data})

    @asynccontextmanager
    async def track(self, download_id: object) -> AsyncIterator[None]:
        """将可选请求标识绑定到当前下载，取消后保留已完成文件。

        Args:
            download_id: 页面生成的 UUID；省略时兼容旧页面。

        Yields:
            受控的下载执行区间。

        Raises:
            ValueError: 标识无效、重复或并发请求过多。
            DownloadCancelled: 此请求已被用户取消。
        """
        if download_id is None:
            yield
            return
        if (
            not isinstance(download_id, str)
            or str(uuid.UUID(download_id)) != download_id
        ):
            raise ValueError("下载标识无效，请刷新页面重试")
        self._cancelled = {
            key: expiry
            for key, expiry in self._cancelled.items()
            if expiry > time.monotonic()
        }
        if download_id in self._cancelled:
            raise DownloadCancelled
        if download_id in self._active or len(self._active) >= 64:
            raise ValueError("下载请求重复或过多，请等待当前下载结束")
        task = asyncio.current_task()
        assert task is not None
        self._active[download_id] = task
        try:
            yield
        except asyncio.CancelledError:
            if download_id in self._cancelled:
                raise DownloadCancelled from None
            raise
        finally:
            self._active.pop(download_id, None)
            self._progress.pop(download_id, None)

    async def api_cancel(self) -> WebApiResponse:
        """停止一个页面拥有的下载，等待其连接关闭和临时文件清理。

        Returns:
            幂等取消回执；无效标识返回 400。
        """
        try:
            body = await request.json()
            download_id = body.get("download_id") if type(body) is dict else None
            if (
                not isinstance(download_id, str)
                or str(uuid.UUID(download_id)) != download_id
            ):
                raise ValueError("下载标识无效")
        except (ValueError, TypeError):
            return error_response("下载标识无效，请刷新页面重试", status_code=400)
        now = time.monotonic()
        self._cancelled = {
            key: expiry for key, expiry in self._cancelled.items() if expiry > now
        }
        # 队列取消可能先于下载请求到达，保留标记；限制数量以免长期累积。
        if download_id not in self._cancelled and len(self._cancelled) >= 1024:
            return error_response("取消请求过多，请稍后重试", status_code=429)
        already_cancelled = download_id in self._cancelled
        self._cancelled[download_id] = now + 300
        task = self._active.get(download_id)
        if task is not None:
            if not already_cancelled:
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return json_response(
            {"status": "ok", "data": {"download_id": download_id, "cancelled": True}}
        )
