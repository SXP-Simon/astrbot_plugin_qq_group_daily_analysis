"""词云发送与日报隔离、重试及会话隔离回归。"""

import asyncio
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.services.merged_forward_delivery import (
    MergedForwardDeliveryService,
)
from src.application.services.wordcloud_delivery_service import WordCloudDeliveryService
from src.domain.value_objects.wordcloud import (
    WordCloudData,
    WordCloudOptions,
    WordFrequency,
)
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.persistence.wordcloud_store import WordCloudStore
from src.infrastructure.reporting.dispatcher import ReportDispatcher


def config(values=None):
    manager = object.__new__(ConfigManager)
    manager.config = values or {}
    return manager


def test_config_global_group_and_defaults():
    manager = config(
        {
            "wordcloud": {
                "word_spacing": 9,
                "group_overrides": {
                    "a:GroupMessage:1": {"word_spacing": 3, "font": "serif"}
                },
            }
        }
    )
    assert manager.get_wordcloud_options().word_spacing == 9
    assert manager.get_wordcloud_options().max_words == 80
    assert manager.get_wordcloud_options("a:GroupMessage:1").word_spacing == 3
    assert manager.get_wordcloud_options("b:GroupMessage:1").word_spacing == 9
    assert manager.get_wordcloud_options("a:GroupMessage:1").font == "serif"


@pytest.mark.asyncio
async def test_failed_wordcloud_can_retry_without_report_or_refetch(tmp_path):
    renderer = SimpleNamespace(
        render=AsyncMock(side_effect=[RuntimeError("字体不可用"), b"image"])
    )
    sender = SimpleNamespace(send_image_smart=AsyncMock(return_value=True))
    store = WordCloudStore(tmp_path / "wordcloud.db")
    delivery = WordCloudDeliveryService(config(), renderer, store, sender)
    data = WordCloudData(
        (WordFrequency("高性能", 10, 5),), message_count=5, group_id="1"
    )
    assert not await delivery.send(data, "1", "a")
    cached = store.latest("a:GroupMessage:1")
    assert cached == data
    assert store.latest("b:GroupMessage:1") is None
    assert await delivery.send(cached, "1", "a", force=True)
    assert sender.send_image_smart.await_count == 1
    assert renderer.render.call_args.kwargs["umo"] == "a:GroupMessage:1"
    assert await delivery.send(data, "1", "a")
    assert sender.send_image_smart.await_count == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_snapshot_sent_once(tmp_path):
    import asyncio

    renderer = SimpleNamespace(render=AsyncMock(return_value=b"image"))
    sender = SimpleNamespace(send_image_smart=AsyncMock(return_value=True))
    service = WordCloudDeliveryService(
        config(), renderer, WordCloudStore(tmp_path / "w.db"), sender
    )
    data = WordCloudData((WordFrequency("高性能", 10, 5),), message_count=5)
    assert all(
        await asyncio.gather(service.send(data, "1", "p"), service.send(data, "1", "p"))
    )
    assert sender.send_image_smart.await_count == 1


@pytest.mark.asyncio
async def test_report_success_survives_wordcloud_failure_and_order():
    calls = []

    async def report(*_args):
        calls.append("report")
        return True

    async def cloud(*_args):
        calls.append("wordcloud")
        return False

    manager = SimpleNamespace(get_output_format=lambda: ["text"])
    sender = SimpleNamespace(bot_manager=SimpleNamespace(get_adapter=lambda _pid: None))
    dispatcher = ReportDispatcher(manager, None, sender)
    dispatcher._dispatch_text = report
    dispatcher.wordcloud_delivery = SimpleNamespace(send_with_report=cloud)
    assert await dispatcher.dispatch("1", {}, "p")
    assert calls == ["report", "wordcloud"]


@pytest.mark.asyncio
async def test_failed_report_does_not_send_wordcloud():
    dispatcher = ReportDispatcher(
        SimpleNamespace(get_output_format=lambda: ["text"]), None, None
    )
    dispatcher._dispatch_text = AsyncMock(return_value=False)
    dispatcher.wordcloud_delivery = SimpleNamespace(send_with_report=AsyncMock())
    assert not await dispatcher.dispatch("1", {}, "p")
    dispatcher.wordcloud_delivery.send_with_report.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_uses_current_appearance(tmp_path):
    manager = config({"wordcloud": {"word_spacing": 4}})
    renderer = SimpleNamespace(render=AsyncMock(return_value=b"image"))
    sender = SimpleNamespace(send_image_smart=AsyncMock(return_value=True))
    service = WordCloudDeliveryService(
        manager, renderer, WordCloudStore(tmp_path / "w.db"), sender
    )
    data = WordCloudData((WordFrequency("高性能", 10, 5),))
    await service.send(data, "1", "p")
    manager.config["wordcloud"]["word_spacing"] = 20
    await service.send(service.store.latest("p:GroupMessage:1"), "1", "p", force=True)
    assert renderer.render.call_args.kwargs["options"].word_spacing == 20
    assert renderer.render.call_args.args[0] == data


@pytest.mark.parametrize(
    "bad",
    [
        {"word_spacing": -1},
        {"word_spacing": 41},
        {"min_font_size": 100, "max_font_size": 40},
        {"font": "https://bad/font"},
    ],
)
def test_invalid_settings_rejected(bad):
    with pytest.raises(ValueError):
        WordCloudOptions.from_mapping(bad)


@pytest.fixture
def merged_wordcloud(tmp_path):
    """使用真实词云持久化与合并协调器，仅隔离渲染及平台网络。"""
    manager = config({"basic": {"enable_merged_forward": True}})
    renderer = SimpleNamespace(render=AsyncMock(return_value=b"wordcloud-image"))
    adapter = SimpleNamespace(
        capabilities=SimpleNamespace(supports_forward_message=True),
        bot_self_ids=["10000"],
        platform_id="onebot",
        send_forward_msg=AsyncMock(return_value=True),
    )
    bots = SimpleNamespace(get_adapter=lambda _platform: adapter)
    sender = SimpleNamespace(bot_manager=bots, send_image_smart=AsyncMock())
    store = WordCloudStore(tmp_path / "merged-wordcloud.db")
    delivery = WordCloudDeliveryService(manager, renderer, store, sender)
    coordinator = MergedForwardDeliveryService(manager, bots)
    delivery.merged_delivery = coordinator
    delivery._try_upload_album = AsyncMock()
    data = WordCloudData(
        (WordFrequency("高性能", 10, 5),), message_count=5, group_id="1"
    )
    return SimpleNamespace(
        manager=manager,
        renderer=renderer,
        adapter=adapter,
        sender=sender,
        store=store,
        delivery=delivery,
        coordinator=coordinator,
        data=data,
        umo="onebot:GroupMessage:1",
    )


def latest_delivery_record(store, umo):
    """直接读取持久化状态，避免将调用过保存等同于保存成功。"""
    with sqlite3.connect(store.path) as connection:
        return connection.execute(
            "SELECT status, error, fingerprint FROM wordcloud_delivery "
            "WHERE umo = ? ORDER BY updated_at DESC LIMIT 1",
            (umo,),
        ).fetchone()


@pytest.mark.asyncio
async def test_merged_wordcloud_waits_for_receipt_before_sent_and_album(
    merged_wordcloud,
):
    """真实单项合并在平台确认前保持 pending，确认后才成功落库及上传。"""
    env = merged_wordcloud
    entered, receipt = asyncio.Event(), asyncio.Event()

    async def forward(_group, _nodes):
        entered.set()
        await receipt.wait()
        return True

    env.adapter.send_forward_msg.side_effect = forward
    task = asyncio.create_task(env.delivery.send(env.data, "1", "onebot"))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        record = latest_delivery_record(env.store, env.umo)
        assert record[0] == "pending"
        assert not env.store.is_sent(env.umo, record[2])
        env.delivery._try_upload_album.assert_not_awaited()
        env.sender.send_image_smart.assert_not_awaited()
    finally:
        receipt.set()
        sent = await task

    assert sent
    assert latest_delivery_record(env.store, env.umo)[0] == "sent"
    env.delivery._try_upload_album.assert_awaited_once()
    group, nodes = env.adapter.send_forward_msg.await_args.args
    assert group == "1" and len(nodes) == 1
    content = nodes[0]["data"]["content"]
    assert len([part for part in content if part["type"] == "image"]) == 1
    assert await env.delivery.send(env.data, "1", "onebot")
    assert env.adapter.send_forward_msg.await_count == 1


@pytest.mark.asyncio
async def test_merged_wordcloud_forward_failure_is_retryable(merged_wordcloud):
    """失败回执持久化为 failed，显式重试仅在成功后上传相册。"""
    env = merged_wordcloud
    env.adapter.send_forward_msg.side_effect = [False, True]

    assert not await env.delivery.send(env.data, "1", "onebot")
    failed = latest_delivery_record(env.store, env.umo)
    assert failed[0] == "failed" and failed[1]
    assert not env.store.is_sent(env.umo, failed[2])
    env.delivery._try_upload_album.assert_not_awaited()
    assert env.store.latest(env.umo) == env.data

    assert await env.delivery.send(env.store.latest(env.umo), "1", "onebot", force=True)
    assert latest_delivery_record(env.store, env.umo)[0] == "sent"
    assert env.adapter.send_forward_msg.await_count == 2
    env.delivery._try_upload_album.assert_awaited_once()
    env.sender.send_image_smart.assert_not_awaited()


@pytest.mark.asyncio
async def test_merged_wordcloud_prepare_timeout_persists_failed(
    merged_wordcloud, monkeypatch
):
    """词云渲染超过收集期限被取消后，缓存可重试且不会误记发送成功。"""
    env = merged_wordcloud
    cancelled = asyncio.Event()

    async def hung_render(*_args, **_kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    env.renderer.render.side_effect = hung_render
    monkeypatch.setattr(env.manager, "get_merged_forward_timeout", lambda: 0.02)
    assert not await asyncio.wait_for(
        env.delivery.send(env.data, "1", "onebot"), timeout=2
    )

    assert cancelled.is_set()
    assert latest_delivery_record(env.store, env.umo)[0] == "failed"
    assert env.store.latest(env.umo) == env.data
    env.adapter.send_forward_msg.assert_not_awaited()
    env.delivery._try_upload_album.assert_not_awaited()


@pytest.mark.asyncio
async def test_merged_wordcloud_parent_cancellation_while_rendering_marks_failed(
    merged_wordcloud,
):
    """父任务取消会传播给渲染，并释放独立发送锁以允许重试。"""
    env = merged_wordcloud
    entered = asyncio.Event()

    async def hung_render(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    env.renderer.render.side_effect = hung_render
    task = asyncio.create_task(env.delivery.send(env.data, "1", "onebot"))
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert latest_delivery_record(env.store, env.umo)[0] == "failed"
    env.adapter.send_forward_msg.assert_not_awaited()
    env.delivery._try_upload_album.assert_not_awaited()
    env.renderer.render.side_effect = None
    assert await asyncio.wait_for(
        env.delivery.send(env.data, "1", "onebot", force=True), timeout=1
    )


@pytest.mark.asyncio
async def test_merged_wordcloud_parent_cancellation_after_prepare_marks_failed(
    merged_wordcloud, monkeypatch
):
    """词云准备完成、平台图片转换途中取消，也必须终结 pending 状态。"""
    env = merged_wordcloud
    entered = asyncio.Event()

    async def converting_image(_source):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(env.coordinator, "_image_source", converting_image)
    task = asyncio.create_task(env.delivery.send(env.data, "1", "onebot"))
    await asyncio.wait_for(entered.wait(), timeout=1)
    assert latest_delivery_record(env.store, env.umo)[0] == "pending"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert latest_delivery_record(env.store, env.umo)[0] == "failed"
    env.adapter.send_forward_msg.assert_not_awaited()
    env.delivery._try_upload_album.assert_not_awaited()


@pytest.mark.asyncio
async def test_merged_wordcloud_can_send_when_report_producer_fails(merged_wordcloud):
    """日报准备异常不阻断真实附送词云，dispatch 仍准确返回报告未成功。"""
    env = merged_wordcloud
    dispatcher = ReportDispatcher(env.manager, None, env.sender)
    dispatcher.merged_delivery = env.coordinator
    dispatcher.wordcloud_delivery = env.delivery
    dispatcher.prepare_report = AsyncMock(side_effect=RuntimeError("日报不可用"))

    assert not await dispatcher.dispatch("1", {"wordcloud": env.data}, "onebot")

    dispatcher.prepare_report.assert_awaited()
    assert latest_delivery_record(env.store, env.umo)[0] == "sent"
    assert env.adapter.send_forward_msg.await_count == 1
    nodes = env.adapter.send_forward_msg.await_args.args[1]
    assert len(nodes) == 1
    assert nodes[0]["data"]["nickname"] == "☁️ 群聊词云"
    env.delivery._try_upload_album.assert_awaited_once()
    env.sender.send_image_smart.assert_not_awaited()


@pytest.mark.asyncio
async def test_merged_wordcloud_callbacks_keep_group_and_platform_isolation(
    merged_wordcloud,
):
    """不同会话的准备结果分别落库，失败回调不能污染已成功的另一群。"""
    env = merged_wordcloud
    other_umo = "other-platform:GroupMessage:2"
    first = await env.delivery.prepare_for_report(env.data, "1", "onebot")
    other = await env.delivery.prepare_for_report(env.data, "2", "other-platform")

    assert latest_delivery_record(env.store, env.umo)[0] == "pending"
    assert latest_delivery_record(env.store, other_umo)[0] == "pending"
    env.adapter.send_forward_msg.assert_not_awaited()
    env.delivery._try_upload_album.assert_not_awaited()
    await asyncio.gather(first[0].after_failure(), other[0].after_send())

    assert latest_delivery_record(env.store, env.umo)[0] == "failed"
    assert latest_delivery_record(env.store, other_umo)[0] == "sent"
    env.delivery._try_upload_album.assert_awaited_once()
    assert env.delivery._try_upload_album.await_args.args[0] == "2"
    assert env.delivery._try_upload_album.await_args.args[2] == "other-platform"


@pytest.mark.asyncio
async def test_merged_duplicate_prepare_reserved_until_receipt_then_failure_can_retry(
    merged_wordcloud,
):
    """同快照从渲染中到已准备未回执都只预约一份，失败释放后可重试。"""
    env = merged_wordcloud
    entered, release = asyncio.Event(), asyncio.Event()

    async def rendering(*_args, **_kwargs):
        entered.set()
        await release.wait()
        return b"image"

    env.renderer.render.side_effect = rendering
    first_task = asyncio.create_task(
        env.delivery.prepare_for_report(env.data, "1", "onebot")
    )
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert (
            await asyncio.wait_for(
                env.delivery.prepare_for_report(env.data, "1", "onebot"), timeout=1
            )
            == []
        )
    finally:
        release.set()
        prepared = await first_task

    assert len(prepared) == 1
    assert env.renderer.render.await_count == 1
    assert await env.delivery.prepare_for_report(env.data, "1", "onebot") == []
    await prepared[0].after_failure()
    assert latest_delivery_record(env.store, env.umo)[0] == "failed"

    retried = await env.delivery.prepare_for_report(env.data, "1", "onebot")
    assert len(retried) == 1 and env.renderer.render.await_count == 2
    await retried[0].after_send()
    assert latest_delivery_record(env.store, env.umo)[0] == "sent"
    assert await env.delivery.prepare_for_report(env.data, "1", "onebot") == []
    assert env.renderer.render.await_count == 2


@pytest.mark.asyncio
async def test_merged_prepare_cancellation_releases_same_snapshot_reservation(
    merged_wordcloud,
):
    """取消渲染清理预约，同一词频无需变更即可再次准备。"""
    env = merged_wordcloud
    entered = asyncio.Event()

    async def rendering(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    env.renderer.render.side_effect = rendering
    task = asyncio.create_task(env.delivery.prepare_for_report(env.data, "1", "onebot"))
    await asyncio.wait_for(entered.wait(), timeout=1)
    assert (
        await asyncio.wait_for(
            env.delivery.prepare_for_report(env.data, "1", "onebot"), timeout=1
        )
        == []
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert latest_delivery_record(env.store, env.umo)[0] == "failed"
    env.renderer.render.side_effect = None
    prepared = await env.delivery.prepare_for_report(env.data, "1", "onebot")
    assert len(prepared) == 1
    await prepared[0].after_failure()


@pytest.mark.asyncio
async def test_merged_preparing_distinct_sessions_does_not_share_reservations(
    merged_wordcloud,
):
    """相同词频在不同会话中可同时渲染，不被另一群的预约阻断。"""
    env = merged_wordcloud
    started = set()
    both_started, release = asyncio.Event(), asyncio.Event()

    async def rendering(*_args, **kwargs):
        started.add(kwargs["umo"])
        if len(started) == 2:
            both_started.set()
        await release.wait()
        return b"image"

    env.renderer.render.side_effect = rendering
    first = asyncio.create_task(
        env.delivery.prepare_for_report(env.data, "1", "onebot")
    )
    second = asyncio.create_task(
        env.delivery.prepare_for_report(env.data, "1", "other-platform")
    )
    try:
        await asyncio.wait_for(both_started.wait(), timeout=1)
    finally:
        release.set()
        first_prepared, second_prepared = await asyncio.gather(first, second)

    assert len(first_prepared) == len(second_prepared) == 1
    await asyncio.gather(
        first_prepared[0].after_failure(), second_prepared[0].after_send()
    )
    assert latest_delivery_record(env.store, env.umo)[0] == "failed"
    assert (
        latest_delivery_record(env.store, "other-platform:GroupMessage:1")[0] == "sent"
    )
