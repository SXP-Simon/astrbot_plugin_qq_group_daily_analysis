"""单次用例的协作式停止状态与监听契约，不依赖宿主或基础设施。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable


class StopRequest:
    """管理本次用例的停止信号及其拥有的后台任务。

    Args:
        probe: 外部停止来源的读取能力；由接入层提供，应用层不解释来源格式。
    """

    def __init__(self, probe: Callable[[], bool] | None = None) -> None:
        self._probe = probe
        self._event = asyncio.Event()
        self._tasks: set[asyncio.Task[object]] = set()

    @property
    def requested(self) -> bool:
        """只读取本地停止状态，不访问外部来源或取消任务。"""
        return self._event.is_set()

    def refresh(self) -> bool:
        """显式读取外部停止来源，并在首次命中时取消本次关联任务。

        Returns:
            本次用例是否已请求停止；一旦停止不再恢复。
        """
        if not self.requested and self._probe is not None and self._probe():
            self.request()
        return self.requested

    def request(self) -> None:
        """请求停止本次用例，重复调用不会重复取消后台任务。"""
        if self.requested:
            return
        self._event.set()
        for task in self._tasks:
            task.cancel()

    def cancel_on_stop(self, task: asyncio.Task[object]) -> None:
        """登记本次用例新建的后台任务，结束后自动解除关联。

        Args:
            task: 本次用例拥有的任务，不能传入既有或其他用例的任务。
        """
        if task.done():
            return
        if self.refresh():
            task.cancel()
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait(self) -> None:
        """等待本次用例收到停止请求。"""
        await self._event.wait()


class StopWatcher(Protocol):
    """外部停止监听的应用层契约，实现由接入层注入。"""

    @property
    def stop_request(self) -> StopRequest: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def stop_now(self) -> None: ...
