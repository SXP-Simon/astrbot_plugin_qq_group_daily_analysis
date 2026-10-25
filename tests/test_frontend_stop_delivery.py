import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from frontend_stop_support import (
    CaptionConfig,
    DeliveryAdapter,
    FastRenderGenerator,
    HostEvent,
    OutputConfig,
    ReportResultService,
    SlowRenderGenerator,
    SlowSendingAdapter,
    StubAnalysisService,
    StubTaskManager,
    _spy_trace,
    make_handler,
)

from src.application.handlers import analysis_command_handler as handler_module
from src.application.handlers.comic_command_handler import ComicCommandHandler
from src.application.services.stop_request import StopRequest
from src.application.services.task_guard import TaskGuard
from src.infrastructure.platform.stop_signal import FrontendStopWatcher
from src.shared.trace_context import TraceContext


async def collect(handler, event):
    return [item async for item in handler.handle_daily_analysis(event)]


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["text", "image"])
async def test_stop_cancels_qq_markdown_including_image_fallback(output, monkeypatch):
    captured = _spy_trace(monkeypatch)
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def markdown(*_args, **_kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def failed_image(*_args, **_kwargs):
        return None, None

    adapter = DeliveryAdapter("qq_official")
    manager = StubTaskManager()
    handler = make_handler(
        ReportResultService(adapter),
        manager,
        report_generator=SimpleNamespace(
            generate_markdown_report=markdown,
            generate_image_report=failed_image,
        ),
        config=OutputConfig(output),
    )
    event = HostEvent()
    task = asyncio.create_task(collect(handler, event))
    await asyncio.wait_for(started.wait(), timeout=1)
    event.set_extra("agent_stop_requested", True)
    await asyncio.wait_for(task, timeout=2)
    assert cancelled.is_set()
    assert not adapter.sent
    assert not manager.active
    assert captured["trace"].status == "aborted"


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["text", "image", "html"])
async def test_host_stop_at_completion_blocks_delivery_between_polls(
    output, monkeypatch
):
    captured = _spy_trace(monkeypatch)
    event = HostEvent()

    def text(*_args, **_kwargs):
        event.set_extra("agent_stop_requested", True)
        return "不应发送的正文"

    async def image(*_args, **_kwargs):
        event.set_extra("agent_stop_requested", True)
        return "report.png", "<html></html>"

    async def html(*_args, **_kwargs):
        event.set_extra("agent_stop_requested", True)
        return "report.html", "report.json"

    adapter = DeliveryAdapter()
    handler = make_handler(
        ReportResultService(adapter),
        StubTaskManager(),
        report_generator=SimpleNamespace(
            generate_text_report=text,
            generate_image_report=image,
            generate_html_report=html,
        ),
        config=OutputConfig(output),
    )
    handler.stop_watcher_factory = lambda event: FrontendStopWatcher(
        event, poll_interval=60
    )
    delivered = await asyncio.wait_for(collect(handler, event), timeout=1)
    assert len(delivered) == 1
    assert not adapter.sent
    assert captured["trace"].status == "aborted"


@pytest.mark.asyncio
async def test_normal_text_delivery_still_succeeds(monkeypatch):
    captured = _spy_trace(monkeypatch)
    adapter = DeliveryAdapter()
    handler = make_handler(
        ReportResultService(adapter),
        StubTaskManager(),
        report_generator=SimpleNamespace(generate_text_report=lambda _: "正文"),
        config=OutputConfig("text"),
    )
    await collect(handler, HostEvent())
    assert adapter.sent == ["text"]
    assert captured["trace"].status == "succeeded"


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["text", "image"])
@pytest.mark.parametrize("platform", ["telegram", "qq_official", "qq_official_webhook"])
@pytest.mark.parametrize("with_stop", [True, False])
async def test_text_and_image_fallback_share_delivery(
    output, platform, with_stop, monkeypatch
):
    """文字与图片回退都直接发送报告，不绕回插件入口。"""
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    adapter = DeliveryAdapter(platform)
    adapter.platform_id = "bot-a"
    adapter.send_text_report = AsyncMock()
    generator = SimpleNamespace(
        generate_image_report=AsyncMock(return_value=(None, None)),
        generate_markdown_report=AsyncMock(return_value=("Markdown 正文", "回退正文")),
        generate_text_report=Mock(return_value="普通正文"),
    )
    handler = make_handler(
        object(),
        StubTaskManager(),
        report_generator=generator,
        config=OutputConfig(output),
    )
    host_text = AsyncMock(side_effect=AssertionError("不应回调插件私有文字发送方法"))
    handler.plugin_instance = SimpleNamespace(
        comic_command_handler=None,
        _send_text_reports=host_text,
    )
    result = {
        "group_id": "123456",
        "platform_id": "bot-a",
        "analysis_result": {},
        "adapter": adapter,
    }
    delivered = [
        item
        async for item in handler.send_analysis_report(
            HostEvent(),
            result,
            StopRequest() if with_stop else None,
        )
    ]
    assert not delivered
    host_text.assert_not_called()
    if output == "image":
        generator.generate_image_report.assert_awaited_once()
    else:
        generator.generate_image_report.assert_not_called()
    if platform == "telegram":
        generator.generate_markdown_report.assert_not_called()
        generator.generate_text_report.assert_called_once_with({})
        adapter.send_text_report.assert_awaited_once_with("123456", "普通正文")
    else:
        generator.generate_text_report.assert_not_called()
        generator.generate_markdown_report.assert_awaited_once()
        assert (
            generator.generate_markdown_report.await_args.kwargs["mention_style"]
            == "qq"
        )
        adapter.send_text_report.assert_awaited_once_with(
            "123456",
            "Markdown 正文",
            fallback_content="回退正文",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_requested", [True, False])
@pytest.mark.parametrize("upload_owner", ["handler", "host"])
async def test_image_send_stop_skips_copy_upload(
    stop_requested, upload_owner, monkeypatch
):
    """图片发送中停止时跳过副本上传，无停止时保留两种上传入口。"""
    captured = _spy_trace(monkeypatch)
    adapter = SlowSendingAdapter()
    manager = StubTaskManager()
    handler = make_handler(
        ReportResultService(adapter),
        manager,
        report_generator=FastRenderGenerator(),
        config=CaptionConfig(),
    )
    handler.stop_watcher_factory = lambda event: FrontendStopWatcher(
        event, poll_interval=60
    )
    monkeypatch.setattr(
        handler, "_save_report_to_history", lambda *_args, **_kwargs: None
    )
    upload = AsyncMock()
    if upload_owner == "host":
        handler.plugin_instance = SimpleNamespace(
            comic_command_handler=None,
            _try_upload_image=upload,
        )
    else:
        monkeypatch.setattr(handler, "_try_upload_image", upload)

    event = HostEvent()
    parent = asyncio.create_task(collect(handler, event))
    try:
        await asyncio.wait_for(adapter.started.wait(), timeout=1)
        if stop_requested:
            event.set_extra("agent_stop_requested", True)
        adapter.release.set()
        delivered = await asyncio.wait_for(parent, timeout=1)
        assert adapter.completed
        assert len(delivered) == 1
        assert not manager.active
        assert len(manager.finished) == 1
        if stop_requested:
            upload.assert_not_awaited()
            assert captured["trace"].status == "aborted"
        else:
            upload.assert_awaited_once_with(
                "123456",
                "http://img.local/report.jpg",
                "aiocqhttp_1",
            )
            assert captured["trace"].status == "succeeded"
    finally:
        adapter.release.set()
        if not parent.done():
            parent.cancel()
        await asyncio.gather(parent, return_exceptions=True)


@pytest.mark.asyncio
async def test_pending_stop_prevents_new_work_from_starting():
    request = StopRequest()
    request.request()
    started = False

    async def work():
        nonlocal started
        started = True

    handler = make_handler(object(), StubTaskManager())
    with pytest.raises(handler_module.AnalysisStoppedError):
        await handler._await_with_stop(work(), request)
    assert not started


@pytest.mark.asyncio
@pytest.mark.parametrize("sent", [True, False])
async def test_html_upload_stop_prevents_followup_caption_or_fallback(
    sent, monkeypatch
):
    captured = _spy_trace(monkeypatch)
    started, release = asyncio.Event(), asyncio.Event()

    async def html(*_args, **_kwargs):
        return "report.html", "report.json"

    async def send_file(*_args, **_kwargs):
        started.set()
        await release.wait()
        return sent

    class HtmlOutputConfig(OutputConfig):
        def get_html_only_url(self):
            return False

        def get_html_base_url(self):
            return ""

    handler = make_handler(
        ReportResultService(DeliveryAdapter()),
        StubTaskManager(),
        report_generator=SimpleNamespace(
            generate_html_report=html,
            build_html_caption=lambda _: "报告说明",
        ),
        config=HtmlOutputConfig("html"),
    )
    handler.message_sender = SimpleNamespace(send_file=send_file)
    event = HostEvent()
    parent = asyncio.create_task(collect(handler, event))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        event.set_extra("agent_stop_requested", True)
        release.set()
        delivered = await asyncio.wait_for(parent, timeout=1)
        assert len(delivered) == 1
        assert captured["trace"].status == "aborted"
    finally:
        release.set()
        if not parent.done():
            parent.cancel()
        await asyncio.gather(parent, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("comic_mode", ["owned", "existing", "ignores_cancel"])
async def test_stop_only_cancels_this_manual_reports_comic(
    comic_mode, monkeypatch, tmp_path
):
    captured = _spy_trace(monkeypatch)
    started, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def generate_comic(*_args):
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            if comic_mode != "ignores_cancel":
                raise
            await release.wait()
        return None, "https://image.example/comic.png"

    adapter = DeliveryAdapter()
    service = ReportResultService(adapter)
    config = OutputConfig()
    comic = ComicCommandHandler(
        config_manager=config,
        bot_manager=SimpleNamespace(get_adapter=lambda _: adapter),
        comic_service=SimpleNamespace(generate_comic=generate_comic),
        analysis_service=service,
        plugin_data_dir=tmp_path,
    )
    topics = {"topics": [{"topic": "测试话题", "detail": "详情"}]}
    if comic_mode == "existing":
        assert (
            comic.try_trigger_comic_generation("123456", "aiocqhttp_1", topics)
            == "started"
        )
        await asyncio.wait_for(started.wait(), timeout=1)

    async def analysis(**_kwargs):
        return {
            "success": True,
            "group_id": "123456",
            "platform_id": "aiocqhttp_1",
            "analysis_result": topics,
            "adapter": adapter,
        }

    service.execute_daily_analysis = analysis
    renderer = SlowRenderGenerator()
    manager = StubTaskManager()
    handler = make_handler(service, manager, report_generator=renderer, config=config)
    handler.comic_handler = comic
    event = HostEvent()
    parent = asyncio.create_task(collect(handler, event))
    try:
        await asyncio.wait_for(
            asyncio.gather(started.wait(), renderer.started.wait()), timeout=1
        )
        comic_task = comic._comic_group_tasks["aiocqhttp_1:123456"]
        event.set_extra("agent_stop_requested", True)
        await asyncio.wait_for(parent, timeout=2)
        assert renderer.cancelled
        assert captured["trace"].status == "aborted"
        assert not manager.active
        if comic_mode == "existing":
            assert not cancelled.is_set()
            assert not comic_task.done()
        else:
            await asyncio.wait_for(cancelled.wait(), timeout=1)
        release.set()
        await asyncio.wait_for(
            asyncio.gather(comic_task, return_exceptions=True), timeout=1
        )
        assert adapter.sent == (
            ["https://image.example/comic.png"] if comic_mode == "existing" else []
        )
    finally:
        release.set()
        if not parent.done():
            parent.cancel()
        for task in list(comic._background_tasks):
            task.cancel()
        await asyncio.gather(
            parent, *list(comic._background_tasks), return_exceptions=True
        )


@pytest.mark.asyncio
async def test_handler_accepts_an_independent_stop_watcher(monkeypatch):
    """应用入口只依赖注入的监听契约，不需要宿主停止标记。"""
    captured = _spy_trace(monkeypatch)

    class Watcher:
        def __init__(self):
            self.stop_request = StopRequest()
            self.started = False
            self.stopped = False

        async def start(self):
            self.started = True

        async def stop(self):
            self.stopped = True

        def stop_now(self):
            self.stopped = True

    watcher = Watcher()
    event = HostEvent()
    service = StubAnalysisService(TaskGuard(1))
    manager = StubTaskManager()
    factory = Mock(return_value=watcher)
    handler = make_handler(service, manager, stop_watcher_factory=factory)

    async def collect():
        return [item async for item in handler.handle_daily_analysis(event)]

    parent = asyncio.create_task(collect())
    try:
        await asyncio.wait_for(service.started.wait(), timeout=1)
        assert watcher.started
        assert event.get_extra("agent_stop_requested") is None
        watcher.stop_request.request()
        delivered = await asyncio.wait_for(parent, timeout=1)
        factory.assert_called_once_with(event)
        assert service.cancelled
        assert watcher.stopped
        assert len(delivered) == 1
        assert not manager.active
        assert len(manager.finished) == 1
        assert captured["trace"].status == "aborted"
    finally:
        if not parent.done():
            parent.cancel()
        await asyncio.gather(parent, return_exceptions=True)
