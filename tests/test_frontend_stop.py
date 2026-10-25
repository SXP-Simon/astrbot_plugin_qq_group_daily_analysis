"""前台停止信号桥接与手动分析中止的验收测试。

事件桩复刻宿主语义：is_stopped() 表示「终止事件传播」，与用户 /stop 无关。
"""

import asyncio
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from frontend_stop_support import (
    CaptionConfig,
    FastRenderGenerator,
    FastSuccessService,
    FlakyEvent,
    HostEvent,
    ImageConfig,
    NoExtraEvent,
    ReportResultService,
    SlowRenderGenerator,
    SlowSendingAdapter,
    StubAdapter,
    StubAnalysisService,
    StubbornService,
    StubConfig,
    StubTaskManager,
    _spy_trace,
    make_handler,
)

from src.application.handlers.analysis_command_handler import AnalysisStoppedError
from src.application.services.stop_request import StopRequest
from src.application.services.task_guard import TaskGuard
from src.domain.value_objects.task_event import TaskEvent
from src.infrastructure.platform.stop_signal import (
    STOP_EXTRA_KEY,
    FrontendStopWatcher,
    StopSignalEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from src.shared.trace_context import TraceContext


# ── StopRequest / FrontendStopWatcher ──


def test_stop_request_is_idempotent():
    request = StopRequest()
    assert request.requested is False
    request.request()
    request.request()
    assert request.requested is True


@pytest.mark.asyncio
async def test_watcher_detects_host_stop_flag():
    event = HostEvent()
    watcher = FrontendStopWatcher(event, poll_interval=0.02)
    await watcher.start()
    event.set_extra("agent_stop_requested", True)
    await asyncio.wait_for(watcher.stop_request.wait(), timeout=1)
    assert watcher.stop_request.requested is True
    await watcher.stop()


@pytest.mark.asyncio
async def test_watcher_ignores_stop_event_propagation():
    """is_stopped() 是「终止事件传播」，不能当成用户停止。"""
    event = HostEvent()
    watcher = FrontendStopWatcher(event, poll_interval=0.02)
    await watcher.start()
    event.stop_event()
    await asyncio.sleep(0.1)
    assert event.is_stopped() is True
    assert watcher.stop_request.requested is False
    await watcher.stop()


@pytest.mark.asyncio
async def test_watcher_keeps_polling_after_read_errors():
    """单次读取异常不能永久放弃监听。"""
    event = FlakyEvent(failures=2)
    watcher = FrontendStopWatcher(event, poll_interval=0.02)
    await watcher.start()
    event.set_extra(STOP_EXTRA_KEY, True)
    await asyncio.wait_for(watcher.stop_request.wait(), timeout=1)
    assert watcher.stop_request.requested is True
    await watcher.stop()


@pytest.mark.asyncio
async def test_watcher_without_get_extra_does_not_start():
    watcher = FrontendStopWatcher(cast("StopSignalEvent", NoExtraEvent()))
    await watcher.start()
    assert watcher.watching is False
    await watcher.stop()


@pytest.mark.asyncio
async def test_watcher_stop_is_safe_to_call_twice():
    watcher = FrontendStopWatcher(HostEvent(), poll_interval=0.02)
    await watcher.start()
    await watcher.stop()
    await watcher.stop()


# ── handler 集成 ──


@pytest.mark.asyncio
async def test_handler_aborts_work_and_releases_group_lock():
    guard = TaskGuard(2)
    service = StubAnalysisService(guard)
    manager = StubTaskManager()
    handler = make_handler(service, manager)
    event = HostEvent()
    delivered: list[object] = []

    async def consume() -> None:
        async for item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            delivered.append(item)

    consumer = asyncio.create_task(consume())
    await asyncio.wait_for(service.started.wait(), timeout=2)
    assert guard.is_group_running("123456", "daily") is True

    stop_requested_at = time.monotonic()
    event.set_extra(STOP_EXTRA_KEY, True)
    await asyncio.wait_for(consumer, timeout=3)
    stop_latency = time.monotonic() - stop_requested_at

    assert stop_latency < 2.5
    assert service.cancelled is True
    assert guard.is_group_running("123456", "daily") is False
    assert manager.active == set()
    assert len(manager.finished) == 1  # 收尾只做一次
    texts = [getattr(item, "text", None) for item in delivered]
    assert len(texts) == 1  # 只有启动提示，停止不额外发消息


@pytest.mark.asyncio
async def test_handler_finishes_when_work_swallows_cancel(
    monkeypatch: pytest.MonkeyPatch,
):
    """子任务吞掉取消时，超时后仍要收尾并回执，不能无限挂住。"""
    from src.application.handlers import analysis_command_handler as handler_module

    monkeypatch.setattr(handler_module, "STOP_GRACE_SECONDS", 0.2)

    service = StubbornService()
    manager = StubTaskManager()
    handler = make_handler(service, manager)
    event = HostEvent()
    delivered: list[object] = []

    async def consume() -> None:
        async for item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            delivered.append(item)

    consumer = asyncio.create_task(consume())
    await asyncio.wait_for(service.started.wait(), timeout=2)
    event.set_extra(STOP_EXTRA_KEY, True)
    started_at = time.monotonic()
    await asyncio.wait_for(consumer, timeout=3)
    elapsed = time.monotonic() - started_at

    # 子任务吞掉取消后，宽限期（0.2s）必须真的等满才继续收尾
    assert elapsed >= 0.2
    assert manager.finished
    assert service.cancel_received.is_set()

    service.release = True
    if service.task is not None:
        service.task.cancel()
        await asyncio.gather(service.task, return_exceptions=True)


@pytest.mark.asyncio
async def test_handler_cancel_without_stop_flag_keeps_silent():
    """插件重载/卸载取消宿主任务时，不应给群发「已停止」回执。"""
    guard = TaskGuard(2)
    service = StubAnalysisService(guard)
    handler = make_handler(service, StubTaskManager())
    event = HostEvent()
    delivered: list[object] = []

    async def consume() -> None:
        async for item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            delivered.append(item)

    consumer = asyncio.create_task(consume())
    await asyncio.wait_for(service.started.wait(), timeout=2)

    consumer.cancel()
    await asyncio.gather(consumer, return_exceptions=True)

    assert len(delivered) == 1  # 只有启动提示，取消后不再有报告
    assert guard.is_group_running("123456", "daily") is False


@pytest.mark.asyncio
async def test_finalize_stopped_analysis_marks_cancel_reason():
    service = StubAnalysisService(TaskGuard(1))
    manager = StubTaskManager()
    handler = make_handler(service, manager)
    calls: list[dict[str, object]] = []
    trace = SimpleNamespace(
        status="running",
        finish=lambda **kwargs: calls.append(kwargs),
    )

    await handler._finalize_stopped_analysis(
        "trace_1", cast("TraceContext", trace), "123456"
    )

    assert calls and calls[0]["event"] == TaskEvent.CANCEL
    assert calls[0]["error_message"] == "用户通过 stop 中止了本次分析"
    assert manager.finished == ["trace_1"]


def test_real_trace_accepts_cancel_transition():
    """真实 TraceContext 的 RUNNING → CANCEL 转移必须合法且落到 aborted。"""
    from src.shared.trace_context import TraceContext

    trace = TraceContext(trace_id="stop_cancel_probe", group_id="g")
    assert trace.status == "running"

    trace.finish(
        event=TaskEvent.CANCEL, error_message="Task cancelled by frontend stop request"
    )

    assert trace.status == "aborted"
    assert trace.error_message == "Task cancelled by frontend stop request"


@pytest.mark.asyncio
async def test_stop_during_render_aborts_and_sends_nothing():
    """渲染阶段（最长的一段）也必须能被 /stop 打断。"""
    renderer = SlowRenderGenerator()
    adapter = StubAdapter()
    handler = make_handler(
        ReportResultService(adapter),
        StubTaskManager(),
        report_generator=renderer,
        config=ImageConfig(),
    )
    event = HostEvent()
    delivered: list[object] = []

    async def consume() -> None:
        async for item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            delivered.append(item)

    consumer = asyncio.create_task(consume())
    await asyncio.wait_for(renderer.started.wait(), timeout=3)

    event.set_extra(STOP_EXTRA_KEY, True)
    await asyncio.wait_for(consumer, timeout=3)

    assert renderer.cancelled is True
    texts = [getattr(item, "text", None) for item in delivered]
    assert "报告正文" not in texts and len(texts) == 1  # 只有启动提示


class HtmlConfig(StubConfig):
    def get_output_format(self) -> list[str]:
        return ["html"]

    def get_report_template(self) -> str:
        return "default"


class SlowHtmlGenerator:
    """HTML 报告渲染桩。"""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def generate_html_report(self, *args: object, **kwargs: object):
        self.started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return ("/tmp/report.html", "/tmp/report.json")


@pytest.mark.asyncio
async def test_stop_during_html_render_is_not_swallowed():
    """html 分支的停止必须穿过多层 except Exception 到达 handler。"""
    generator = SlowHtmlGenerator()
    handler = make_handler(
        ReportResultService(StubAdapter()),
        StubTaskManager(),
        report_generator=generator,
        config=HtmlConfig(),
    )
    event = HostEvent()
    delivered: list[object] = []

    async def consume() -> None:
        async for item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            delivered.append(item)

    consumer = asyncio.create_task(consume())
    await asyncio.wait_for(generator.started.wait(), timeout=3)

    event.set_extra(STOP_EXTRA_KEY, True)
    await asyncio.wait_for(consumer, timeout=3)

    assert generator.cancelled is True
    assert len(delivered) == 1  # 只有启动提示，没有 HTML 交付消息


@pytest.mark.asyncio
async def test_stop_signal_passes_through_text_send_fallback():
    """文本回退路径的 except Exception 不能吞掉停止信号。"""

    class BoomAdapter(StubAdapter):
        async def send_text_report(self, *args: object, **kwargs: object) -> None:
            raise AnalysisStoppedError

    class TextReportGenerator:
        def generate_text_report(self, analysis_result: dict[str, object]) -> str:
            return "回退报告文本"

    handler = make_handler(
        FastSuccessService(),
        StubTaskManager(),
        report_generator=TextReportGenerator(),
    )
    with pytest.raises(AnalysisStoppedError):
        await handler._send_text_reports(  # type: ignore[arg-type]
            "123456", {}, False, BoomAdapter()
        )


@pytest.mark.asyncio
async def test_stop_during_upload_keeps_send_but_finalizes_cleanly(monkeypatch):
    """发送阶段停止：上传已经发出不可撤销，但收尾必须干净、不重复发消息。

    走真实的 send_analysis_report（不替换该方法），只替换落盘与图床上传。
    """
    captured = _spy_trace(monkeypatch)
    watchers = []
    watcher_type = FrontendStopWatcher

    def capture_watcher(event):
        watcher = watcher_type(event, poll_interval=0.01)
        watchers.append(watcher)
        return watcher

    adapter = SlowSendingAdapter()
    manager = StubTaskManager()
    handler = make_handler(
        ReportResultService(adapter),
        manager,
        report_generator=FastRenderGenerator(),
        config=CaptionConfig(),
        stop_watcher_factory=capture_watcher,
    )
    monkeypatch.setattr(handler, "_save_report_to_history", lambda *_a, **_k: None)

    async def noop_upload(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(handler, "_try_upload_image", noop_upload)

    event = HostEvent()
    delivered: list[object] = []

    async def consume() -> None:
        async for item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            delivered.append(item)

    consumer = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(adapter.started.wait(), timeout=3)
        event.set_extra("agent_stop_requested", True)
        await asyncio.wait_for(watchers[0].stop_request.wait(), timeout=1)
        adapter.release.set()
        await asyncio.wait_for(consumer, timeout=3)
    finally:
        adapter.release.set()
        if not consumer.done():
            consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)

    assert adapter.completed is True  # 上传已完成，停止不会撤回
    assert len(delivered) == 1  # 只有启动提示
    assert manager.finished  # 收尾照常完成
    assert captured["trace"].status == "aborted"


class ExplodingStubbornService:
    """宽限期后仍未退出，且最终以异常结束的任务。"""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.task: asyncio.Task[object] | None = None
        self.release = False

    def is_group_running(self, group_id: str, task_type: str = "daily") -> bool:
        return False

    async def execute_daily_analysis(self, **kwargs: object) -> dict[str, object]:
        self.task = asyncio.current_task()
        self.started.set()
        while True:
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                if self.release:
                    raise RuntimeError("孤儿任务失败") from None
                continue
        return {"success": True}


@pytest.mark.asyncio
async def test_orphan_task_exception_is_retrieved(monkeypatch: pytest.MonkeyPatch):
    """宽限期超时后放弃的子任务，其异常必须被取回，不能落到事件循环兜底。"""
    from src.application.handlers import analysis_command_handler as handler_module

    monkeypatch.setattr(handler_module, "STOP_GRACE_SECONDS", 0.1)

    service = ExplodingStubbornService()
    handler = make_handler(service, StubTaskManager())
    event = HostEvent()

    async def consume() -> None:
        async for _item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            pass

    loop = asyncio.get_running_loop()
    reported: list[dict[str, object]] = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, ctx: reported.append(dict(ctx)))
    warnings: list[str] = []
    monkeypatch.setattr(
        handler_module.logger,
        "warning",
        lambda msg, *_a, **_k: warnings.append(str(msg)),
    )
    try:
        consumer = asyncio.create_task(consume())
        await asyncio.wait_for(service.started.wait(), timeout=2)
        event.set_extra(STOP_EXTRA_KEY, True)
        await asyncio.wait_for(consumer, timeout=3)

        assert service.task is not None
        service.release = True
        service.task.cancel()
        # 刻意不 gather：gather 会自己取回异常，掩盖回调是否生效
        await asyncio.sleep(0.15)
    finally:
        loop.set_exception_handler(previous)

    assert reported == []
    assert any("孤儿前台任务结束后抛出异常" in m for m in warnings)


class GatedService:
    """完成时机由用例控制的假服务。"""

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.started = asyncio.Event()

    def is_group_running(self, group_id: str, task_type: str = "daily") -> bool:
        return False

    async def execute_daily_analysis(self, **kwargs: object) -> dict[str, object]:
        self.started.set()
        await self.gate.wait()
        return {"success": True}


async def _report_stub(
    event: HostEvent,
    _result: dict[str, object],
    _stop_request: object = None,
) -> "AsyncGenerator[object, None]":
    yield event.plain_result("报告正文")


@pytest.mark.asyncio
async def test_stop_wins_when_work_still_running(monkeypatch: pytest.MonkeyPatch):
    """停止先到：任务未完成，报告一条都不该发。"""
    captured = _spy_trace(monkeypatch)
    service = GatedService()
    handler = make_handler(service, StubTaskManager())
    monkeypatch.setattr(handler, "send_analysis_report", _report_stub)

    event = HostEvent()
    delivered: list[object] = []

    async def consume() -> None:
        async for item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            delivered.append(item)

    consumer = asyncio.create_task(consume())
    await asyncio.wait_for(service.started.wait(), timeout=2)

    event.set_extra(STOP_EXTRA_KEY, True)
    await asyncio.wait_for(consumer, timeout=3)

    texts = [getattr(item, "text", None) for item in delivered]
    assert texts.count("报告正文") == 0
    assert getattr(captured.get("trace"), "status", None) == "aborted"


@pytest.mark.asyncio
async def test_completion_wins_when_work_finishes_first(
    monkeypatch: pytest.MonkeyPatch,
):
    """完成先到：报告照发，trace 正常结束，停不停止都不再影响。"""
    captured = _spy_trace(monkeypatch)
    service = GatedService()
    handler = make_handler(service, StubTaskManager())
    monkeypatch.setattr(handler, "send_analysis_report", _report_stub)

    event = HostEvent()
    delivered: list[object] = []

    async def consume() -> None:
        async for item in handler.handle_daily_analysis(event):  # type: ignore[arg-type]
            delivered.append(item)

    consumer = asyncio.create_task(consume())
    await asyncio.wait_for(service.started.wait(), timeout=2)

    service.gate.set()  # 先完成
    await asyncio.wait_for(consumer, timeout=3)

    texts = [getattr(item, "text", None) for item in delivered]
    assert texts.count("报告正文") == 1
    assert getattr(captured.get("trace"), "status", None) == "succeeded"
