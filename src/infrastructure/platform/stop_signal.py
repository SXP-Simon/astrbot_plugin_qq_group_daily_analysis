"""宿主前台停止信号桥接

AstrBot 的 /stop 是协作式取消：它给本会话的活跃事件打上 ``agent_stop_requested``
标记。命令式插件需要主动读取标记，才能取消自己创建的工作任务。

本模块读取宿主的公开事件状态（``event.get_extra``），并登记本插件的活跃监听器，
使宿主未登记命令任务时仍能按同一会话接收 stop 请求。

两点刻意的取舍：

- 不读 ``event.is_stopped()``。该接口的语义是「终止事件传播」，任何地方调用
  ``event.stop_event()`` 都会置位，与用户主动停止无关，混用会误杀正常运行的任务。
- 不向宿主注册停止回调。宿主的回调槽位是每个事件一个（dict[event, callback]），
  注册会覆盖 Agent 运行器已有的回调、注销会把槽位删掉，属于侵入宿主内部状态。
  0.5 秒轮询对分钟级任务没有体感差异，且只依赖公开接口。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast
from weakref import WeakSet

from ...application.services.stop_request import StopRequest
from ...utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import ClassVar

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

    _active: ClassVar[WeakSet[FrontendStopWatcher]] = WeakSet()

    def __init__(
        self,
        event: AstrMessageEvent,
        *,
        poll_interval: float = STOP_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._event: AstrMessageEvent = event
        self._poll_interval = poll_interval
        self._poll_task: asyncio.Task[None] | None = None
        self._stop_request = StopRequest(self._read_host_stop)
        self._read_error_logged = False
        origin = getattr(event, "unified_msg_origin", "")
        self._origin = origin if isinstance(origin, str) else ""

    @classmethod
    def request_stop_for(cls, event: AstrMessageEvent) -> int:
        """请求停止同一宿主会话的插件任务，同时保留宿主 Agent 的停止语义。

        Args:
            event: 已通过宿主命令匹配的 stop 事件。

        Returns:
            匹配到的活跃插件监听器数量；零表示继续由宿主处理。
        """
        origin = getattr(event, "unified_msg_origin", "")
        if not isinstance(origin, str) or not origin:
            return 0
        matches = [
            watcher for watcher in tuple(cls._active) if watcher._origin == origin
        ]
        if not matches:
            logger.debug(
                "收到 stop，但当前会话没有手动群分析监听器: umo=%s，活跃监听数=%s",
                origin,
                len(cls._active),
            )
            return 0
        for watcher in matches:
            watcher.stop_request.request()
        # 不注册或覆盖宿主回调，只复用宿主公开的同会话停止接口。
        try:
            from astrbot.core.utils.active_event_registry import active_event_registry

            active_event_registry.request_agent_stop_all(origin, exclude=event)
        except Exception as error:
            logger.warning("插件任务已收到停止请求，宿主停止桥接未完成: %s", error)
        logger.info(
            "收到 stop 命令，中止同会话群分析任务: umo=%s，任务数=%s",
            origin,
            len(matches),
        )
        return len(matches)

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
        self._active.add(self)
        logger.debug("已启动群分析停止监听: umo=%s", self._origin or "未知")

    async def stop(self) -> None:
        """停止监听，可重复调用。

        Returns:
            None
        """
        task = self._poll_task
        self._active.discard(self)
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
        self._active.discard(self)
        self._poll_task = None
        if task is not None and not task.done():
            task.cancel()

    def _read_host_stop(self) -> bool:
        """读取宿主停止标记，兼容缺少接口及临时读取失败的宿主。

        Returns:
            是否观察到宿主的停止请求；读取失败时保持当前任务继续运行。
        """
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
