"""手动分析准备阶段及表情回应的停止边界。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from frontend_stop_support import (
    DeliveryAdapter,
    HostEvent,
    OutputConfig,
    ReportResultService,
    StubTaskManager,
    _spy_trace,
    make_handler,
)

from src.infrastructure.platform.stop_signal import FrontendStopWatcher


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage",
    ["group_info", "register", "analysis_started", "analysis_done", "update_stage"],
)
@pytest.mark.parametrize("stop_mode", ["stop", "host_cancel", "normal"])
async def test_preparation_waits_are_stoppable(stage, stop_mode, monkeypatch):
    captured = _spy_trace(monkeypatch)
    started, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    watchers = []

    async def wait_for_release():
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    class Adapter(DeliveryAdapter):
        def __init__(self):
            super().__init__()
            self.reactions = []

        async def get_group_info(self, _group_id):
            if stage == "group_info":
                await wait_for_release()
            return SimpleNamespace(group_name="测试群")

        async def set_reaction(self, _group_id, _message_id, reaction):
            self.reactions.append(reaction)
            if stage == reaction:
                await wait_for_release()
            return True

    class Manager(StubTaskManager):
        registered_parent = None

        async def register_task(self, task_id, **kwargs):
            self.registered_parent = kwargs["asyncio_task"]
            await super().register_task(task_id, **kwargs)
            if stage == "register":
                await wait_for_release()

        async def update_stage(self, *_args):
            if stage == "update_stage":
                await wait_for_release()

    def factory(event):
        watcher = FrontendStopWatcher(event, poll_interval=0.01)
        watchers.append(watcher)
        return watcher

    adapter, manager, event = Adapter(), Manager(), HostEvent()
    service = SimpleNamespace(
        is_group_running=Mock(return_value=False),
        execute_daily_analysis=AsyncMock(
            return_value={
                "success": True,
                "group_id": "123456",
                "platform_id": "aiocqhttp_1",
                "analysis_result": {},
                "adapter": adapter,
            }
        ),
    )
    config = OutputConfig("text")
    monkeypatch.setattr(config, "get_enable_analysis_reply", lambda: False)
    handler = make_handler(
        service,
        manager,
        config=config,
        report_generator=SimpleNamespace(generate_text_report=lambda _: "报告正文"),
        stop_watcher_factory=factory,
    )
    handler.bot_manager = SimpleNamespace(
        update_from_event=lambda _: None,
        get_adapter=lambda _: adapter,
    )

    async def collect():
        return [item async for item in handler.handle_daily_analysis(event)]

    parent = asyncio.create_task(collect())
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        if stop_mode == "stop":
            event.set_extra("agent_stop_requested", True)
        elif stop_mode == "host_cancel":
            parent.cancel()
        else:
            release.set()
        # 不能让 wait_for 自己取消被测任务，否则会掩盖未响应 /stop 的缺陷。
        delivered = await asyncio.wait_for(asyncio.shield(parent), timeout=1)
        assert not delivered
        assert not manager.active
        assert len(watchers) == 1
        assert not watchers[0].watching
        if stop_mode != "normal":
            assert cancelled.is_set()
            assert not adapter.sent
            if stage == "group_info":
                assert "trace" not in captured
                assert not manager.finished
            else:
                assert captured["trace"].status == "aborted"
                assert captured["trace"].error_message == (
                    "用户通过 stop 中止了本次分析"
                    if stop_mode == "stop"
                    else "Task cancelled by system"
                )
                assert len(manager.finished) == 1
                assert manager.registered_parent is parent
            if stage in {"group_info", "register", "analysis_started"}:
                service.execute_daily_analysis.assert_not_called()
            else:
                service.execute_daily_analysis.assert_awaited_once()
        else:
            assert not cancelled.is_set()
            assert adapter.reactions == ["analysis_started", "analysis_done"]
            assert adapter.sent == ["text"]
            assert captured["trace"].status == "succeeded"
            assert captured["trace"].group_name == "测试群"
            assert len(manager.finished) == 1
            assert manager.registered_parent is parent
            service.execute_daily_analysis.assert_awaited_once()
    finally:
        release.set()
        if not parent.done():
            parent.cancel()
        await asyncio.gather(parent, return_exceptions=True)


@pytest.mark.asyncio
async def test_stop_before_preparation_does_not_start_group_query(monkeypatch):
    captured = _spy_trace(monkeypatch)
    adapter = DeliveryAdapter()
    adapter.get_group_info = AsyncMock(
        return_value=SimpleNamespace(group_name="测试群")
    )
    service = SimpleNamespace(
        is_group_running=Mock(return_value=False),
        execute_daily_analysis=AsyncMock(),
    )
    manager = StubTaskManager()
    handler = make_handler(service, manager)
    handler.bot_manager = SimpleNamespace(
        update_from_event=lambda _: None,
        get_adapter=lambda _: adapter,
    )
    event = HostEvent()
    event.set_extra("agent_stop_requested", True)
    delivered = [item async for item in handler.handle_daily_analysis(event)]
    assert not delivered
    adapter.get_group_info.assert_not_awaited()
    service.execute_daily_analysis.assert_not_awaited()
    assert "trace" not in captured
    assert not manager.active


@pytest.mark.asyncio
async def test_stop_while_startup_response_is_yielded_prevents_analysis(monkeypatch):
    captured = _spy_trace(monkeypatch)
    watchers = []

    def factory(event):
        watcher = FrontendStopWatcher(event, poll_interval=0.01)
        watchers.append(watcher)
        return watcher

    service = SimpleNamespace(
        is_group_running=Mock(return_value=False),
        execute_daily_analysis=AsyncMock(),
    )
    manager, event = StubTaskManager(), HostEvent()
    handler = make_handler(service, manager, stop_watcher_factory=factory)
    stream = handler.handle_daily_analysis(event)
    try:
        startup = await anext(stream)
        assert "正在启动分析引擎" in startup.text
        event.set_extra("agent_stop_requested", True)
        assert len(watchers) == 1
        await asyncio.wait_for(watchers[0].stop_request.wait(), timeout=1)
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        service.execute_daily_analysis.assert_not_awaited()
        assert captured["trace"].status == "aborted"
        assert not manager.active
        assert len(manager.finished) == 1
        assert not watchers[0].watching
    finally:
        await stream.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("guard", ["private", "forbidden", "duplicate"])
async def test_rejected_command_does_not_start_stop_watcher(guard, monkeypatch):
    service = SimpleNamespace(
        is_group_running=Mock(return_value=guard == "duplicate"),
        execute_daily_analysis=AsyncMock(),
    )
    manager, event = StubTaskManager(), HostEvent()
    config = OutputConfig("text")
    monkeypatch.setattr(config, "is_group_allowed", lambda _: guard != "forbidden")
    if guard == "private":
        monkeypatch.setattr(event, "get_group_id", lambda: None)
    factory = Mock(side_effect=AssertionError("被拒绝的命令不应启动停止监听"))
    handler = make_handler(
        service, manager, config=config, stop_watcher_factory=factory
    )
    delivered = [item async for item in handler.handle_daily_analysis(event)]
    assert len(delivered) == 1
    assert {
        "private": "请在群聊中使用此命令",
        "forbidden": "此群未启用日常分析功能",
        "duplicate": "该群的分析任务正在执行中",
    }[guard] in delivered[0].text
    factory.assert_not_called()
    service.execute_daily_analysis.assert_not_awaited()
    assert not manager.active


@pytest.mark.asyncio
async def test_group_info_failure_still_allows_analysis(monkeypatch):
    """普通群信息查询失败仍可降级，不能与用户停止混淆。"""
    captured = _spy_trace(monkeypatch)
    adapter = DeliveryAdapter()
    adapter.get_group_info = AsyncMock(side_effect=RuntimeError("群信息暂时不可用"))
    manager = StubTaskManager()
    handler = make_handler(
        ReportResultService(adapter),
        manager,
        config=OutputConfig("text"),
        report_generator=SimpleNamespace(generate_text_report=lambda _: "报告正文"),
    )
    handler.bot_manager = SimpleNamespace(
        update_from_event=lambda _: None,
        get_adapter=lambda _: adapter,
    )
    delivered = [item async for item in handler.handle_daily_analysis(HostEvent())]
    assert len(delivered) == 1
    assert adapter.sent == ["text"]
    assert captured["trace"].status == "succeeded"
    assert captured["trace"].group_name == ""
    assert not manager.active
    assert len(manager.finished) == 1
