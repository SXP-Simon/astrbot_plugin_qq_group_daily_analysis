"""漫画合并投递的准备、去重、取消及独立指令回归。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.handlers.comic_command_handler import ComicCommandHandler
from src.domain.value_objects.analysis_results import SummaryTopic
from src.shared.trace_context import TraceContext, _current_trace

TOPICS = [{"topic": "测试话题", "detail": "群友正在讨论绘图模板"}]
JPEG = b"\xff\xd8\xffcomic-preview"


@pytest.fixture
def comic_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """创建隔离漫画资源、平台与生成器，并避免继承其他用例的追踪。"""
    token = _current_trace.set(None)
    config = SimpleNamespace(
        get_t2i_max_concurrent=Mock(return_value=1),
        get_enable_daily_comic=Mock(return_value=True),
        get_enable_auto_daily_comic=Mock(return_value=True),
        is_comic_group_allowed=Mock(return_value=True),
        get_show_report_caption=Mock(return_value=True),
    )
    generator = SimpleNamespace(generate_comic=AsyncMock(return_value=(JPEG, None)))
    adapter = SimpleNamespace(send_image=AsyncMock(return_value=True))
    bots = SimpleNamespace(
        get_adapter=Mock(return_value=adapter), update_from_event=Mock()
    )
    handler = ComicCommandHandler(
        config_manager=config,
        bot_manager=bots,
        comic_service=generator,
        analysis_service=None,
        plugin_data_dir=tmp_path,
    )
    upload = AsyncMock()
    monkeypatch.setattr(handler, "_try_upload_image", upload)
    yield SimpleNamespace(
        handler=handler,
        config=config,
        generator=generator,
        adapter=adapter,
        bots=bots,
        upload=upload,
        directory=tmp_path,
    )
    _current_trace.reset(token)


@pytest.mark.asyncio
async def test_prepare_comic_persists_real_format_and_defers_send_and_album(
    comic_environment,
):
    """准备成功只保存资源；发送器确认投递后才能执行群相册归档。"""
    env = comic_environment
    trace = TraceContext.set(
        trace_id="merged-comic",
        group_id="123",
        platform="onebot",
        trigger_type="manual",
    )

    messages = await env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS})

    assert len(messages) == 1
    message = messages[0]
    assert message.kind == "comic"
    image_path = Path(message.image_url)
    assert image_path.suffix == ".jpg"
    assert image_path.read_bytes() == JPEG
    assert image_path.parent == env.directory / "reports"
    assert "漫画" in message.text
    env.generator.generate_comic.assert_awaited_once_with(
        TOPICS, "123", "onebot:GroupMessage:123"
    )
    env.config.is_comic_group_allowed.assert_called_once_with(
        "onebot:GroupMessage:123", True
    )
    env.adapter.send_image.assert_not_awaited()
    env.upload.assert_not_awaited()
    assert env.handler._comic_group_tasks == {}
    assert env.handler._background_tasks == set()
    assert any(
        item["filename"] == image_path.name and item["stage"] == "COMIC_GENERATION"
        for item in trace.metadata["report_files"]
    )

    assert message.after_send is not None
    await message.after_send()
    env.upload.assert_awaited_once_with("123", str(image_path), "onebot", is_comic=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", ["comic", "auto", "group", "terminating"])
async def test_prepare_comic_honors_switches_and_group_permissions(
    comic_environment, disabled: str
):
    """总开关、自动开关、群名单或关闭状态阻止漫画生成。"""
    env = comic_environment
    if disabled == "comic":
        env.config.get_enable_daily_comic.return_value = False
    elif disabled == "auto":
        env.config.get_enable_auto_daily_comic.return_value = False
    elif disabled == "group":
        env.config.is_comic_group_allowed.return_value = False
    else:
        env.handler.set_terminating(True)

    assert (
        await env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS}) == []
    )

    env.generator.generate_comic.assert_not_awaited()
    env.adapter.send_image.assert_not_awaited()
    assert env.handler._comic_group_tasks == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "analysis", [{}, {"topics": []}, {"topics": [{"topic": "  ", "detail": "无标题"}]}]
)
async def test_prepare_comic_requires_nonempty_topics(comic_environment, analysis):
    """没有有效话题时不会启动绘图或消耗模板轮换。"""
    env = comic_environment

    assert await env.handler.prepare_for_report("123", "onebot", analysis) == []

    env.generator.generate_comic.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_comic_accepts_structured_topics_from_statistics(
    comic_environment,
):
    """增量统计中的话题值对象与直接话题拥有相同准备行为。"""
    env = comic_environment
    topic = SummaryTopic(topic=" 值对象话题 ", contributors=[], detail=" 详细内容 ")

    messages = await env.handler.prepare_for_report(
        "123", "onebot", {"statistics": {"topics": [topic]}}
    )

    assert len(messages) == 1
    env.generator.generate_comic.assert_awaited_once_with(
        [{"topic": "值对象话题", "detail": "详细内容"}],
        "123",
        "onebot:GroupMessage:123",
    )


@pytest.mark.asyncio
async def test_prepare_comic_fallback_url_stays_unsent(comic_environment):
    """API 下载失败的远程地址仍能成为合并节点，不会另行发图。"""
    env = comic_environment
    image_url = "https://images.example.test/comic.jpg"
    env.generator.generate_comic.return_value = (None, image_url)

    messages = await env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS})

    assert len(messages) == 1 and messages[0].image_url == image_url
    assert not (env.directory / "reports").exists()
    env.adapter.send_image.assert_not_awaited()
    env.upload.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("raises", [False, True])
async def test_prepare_comic_failure_releases_task_and_returns_empty(
    comic_environment, raises: bool
):
    """生成失败隔离在漫画项中，并释放同群任务占位。"""
    env = comic_environment
    if raises:
        env.generator.generate_comic.side_effect = RuntimeError("上游绘图失败")
    else:
        env.generator.generate_comic.return_value = (None, None)

    assert (
        await env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS}) == []
    )

    assert env.handler._comic_group_tasks == {}
    assert env.handler._background_tasks == set()
    env.adapter.send_image.assert_not_awaited()
    env.upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_comic_and_background_trigger_share_group_deduplication(
    comic_environment,
):
    """合并等待期间，独立漫画和第二次合并都不能重复启动同群绘图。"""
    env = comic_environment
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_generation(*_args):
        """让首项保持运行，以检查同群去重。"""
        started.set()
        await release.wait()
        return JPEG, None

    env.generator.generate_comic.side_effect = blocked_generation
    first = asyncio.create_task(
        env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS})
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        assert (
            await env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS})
            == []
        )
        assert (
            env.handler.try_trigger_comic_generation(
                "123", "onebot", {"topics": TOPICS}
            )
            == "duplicate"
        )
        assert env.handler._comic_group_tasks["onebot:123"] is first
    finally:
        release.set()
        await first

    env.generator.generate_comic.assert_awaited_once()
    assert env.handler._comic_group_tasks == {}
    assert env.handler._background_tasks == set()


@pytest.mark.asyncio
async def test_prepare_comic_cancellation_propagates_and_releases_semaphore(
    comic_environment,
):
    """总等待超时取消漫画时，不自行发送、不遗留群锁或并发许可。"""
    env = comic_environment
    started = asyncio.Event()

    async def blocked_generation(*_args):
        """模拟仍在等待上游的绘图请求。"""
        started.set()
        await asyncio.Event().wait()

    env.generator.generate_comic.side_effect = blocked_generation
    task = asyncio.create_task(
        env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS})
    )
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert env.handler._comic_group_tasks == {}
    assert env.handler._background_tasks == set()
    env.adapter.send_image.assert_not_awaited()
    env.upload.assert_not_awaited()
    await asyncio.wait_for(env.handler._comic_semaphore.acquire(), timeout=1)
    env.handler._comic_semaphore.release()


@pytest.mark.asyncio
async def test_prepare_comic_cancellation_while_queued_releases_group_reservation(
    comic_environment,
):
    """排队等待并发许可也计入协调等待期限，并能安全取消。"""
    env = comic_environment
    await env.handler._comic_semaphore.acquire()
    task = asyncio.create_task(
        env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS})
    )
    try:
        await asyncio.sleep(0)
        assert env.handler._comic_group_tasks["onebot:123"] is task
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        env.handler._comic_semaphore.release()

    assert env.handler._comic_group_tasks == {}
    assert env.handler._background_tasks == set()
    env.generator.generate_comic.assert_not_awaited()


@pytest.mark.asyncio
async def test_standalone_comic_uses_single_item_merged_delivery(comic_environment):
    """独立漫画启用合并后也交给协调器，且不受自动漫画开关限制。"""
    env = comic_environment
    env.config.get_enable_auto_daily_comic.return_value = False
    prepared = []

    async def deliver(group_id, platform_id, producers):
        """消费实际生产器，但不在测试中向外发送。"""
        assert group_id == "123" and platform_id == "onebot"
        assert list(producers) == ["comic"]
        prepared.extend(await producers["comic"]())
        return {"comic"}

    delivery = SimpleNamespace(
        enabled_for=Mock(return_value=True), deliver=AsyncMock(side_effect=deliver)
    )
    env.handler.merged_delivery = delivery

    status = env.handler.try_trigger_comic_generation(
        "123", "onebot", {"topics": TOPICS}, require_auto_enabled=False
    )
    assert status == "started"
    task = env.handler._comic_group_tasks["onebot:123"]
    await task
    await asyncio.sleep(0)

    assert len(prepared) == 1 and prepared[0].kind == "comic"
    delivery.deliver.assert_awaited_once()
    env.generator.generate_comic.assert_awaited_once()
    env.adapter.send_image.assert_not_awaited()
    env.upload.assert_not_awaited()
    assert env.handler._comic_group_tasks == {}
    assert env.handler._background_tasks == set()


@pytest.mark.asyncio
async def test_disabled_merged_delivery_preserves_standalone_image_and_album(
    comic_environment,
):
    """关闭配置后保持原有单图发送与成功后上传行为。"""
    env = comic_environment
    delivery = SimpleNamespace(
        enabled_for=Mock(return_value=False), deliver=AsyncMock()
    )
    env.handler.merged_delivery = delivery

    await env.handler._trigger_comic_generation(
        TOPICS, "123", "onebot", "onebot:GroupMessage:123"
    )

    env.adapter.send_image.assert_awaited_once()
    path = env.adapter.send_image.await_args.args[1]
    assert Path(path).read_bytes() == JPEG
    env.upload.assert_awaited_once_with("123", path, "onebot", is_comic=True)
    delivery.deliver.assert_not_awaited()


@pytest.mark.asyncio
async def test_standalone_merged_comic_command_keeps_plain_progress(
    comic_environment,
):
    """漫画最终产物合并发送，提取和任务启动提示仍在原指令中普通回复。"""
    env = comic_environment

    async def deliver(_group_id, _platform_id, producers):
        """在合并任务内完成准备，不产生真实平台消息。"""
        assert await producers["comic"]()
        return {"comic"}

    env.handler.merged_delivery = SimpleNamespace(
        enabled_for=Mock(return_value=True), deliver=AsyncMock(side_effect=deliver)
    )
    env.handler.analysis_service = SimpleNamespace(
        execute_comic_topic_analysis=AsyncMock(
            return_value={"success": True, "topics": TOPICS}
        )
    )
    event = SimpleNamespace(
        should_call_llm=Mock(),
        get_group_id=Mock(return_value="123"),
        get_platform_id=Mock(return_value="onebot"),
        unified_msg_origin="onebot:GroupMessage:123",
        plain_result=Mock(side_effect=lambda text: text),
    )

    command = env.handler.handle_group_comic(event)
    first = await anext(command)
    assert first == "🎨 正在提取群聊话题并生成漫画..."
    env.handler.analysis_service.execute_comic_topic_analysis.assert_not_awaited()
    env.handler.merged_delivery.deliver.assert_not_awaited()
    results = [first, *[result async for result in command]]
    pending = list(env.handler._background_tasks)
    if pending:
        await asyncio.gather(*pending)

    assert results == [
        "🎨 正在提取群聊话题并生成漫画...",
        "✅ 漫画生成任务已启动，完成后会发送到群里",
    ]
    assert [call.args[0] for call in event.plain_result.call_args_list] == results
    env.handler.merged_delivery.deliver.assert_awaited_once()
    env.adapter.send_image.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "message"),
    [
        ("no_messages", "❌ 未找到可用于生成漫画的群聊记录"),
        ("no_topics", "❌ 未提取到可用于生成漫画的话题"),
    ],
)
async def test_standalone_merged_comic_failure_keeps_plain_error(
    comic_environment, reason, message
):
    """漫画提取失败仍普通回复错误，不将提示送入最终产物合并协调器。"""
    env = comic_environment
    env.handler.merged_delivery = SimpleNamespace(
        enabled_for=Mock(return_value=True), deliver=AsyncMock()
    )
    env.handler.analysis_service = SimpleNamespace(
        execute_comic_topic_analysis=AsyncMock(
            return_value={"success": False, "reason": reason}
        )
    )
    event = SimpleNamespace(
        should_call_llm=Mock(),
        get_group_id=Mock(return_value="123"),
        get_platform_id=Mock(return_value="onebot"),
        unified_msg_origin="onebot:GroupMessage:123",
        plain_result=Mock(side_effect=lambda text: text),
    )

    results = [result async for result in env.handler.handle_group_comic(event)]

    assert results == ["🎨 正在提取群聊话题并生成漫画...", message]
    assert [call.args[0] for call in event.plain_result.call_args_list] == results
    env.handler.merged_delivery.deliver.assert_not_awaited()
    env.generator.generate_comic.assert_not_awaited()
    env.adapter.send_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_standalone_comic_real_coordinator_sends_one_forward_node(
    comic_environment,
):
    """真实协调器即使只有漫画一种产物，也只调用一次合并转发。"""
    from src.application.services.merged_forward_delivery import (
        MergedForwardDeliveryService,
    )

    env = comic_environment
    env.config.get_enable_merged_forward = Mock(return_value=True)
    env.config.get_merged_forward_timeout = Mock(return_value=5)
    env.adapter.capabilities = SimpleNamespace(supports_forward_message=True)
    env.adapter.bot_self_ids = ["10000"]
    env.adapter.send_forward_msg = AsyncMock(return_value=True)
    env.handler.merged_delivery = MergedForwardDeliveryService(env.config, env.bots)

    assert (
        env.handler.try_trigger_comic_generation(
            "123", "onebot", {"topics": TOPICS}, require_auto_enabled=False
        )
        == "started"
    )
    await env.handler._comic_group_tasks["onebot:123"]

    env.adapter.send_forward_msg.assert_awaited_once()
    group_id, nodes = env.adapter.send_forward_msg.await_args.args
    assert group_id == "123" and len(nodes) == 1
    image_segments = [
        part for part in nodes[0]["data"]["content"] if part["type"] == "image"
    ]
    assert len(image_segments) == 1
    assert image_segments[0]["data"]["file"].startswith("base64://")
    env.adapter.send_image.assert_not_awaited()
    env.upload.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_merged_comics_respect_shared_semaphore(comic_environment):
    """不同群的漫画准备仍复用现有并发上限，不能各自绕过限流。"""
    env = comic_environment
    started = asyncio.Event()

    async def blocked_generation(*_args):
        """占用唯一绘图许可直到被测试取消。"""
        started.set()
        await asyncio.Event().wait()

    env.generator.generate_comic.side_effect = blocked_generation
    first = asyncio.create_task(
        env.handler.prepare_for_report("123", "onebot", {"topics": TOPICS})
    )
    await asyncio.wait_for(started.wait(), timeout=1)
    second = asyncio.create_task(
        env.handler.prepare_for_report("456", "onebot", {"topics": TOPICS})
    )
    try:
        await asyncio.sleep(0)
        env.generator.generate_comic.assert_awaited_once()
        assert set(env.handler._comic_group_tasks) == {"onebot:123", "onebot:456"}
    finally:
        first.cancel()
        second.cancel()
        await asyncio.gather(first, second, return_exceptions=True)

    assert env.handler._comic_group_tasks == {}
    assert env.handler._background_tasks == set()
