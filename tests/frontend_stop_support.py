"""停止与报告交付测试共用的事件、服务和平台桩。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from src.application.services.task_guard import TaskGuard
from src.infrastructure.platform.stop_signal import FrontendStopWatcher


class HostEvent:
    """贴近宿主语义的事件桩。

    stop_event() 会置位 is_stopped()，模拟宿主内部终止事件传播；
    用户 /stop 走的是 agent_stop_requested 标记，两者互不相干。
    """

    def __init__(self, group_id: str = "123456") -> None:
        self._extra: dict[str, object] = {}
        self._force_stopped = False
        self.unified_msg_origin = f"aiocqhttp:GroupMessage:{group_id}"
        self.message_obj = SimpleNamespace(message_id="msg_stop")
        self.sent: list[str] = []

    def should_call_llm(self, call_llm: bool) -> None:
        pass

    def get_group_id(self) -> str:
        return "123456"

    def get_platform_id(self) -> str:
        return "aiocqhttp_1"

    def get_extra(self, key: str, default: object = None) -> object:
        return self._extra.get(key, default)

    def set_extra(self, key: str, value: object) -> None:
        self._extra[key] = value

    def stop_event(self) -> None:
        self._force_stopped = True

    def is_stopped(self) -> bool:
        return self._force_stopped

    def plain_result(self, text: str) -> SimpleNamespace:
        self.sent.append(text)
        return SimpleNamespace(text=text)


class FlakyEvent(HostEvent):
    """前若干次读标记抛异常，之后恢复正常。"""

    def __init__(self, failures: int = 2) -> None:
        super().__init__()
        self._failures_left = failures

    def get_extra(self, key: str, default: object = None) -> object:
        if self._failures_left > 0:
            self._failures_left -= 1
            raise RuntimeError("temporary host error")
        return super().get_extra(key, default)


class NoExtraEvent:
    """旧版宿主：事件对象没有 get_extra。"""


class StubConfig:
    def is_group_allowed(self, target: str) -> bool:
        return True

    def get_enable_analysis_reply(self) -> bool:
        return True


class StubBotManager:
    def update_from_event(self, event: HostEvent) -> None:
        pass

    def get_adapter(self, platform_id: str) -> None:
        return None


class StubAnalysisService:
    """用真实 TaskGuard 复刻群锁，便于断言停止后锁是否释放。"""

    def __init__(self, guard: TaskGuard) -> None:
        self.guard = guard
        self.started = asyncio.Event()
        self.cancelled = False

    def is_group_running(self, group_id: str, task_type: str = "daily") -> bool:
        return self.guard.is_group_running(group_id, task_type)

    async def execute_daily_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
        manual: bool = False,
        days: int | None = None,
    ) -> dict[str, object]:
        async with self.guard.group_lock(group_id, "daily"):
            self.started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        return {"success": True}


class FastSuccessService:
    """立即完成的分析服务，用于覆盖发送阶段。"""

    def __init__(self) -> None:
        self.guard = TaskGuard(1)

    def is_group_running(self, group_id: str, task_type: str = "daily") -> bool:
        return self.guard.is_group_running(group_id, task_type)

    async def execute_daily_analysis(self, **kwargs: object) -> dict[str, object]:
        return {"success": True}


class StubbornService:
    """吞掉第一次取消的服务，用于验证超时兜底。"""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.task: asyncio.Task[object] | None = None
        self.release = False
        self.cancel_received = asyncio.Event()

    def is_group_running(self, group_id: str, task_type: str = "daily") -> bool:
        return False

    async def execute_daily_analysis(self, **kwargs: object) -> dict[str, object]:
        self.task = asyncio.current_task()
        self.started.set()
        while not self.release:
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                self.cancel_received.set()
                if self.release:
                    break
                continue
        return {"success": True}


class StubTaskManager:
    def __init__(self) -> None:
        self.active: set[str] = set()
        self.finished: list[str] = []

    async def register_task(self, task_id: str, **kwargs: object) -> None:
        self.active.add(task_id)

    async def update_stage(self, *args: object) -> None:
        pass

    async def finish_task(self, task_id: str) -> None:
        self.active.discard(task_id)
        self.finished.append(task_id)


class ImageConfig(StubConfig):
    def get_output_format(self) -> list[str]:
        return ["image"]

    def get_report_template(self) -> str:
        return "default"


class StubAdapter:
    def get_platform_name(self) -> str:
        return "telegram"


class SlowRenderGenerator:
    """渲染服务桩：模拟几十秒的长图渲染。"""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def generate_image_report(self, *args: object, **kwargs: object):
        self.started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return ("http://img.local/report.jpg", "<html></html>")


class ReportResultService(FastSuccessService):
    def __init__(self, adapter: StubAdapter) -> None:
        super().__init__()
        self.adapter = adapter

    async def execute_daily_analysis(self, **kwargs: object) -> dict[str, object]:
        return {
            "success": True,
            "group_id": "123456",
            "platform_id": "aiocqhttp_1",
            "analysis_result": {},
            "adapter": self.adapter,
        }


def make_handler(
    service: object,
    manager: StubTaskManager,
    report_generator: object | None = None,
    config: object | None = None,
    stop_watcher_factory=None,
):
    from src.application.handlers.analysis_command_handler import (
        AnalysisCommandHandler,
    )

    return AnalysisCommandHandler(
        config_manager=config or StubConfig(),  # type: ignore[arg-type]
        bot_manager=StubBotManager(),  # type: ignore[arg-type]
        analysis_service=service,  # type: ignore[arg-type]
        report_generator=report_generator or object(),  # type: ignore[arg-type]
        html_render=None,  # type: ignore[arg-type]
        active_task_manager=manager,  # type: ignore[arg-type]
        stop_watcher_factory=stop_watcher_factory
        or (lambda event: FrontendStopWatcher(event, poll_interval=0.01)),
    )


class CaptionConfig(ImageConfig):
    def get_show_report_caption(self) -> bool:
        return False


class FastRenderGenerator:
    async def generate_image_report(self, *args: object, **kwargs: object):
        return ("http://img.local/report.jpg", "<html></html>")


class SlowSendingAdapter(StubAdapter):
    """上传慢，制造"发送阶段"窗口。"""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.completed = False
        self.release = asyncio.Event()

    async def send_image(
        self, group_id: str, image_url: str, caption: str = ""
    ) -> bool:
        self.started.set()
        await self.release.wait()
        self.completed = True
        return True


def _spy_trace(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    from src.shared.trace_context import TraceContext

    captured: dict[str, object] = {}
    original_set = TraceContext.set.__func__

    def spy_set(cls: type[TraceContext], **kwargs: object) -> TraceContext:
        trace = original_set(cls, **kwargs)
        captured["trace"] = trace
        return trace

    monkeypatch.setattr(TraceContext, "set", classmethod(spy_set))
    return captured


class OutputConfig(ImageConfig):
    def __init__(self, output="image"):
        self.output = output

    def get_output_format(self):
        return [self.output]

    def get_enable_daily_comic(self):
        return True

    def get_enable_auto_daily_comic(self):
        return True

    def is_comic_group_allowed(self, *args):
        return True


class DeliveryAdapter(StubAdapter):
    platform_id = "test"

    def __init__(self, platform="telegram"):
        self.platform = platform
        self.sent = []

    def get_platform_name(self):
        return self.platform

    async def send_text_report(self, *args, **kwargs):
        self.sent.append("text")

    async def send_image(self, group_id, image_url, caption=""):
        self.sent.append(image_url)
        return True
