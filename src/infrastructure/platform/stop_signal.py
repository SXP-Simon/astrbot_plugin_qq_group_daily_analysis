"""宿主前台停止信号桥接

AstrBot 的 /stop 是协作式取消：它给本会话的活跃事件打上 ``agent_stop_requested``
标记。命令式插件需要主动读取标记，才能取消自己创建的工作任务。

本模块读取宿主的公开事件状态（``event.get_extra``），并将停止监听任务登记到
宿主的后台任务表，使内置 stop 能发现独立执行的群分析；不注册同名命令。

两点刻意的取舍：

- 不读 ``event.is_stopped()``。该接口的语义是「终止事件传播」，任何地方调用
  ``event.stop_event()`` 都会置位，与用户主动停止无关，混用会误杀正常运行的任务。
- 不向宿主注册停止回调。宿主的回调槽位是每个事件一个（dict[event, callback]），
  注册会覆盖 Agent 运行器已有的回调、注销会把槽位删掉，属于侵入宿主内部状态。
  新版宿主通过后台任务登记立即取消监听器，旧版保留前台事件标记轮询。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

from ...application.services.stop_request import StopRequest
from ...utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from astrbot.api.event import AstrMessageEvent

STOP_EXTRA_KEY = "agent_stop_requested"
"""宿主 /stop 命令写入的停止标记键名。"""

STOP_POLL_INTERVAL_SECONDS = 0.5
"""轮询间隔（秒），与宿主 Agent 运行器的检查节奏一致。"""


class FrontendStopWatcher:
    """把宿主停止标记桥接为 StopRequest。

    生命周期由调用方管理：处理开始前 ``start()``，结束后 ``stop()``。

    Args:
        event: AstrBot 原始命令事件，按该事件读取停止标记。
        poll_interval: 后台轮询间隔，发送边界仍会显式即时读取。
    """

    def __init__(
        self,
        event: AstrMessageEvent,
        *,
        poll_interval: float = STOP_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._event: AstrMessageEvent = event
        self._poll_interval = poll_interval
        self._poll_task: asyncio.Task[None] | None = None
        self._host_stop_signal: asyncio.Event | None = None
        self._stop_request = StopRequest(self._read_host_stop)
        self._read_error_logged = False
        origin = getattr(event, "unified_msg_origin", "")
        self._origin = origin if isinstance(origin, str) else ""

    @property
    def stop_request(self) -> StopRequest:
        """本次任务的停止请求对象。"""
        return self._stop_request

    @property
    def watching(self) -> bool:
        """轮询是否已启动。"""
        return self._poll_task is not None and not self._poll_task.done()

    async def start(self) -> None:
        """启动停止监听。

        事件对象不支持读取标记时记一次警告并放弃监听，避免无意义轮询。

        Returns:
            None
        """
        if not callable(getattr(self._event, "get_extra", None)):
            logger.warning(
                "宿主事件不支持停止标记读取，/stop 对本次任务无效；"
                "请确认 AstrBot 版本支持 agent_stop_requested"
            )
            return
        self._poll_task = asyncio.create_task(self._poll_loop())
        # 内置 stop 可能在首次调度前取消监听器，完成回调也必须传递停止标记。
        self._poll_task.add_done_callback(
            lambda task: (
                self._stop_request.request()
                if task.cancelled() and task is self._poll_task
                else None
            )
        )
        if self._origin:
            try:
                from astrbot.core.utils.active_event_registry import (
                    active_event_registry,
                )

                register_background: (
                    Callable[[AstrMessageEvent, asyncio.Task[None]], None] | None
                ) = getattr(active_event_registry, "register_background_task", None)
                if callable(register_background):
                    self._host_stop_signal = (
                        active_event_registry.get_background_stop_signal(self._event)
                    )
                    register_background(self._event, self._poll_task)
            except ImportError:
                logger.debug("宿主未提供后台任务登记接口，继续监听前台事件停止标记")
            except Exception as error:
                logger.warning(
                    "登记宿主停止监听任务失败，继续读取事件停止标记: %s", error
                )
        logger.debug("已启动群分析停止监听: umo=%s", self._origin or "未知")

    async def stop(self) -> None:
        """停止监听，可重复调用。

        Returns:
            None
        """
        task = self._poll_task
        self._poll_task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def stop_now(self) -> None:
        """同步请求监听协程退出，供无法 await 的收尾路径使用。

        Returns:
            None
        """
        task = self._poll_task
        self._poll_task = None
        if task is not None and not task.done():
            task.cancel()

    def _read_host_stop(self) -> bool:
        """读取宿主停止标记，兼容缺少接口及临时读取失败的宿主。

        Returns:
            是否观察到宿主的停止请求；读取失败时保持当前任务继续运行。
        """
        # Agent 收尾可能清空事件布尔标记，共享停止信号在本事件结束前保持置位。
        if self._host_stop_signal is not None and self._host_stop_signal.is_set():
            return True
        get_extra = cast(
            "Callable[[str], object] | None", getattr(self._event, "get_extra", None)
        )
        if not callable(get_extra):
            return False
        try:
            return bool(get_extra(STOP_EXTRA_KEY))
        except Exception as e:
            if not self._read_error_logged:
                self._read_error_logged = True
                logger.warning(f"读取宿主停止标记失败，将继续重试: {e}")
            return False

    async def _poll_loop(self) -> None:
        """轮询宿主停止标记。

        单次读取异常只记一次警告并继续轮询，不因此永久放弃监听。
        """
        while True:
            if self._stop_request.refresh():
                logger.info("检测到宿主停止标记 (agent_stop_requested)，中止前台任务")
                return
            await asyncio.sleep(self._poll_interval)
