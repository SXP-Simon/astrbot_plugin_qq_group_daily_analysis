"""合并产物超时、失败隔离、单项发送与投递回调契约。"""

import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.services.merged_forward_delivery import (
    MergedForwardDeliveryService,
    PreparedForwardMessage,
)


def setup_service(*, timeout=0.03, success=True, enabled=True, supported=True):
    """创建只记录合并调用的适配器，普通发送必须保持未调用。"""
    adapter = SimpleNamespace(
        capabilities=SimpleNamespace(supports_forward_message=supported),
        bot_self_ids=["123456"],
        send_forward_msg=AsyncMock(return_value=success),
        send_image=AsyncMock(),
        send_text=AsyncMock(),
    )
    config = SimpleNamespace(
        get_enable_merged_forward=lambda: enabled,
        get_merged_forward_timeout=lambda: timeout,
    )
    return MergedForwardDeliveryService(
        config, SimpleNamespace(get_adapter=lambda _: adapter)
    ), adapter


@pytest.mark.asyncio
async def test_one_report_is_still_one_forward_node():
    """单独开启报告时依然合并，不回退普通图片。"""
    service, adapter = setup_service()
    sent = AsyncMock()
    producer = AsyncMock(
        return_value=[PreparedForwardMessage("report", "日报", "base64://YWJj", sent)]
    )
    assert await service.deliver("1", "p", {"report": producer}) == {"report"}
    nodes = adapter.send_forward_msg.call_args.args[1]
    assert len(nodes) == 1
    assert nodes[0]["data"]["user_id"] == "123456"
    assert nodes[0]["data"]["content"][1]["data"]["file"] == "base64://YWJj"
    sent.assert_awaited_once()
    adapter.send_image.assert_not_awaited()
    adapter.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_three_producers_start_together_and_deliver_once():
    """三类任务并行，节点顺序固定为报告、词云、漫画。"""
    service, adapter = setup_service(timeout=1)
    started = set()
    ready = asyncio.Event()

    def build(kind):
        async def prepare():
            started.add(kind)
            if len(started) == 3:
                ready.set()
            await ready.wait()
            return [PreparedForwardMessage(kind, kind)]

        return prepare

    assert await service.deliver(
        "1", "p", {kind: build(kind) for kind in ("report", "wordcloud", "comic")}
    ) == {"report", "wordcloud", "comic"}
    assert adapter.send_forward_msg.await_count == 1
    assert [
        n["data"]["content"][0]["data"]["text"]
        for n in adapter.send_forward_msg.call_args.args[1]
    ] == ["report", "wordcloud", "comic"]


@pytest.mark.asyncio
async def test_failed_report_and_hung_comic_do_not_block_ready_wordcloud():
    """报告异常与漫画超时同时发生，仍发送已经就绪的词云。"""
    service, adapter = setup_service()
    cancelled = asyncio.Event()

    async def hung():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    result = await service.deliver(
        "1",
        "p",
        {
            "report:image": AsyncMock(side_effect=RuntimeError("失败")),
            "wordcloud": AsyncMock(
                return_value=[PreparedForwardMessage("wordcloud", "词云")]
            ),
            "comic": hung,
        },
    )
    assert result == {"wordcloud"}
    assert cancelled.is_set()
    assert adapter.send_forward_msg.await_count == 1


@pytest.mark.asyncio
async def test_independent_report_formats_keep_completed_text_when_image_times_out():
    """同属报告的一个格式卡住，不丢掉其他格式。"""
    service, adapter = setup_service()
    assert await service.deliver(
        "1",
        "p",
        {
            "report:image": asyncio.Event().wait,
            "report:text": AsyncMock(
                return_value=[PreparedForwardMessage("report", "有效文本")]
            ),
        },
    ) == {"report"}
    assert len(adapter.send_forward_msg.call_args.args[1]) == 1


@pytest.mark.asyncio
async def test_invalid_local_image_only_excludes_that_artifact(tmp_path):
    """坏图片不会破坏整条合并消息，也不会错误执行成功归档。"""
    service, adapter = setup_service()
    good_sent, bad_sent, bad_failed = AsyncMock(), AsyncMock(), AsyncMock()
    assert await service.deliver(
        "1",
        "p",
        {
            "report": AsyncMock(
                return_value=[
                    PreparedForwardMessage("report", "日报", after_send=good_sent)
                ]
            ),
            "comic": AsyncMock(
                return_value=[
                    PreparedForwardMessage(
                        "comic",
                        "漫画",
                        str(tmp_path / "missing.png"),
                        bad_sent,
                        bad_failed,
                    )
                ]
            ),
        },
    ) == {"report"}
    assert len(adapter.send_forward_msg.call_args.args[1]) == 1
    good_sent.assert_awaited_once()
    bad_failed.assert_awaited_once()
    bad_sent.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_images_are_encoded_for_remote_onebot(tmp_path):
    """转发节点不要求 OneBot 协议端能够访问 AstrBot 文件路径。"""
    service, adapter = setup_service()
    image = tmp_path / "preview.png"
    image.write_bytes(b"local-image")
    await service.deliver(
        "1",
        "p",
        {
            "comic": AsyncMock(
                return_value=[PreparedForwardMessage("comic", image_url=str(image))]
            )
        },
    )
    assert (
        adapter.send_forward_msg.call_args.args[1][0]["data"]["content"][0]["data"][
            "file"
        ]
        == "base64://" + base64.b64encode(b"local-image").decode()
    )


@pytest.mark.asyncio
async def test_forward_failure_marks_failed_and_never_splits_messages():
    """平台失败时不盲目普通补发，防止超时后重复刷屏。"""
    service, adapter = setup_service(success=False)
    after_sent, after_failed = AsyncMock(), AsyncMock()
    assert (
        await service.deliver(
            "1",
            "p",
            {
                "wordcloud": AsyncMock(
                    return_value=[
                        PreparedForwardMessage(
                            "wordcloud",
                            "词云",
                            after_send=after_sent,
                            after_failure=after_failed,
                        )
                    ]
                )
            },
        )
        == set()
    )
    after_failed.assert_awaited_once()
    after_sent.assert_not_awaited()
    adapter.send_image.assert_not_awaited()
    adapter.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_one_archive_failure_does_not_hide_success_or_skip_other_archives():
    """相册归档异常不改变已发送状态，也不阻断其他后处理。"""
    service, adapter = setup_service()
    cloud = AsyncMock()
    messages = [
        PreparedForwardMessage(
            "report", "报告", after_send=AsyncMock(side_effect=RuntimeError("相册失败"))
        ),
        PreparedForwardMessage("wordcloud", "词云", after_send=cloud),
    ]
    assert await service.deliver(
        "1", "p", {"results": AsyncMock(return_value=messages)}
    ) == {"report", "wordcloud"}
    cloud.assert_awaited_once()
    assert adapter.send_forward_msg.await_count == 1


@pytest.mark.asyncio
async def test_parent_cancel_cancels_producers_and_does_not_send():
    """插件卸载取消会传播给准备任务，不产生迟到转发。"""
    service, adapter = setup_service(timeout=1)
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def prepare():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    task = asyncio.create_task(service.deliver("1", "p", {"comic": prepare}))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
    adapter.send_forward_msg.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_at", ["report", "wordcloud"])
async def test_cancel_during_image_preparation_finishes_all_collected_nodes(cancel_at):
    """取消时也收尾正在转换及尚未转换的词云，不遗留 pending。"""
    service, adapter = setup_service(timeout=1)
    converting = asyncio.Event()
    failed_report, failed_cloud = AsyncMock(), AsyncMock()

    async def image_source(source):
        if source == cancel_at:
            converting.set()
            await asyncio.Event().wait()
        return "base64://YWJj"

    service._image_source = image_source
    task = asyncio.create_task(
        service.deliver(
            "1",
            "p",
            {
                "results": AsyncMock(
                    return_value=[
                        PreparedForwardMessage(
                            "report", image_url="report", after_failure=failed_report
                        ),
                        PreparedForwardMessage(
                            "wordcloud",
                            image_url="wordcloud",
                            after_failure=failed_cloud,
                        ),
                    ]
                )
            },
        )
    )
    await converting.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    failed_report.assert_awaited_once()
    failed_cloud.assert_awaited_once()
    adapter.send_forward_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_does_not_repeat_callback_for_already_rejected_image(tmp_path):
    """前一坏图已标记失败，后续取消时不能再次执行其回调。"""
    service, adapter = setup_service(timeout=1)
    failed, converting = AsyncMock(), asyncio.Event()
    original = service._image_source

    async def image_source(source):
        if source == "wait":
            converting.set()
            await asyncio.Event().wait()
        return await original(source)

    service._image_source = image_source
    task = asyncio.create_task(
        service.deliver(
            "1",
            "p",
            {
                "results": AsyncMock(
                    return_value=[
                        PreparedForwardMessage(
                            "wordcloud",
                            image_url=str(tmp_path / "missing.png"),
                            after_failure=failed,
                        ),
                        PreparedForwardMessage("comic", image_url="wait"),
                    ]
                )
            },
        )
    )
    await converting.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    failed.assert_awaited_once()
    adapter.send_forward_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_late_producer_result_is_failed_and_never_sent():
    """上游吞掉取消后返回的产物只落失败，不产生迟到发送。"""
    service, adapter = setup_service()
    failed = AsyncMock()

    async def late():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return [PreparedForwardMessage("wordcloud", "迟到", after_failure=failed)]

    assert not await service.deliver("1", "p", {"wordcloud": late})
    await asyncio.sleep(0)
    failed.assert_awaited_once()
    adapter.send_forward_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_platform_send_timeout_finishes_failed_without_splitting(monkeypatch):
    """平台无响应时到达发送上限，失败回调执行且不重复补发。"""
    service, adapter = setup_service()
    after_failed = AsyncMock()
    original_timeout = asyncio.timeout
    limits = []

    def short_timeout(seconds):
        limits.append(seconds)
        return original_timeout(0.01 if seconds == 60 else seconds)

    monkeypatch.setattr(asyncio, "timeout", short_timeout)

    async def send(*_args):
        await asyncio.Event().wait()

    adapter.send_forward_msg.side_effect = send
    assert not await service.deliver(
        "1",
        "p",
        {
            "report": AsyncMock(
                return_value=[
                    PreparedForwardMessage("report", "日报", after_failure=after_failed)
                ]
            )
        },
    )
    assert 60 in limits
    after_failed.assert_awaited_once()
    adapter.send_forward_msg.assert_awaited_once()
    adapter.send_image.assert_not_awaited()
    adapter.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_receipt_wins_when_parent_cancel_arrives_at_same_time():
    """平台已确认成功时即使同时取消，也不能把词云误记为失败。"""
    service, adapter = setup_service()
    after_sent, after_failed = AsyncMock(), AsyncMock()

    async def send(*_args):
        asyncio.current_task().cancel()
        return True

    adapter.send_forward_msg.side_effect = send
    task = asyncio.create_task(
        service.deliver(
            "1",
            "p",
            {
                "wordcloud": AsyncMock(
                    return_value=[
                        PreparedForwardMessage(
                            "wordcloud",
                            "词云",
                            after_send=after_sent,
                            after_failure=after_failed,
                        )
                    ]
                )
            },
        )
    )
    with pytest.raises(asyncio.CancelledError):
        await task
    after_sent.assert_awaited_once()
    after_failed.assert_not_awaited()
    adapter.send_forward_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_parent_cancel_while_waiting_for_cancel_resistant_producer():
    """限时取消的等待窗口遭父取消时，已完成词云也会收尾。"""
    service, adapter = setup_service()
    cancelling, release = asyncio.Event(), asyncio.Event()
    failed = AsyncMock()

    async def stubborn():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelling.set()
            await release.wait()
            return []

    task = asyncio.create_task(
        service.deliver(
            "1",
            "p",
            {
                "wordcloud": AsyncMock(
                    return_value=[
                        PreparedForwardMessage(
                            "wordcloud", "词云", after_failure=failed
                        )
                    ]
                ),
                "comic": stubborn,
            },
        )
    )
    await cancelling.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    await asyncio.sleep(0)
    failed.assert_awaited_once()
    adapter.send_forward_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_all_failed_or_empty_never_sends_empty_forward():
    service, adapter = setup_service()
    assert not await service.deliver(
        "1",
        "p",
        {
            "report": AsyncMock(side_effect=ValueError("失败")),
            "comic": AsyncMock(return_value=[]),
        },
    )
    adapter.send_forward_msg.assert_not_awaited()


@pytest.mark.parametrize(
    ("enabled", "supported", "expected"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_unsupported_platform_preserves_normal_delivery(enabled, supported, expected):
    service, _ = setup_service(enabled=enabled, supported=supported)
    assert service.enabled_for("p") is expected
