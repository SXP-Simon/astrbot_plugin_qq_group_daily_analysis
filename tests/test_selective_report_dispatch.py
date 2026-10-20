"""按产物类型选择合并转发时的路由、并行发送与故障隔离。"""

import asyncio
from itertools import combinations
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from test_merged_report_dispatch import make_dispatcher

from src.application.services.merged_forward_delivery import PreparedForwardMessage
from src.shared import trace_context
from src.shared.trace_context import TraceContext


@pytest.fixture(autouse=True)
def isolated_trace(monkeypatch):
    """只验证发送路由，隔离其他测试留下的追踪仓储。"""
    monkeypatch.setattr(TraceContext, "current", lambda: None)
    monkeypatch.setattr(trace_context, "_global_trace_store", None)


def make_selective_dispatcher(tmp_path, selected, *, formats=("text",)):
    """保留真实合并收集器，只替换普通发送和附属产物生成边界。"""
    dispatcher, adapter, sender, generator = make_dispatcher(
        tmp_path, formats, enabled=list(selected)
    )
    dispatcher._dispatch_text = AsyncMock(return_value=True)
    dispatcher.wordcloud_delivery = SimpleNamespace(
        prepare_for_report=AsyncMock(
            return_value=[PreparedForwardMessage("wordcloud", text="词云结果")]
        ),
        send_with_report=AsyncMock(return_value=True),
    )
    dispatcher.comic_handler = SimpleNamespace(
        prepare_for_report=AsyncMock(
            return_value=[PreparedForwardMessage("comic", text="漫画结果")]
        ),
        try_trigger_comic_generation=Mock(return_value="started"),
    )
    return dispatcher, adapter, sender, generator


SELECTIONS = [
    selected
    for count in range(4)
    for selected in combinations(("report", "wordcloud", "comic"), count)
]


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", SELECTIONS)
async def test_all_eight_selections_route_each_result_exactly_once(tmp_path, selected):
    dispatcher, adapter, _, generator = make_selective_dispatcher(tmp_path, selected)

    assert await dispatcher.dispatch("123", {}, "bot")

    assert dispatcher._dispatch_text.await_count == ("report" not in selected)
    assert generator.generate_text_report.call_count == ("report" in selected)
    cloud = dispatcher.wordcloud_delivery
    assert cloud.prepare_for_report.await_count == ("wordcloud" in selected)
    assert cloud.send_with_report.await_count == ("wordcloud" not in selected)
    comic = dispatcher.comic_handler
    assert comic.prepare_for_report.await_count == ("comic" in selected)
    # 空选择继续由原有上层入口启动普通漫画，不能在分发器再启动一次。
    assert comic.try_trigger_comic_generation.call_count == bool(
        selected and "comic" not in selected
    )
    assert adapter.send_forward_msg.await_count == bool(selected)
    if selected:
        nodes = adapter.send_forward_msg.call_args.args[1]
        assert len(nodes) == len(selected)
        titles = {node["data"]["nickname"] for node in nodes}
        assert ("📊 群聊分析报告" in titles) == ("report" in selected)
        assert ("☁️ 群聊词云" in titles) == ("wordcloud" in selected)
        assert ("🎬 每日群漫画" in titles) == ("comic" in selected)


@pytest.mark.asyncio
async def test_ordinary_html_retains_file_delivery_when_only_comic_is_selected(
    tmp_path,
):
    dispatcher, adapter, sender, generator = make_selective_dispatcher(
        tmp_path, ["comic"], formats=("html",)
    )
    html_file = tmp_path / "报告.html"
    html_file.write_text("<html>报告正文</html>", encoding="utf-8")
    generator.build_html_caption = Mock(return_value="报告文件")

    assert await dispatcher.dispatch("123", {}, "bot")

    generator.generate_html_report.assert_awaited_once()
    sender.send_file.assert_awaited_once_with(
        "123", str(html_file), caption="报告文件", platform_id="bot"
    )
    generator.generate_text_report.assert_not_called()
    nodes = adapter.send_forward_msg.call_args.args[1]
    assert len(nodes) == 1 and nodes[0]["data"]["nickname"] == "🎬 每日群漫画"


@pytest.mark.asyncio
async def test_ordinary_report_cloud_and_comic_start_before_slow_merged_result(
    tmp_path,
):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["comic"])
    selected_started = asyncio.Event()
    release = asyncio.Event()

    async def selected_comic(*_args):
        selected_started.set()
        await release.wait()
        return [PreparedForwardMessage("comic", text="漫画结果")]

    dispatcher.comic_handler.prepare_for_report.side_effect = selected_comic
    task = asyncio.create_task(dispatcher.dispatch("123", {}, "bot"))
    try:
        await asyncio.wait_for(selected_started.wait(), timeout=1)
        dispatcher._dispatch_text.assert_awaited_once()
        dispatcher.wordcloud_delivery.send_with_report.assert_awaited_once()
        adapter.send_forward_msg.assert_not_awaited()
    finally:
        release.set()
        assert await task


@pytest.mark.asyncio
async def test_unselected_comic_starts_background_before_selected_report_ready(
    tmp_path,
):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["report"])
    report_started = asyncio.Event()
    release = asyncio.Event()

    async def selected_report(*_args):
        report_started.set()
        await release.wait()
        return [PreparedForwardMessage("report", text="报告结果")]

    dispatcher.prepare_report = AsyncMock(side_effect=selected_report)
    task = asyncio.create_task(dispatcher.dispatch("123", {}, "bot"))
    try:
        await asyncio.wait_for(report_started.wait(), timeout=1)
        dispatcher.comic_handler.try_trigger_comic_generation.assert_called_once_with(
            "123", "bot", {}
        )
        dispatcher.comic_handler.prepare_for_report.assert_not_awaited()
        dispatcher.wordcloud_delivery.send_with_report.assert_awaited_once()
        adapter.send_forward_msg.assert_not_awaited()
    finally:
        release.set()
        assert await task


@pytest.mark.asyncio
async def test_fast_selected_cloud_sends_before_slow_ordinary_report(tmp_path):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["wordcloud"])
    report_started = asyncio.Event()
    forwarded = asyncio.Event()
    release = asyncio.Event()

    async def ordinary_report(*_args):
        report_started.set()
        await release.wait()
        return True

    async def send_forward(*_args):
        forwarded.set()
        return True

    dispatcher._dispatch_text.side_effect = ordinary_report
    adapter.send_forward_msg.side_effect = send_forward
    task = asyncio.create_task(dispatcher.dispatch("123", {}, "bot"))
    try:
        await asyncio.wait_for(forwarded.wait(), timeout=1)
        assert report_started.is_set()
        assert not task.done()
        dispatcher.wordcloud_delivery.send_with_report.assert_not_awaited()
    finally:
        release.set()
        assert await task


@pytest.mark.asyncio
async def test_selected_report_does_not_wait_for_slow_ordinary_cloud(tmp_path):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["report"])
    forwarded = asyncio.Event()
    release = asyncio.Event()

    async def ordinary_cloud(*_args):
        await release.wait()
        return True

    async def send_forward(*_args):
        forwarded.set()
        return True

    dispatcher.wordcloud_delivery.send_with_report.side_effect = ordinary_cloud
    adapter.send_forward_msg.side_effect = send_forward
    task = asyncio.create_task(dispatcher.dispatch("123", {}, "bot"))
    try:
        await asyncio.wait_for(forwarded.wait(), timeout=1)
        assert not task.done()
    finally:
        release.set()
        assert await task


@pytest.mark.asyncio
async def test_ordinary_report_failure_does_not_block_selected_comic_or_ordinary_cloud(
    tmp_path,
):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["comic"])
    dispatcher._dispatch_text.side_effect = RuntimeError("普通报告失败")

    assert not await dispatcher.dispatch("123", {}, "bot")

    adapter.send_forward_msg.assert_awaited_once()
    dispatcher.wordcloud_delivery.send_with_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_selected_report_failure_does_not_block_ordinary_cloud_or_background_comic(
    tmp_path,
):
    dispatcher, adapter, _, generator = make_selective_dispatcher(tmp_path, ["report"])
    generator.generate_text_report.side_effect = RuntimeError("所选报告失败")

    assert not await dispatcher.dispatch("123", {}, "bot")

    adapter.send_forward_msg.assert_not_awaited()
    dispatcher.wordcloud_delivery.send_with_report.assert_awaited_once()
    dispatcher.comic_handler.try_trigger_comic_generation.assert_called_once()


@pytest.mark.asyncio
async def test_ordinary_cloud_and_comic_failure_do_not_change_report_success(tmp_path):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["report"])
    dispatcher.wordcloud_delivery.send_with_report.side_effect = RuntimeError(
        "词云失败"
    )
    dispatcher.comic_handler.try_trigger_comic_generation.side_effect = RuntimeError(
        "漫画启动失败"
    )

    assert await dispatcher.dispatch("123", {}, "bot")

    adapter.send_forward_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_merged_send_failure_keeps_successful_ordinary_report_status(tmp_path):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["wordcloud"])
    adapter.send_forward_msg.return_value = False

    assert await dispatcher.dispatch("123", {}, "bot")

    dispatcher._dispatch_text.assert_awaited_once()
    dispatcher.wordcloud_delivery.prepare_for_report.assert_awaited_once()
    dispatcher.wordcloud_delivery.send_with_report.assert_not_awaited()


@pytest.mark.asyncio
async def test_unexpected_merged_exception_does_not_hide_successful_ordinary_report(
    tmp_path,
):
    dispatcher, _, _, _ = make_selective_dispatcher(tmp_path, ["wordcloud"])
    dispatcher.merged_delivery.deliver = AsyncMock(side_effect=RuntimeError("收集失败"))

    assert await dispatcher.dispatch("123", {}, "bot")

    dispatcher._dispatch_text.assert_awaited_once()
    dispatcher.wordcloud_delivery.send_with_report.assert_not_awaited()


@pytest.mark.asyncio
async def test_slow_ordinary_cloud_has_independent_bound_and_cannot_block_merge(
    tmp_path, monkeypatch
):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["report"])
    cancelled = asyncio.Event()

    async def ordinary_cloud(*_args):
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    dispatcher.wordcloud_delivery.send_with_report.side_effect = ordinary_cloud
    monkeypatch.setattr(dispatcher, "_ORDINARY_DELIVERY_TIMEOUT_SECONDS", 0.01)

    assert await asyncio.wait_for(dispatcher.dispatch("123", {}, "bot"), timeout=1)

    assert cancelled.is_set()
    adapter.send_forward_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_external_cancel_stops_both_routes_without_retry(tmp_path):
    dispatcher, adapter, _, _ = make_selective_dispatcher(tmp_path, ["wordcloud"])
    report_started = asyncio.Event()
    cloud_started = asyncio.Event()
    report_cancelled = asyncio.Event()
    cloud_cancelled = asyncio.Event()

    async def ordinary_report(*_args):
        report_started.set()
        try:
            await asyncio.Future()
        finally:
            report_cancelled.set()

    async def selected_cloud(*_args):
        cloud_started.set()
        try:
            await asyncio.Future()
        finally:
            cloud_cancelled.set()

    dispatcher._dispatch_text.side_effect = ordinary_report
    dispatcher.wordcloud_delivery.prepare_for_report.side_effect = selected_cloud
    task = asyncio.create_task(dispatcher.dispatch("123", {}, "bot"))
    await asyncio.wait_for(
        asyncio.gather(report_started.wait(), cloud_started.wait()), timeout=1
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert report_cancelled.is_set() and cloud_cancelled.is_set()
    adapter.send_forward_msg.assert_not_awaited()
    dispatcher.wordcloud_delivery.prepare_for_report.assert_awaited_once()
    dispatcher.wordcloud_delivery.send_with_report.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["image", "html", "text"])
async def test_cancel_swallowing_ordinary_renderer_cannot_send_late_result(
    tmp_path, monkeypatch, fmt
):
    dispatcher, adapter, sender, generator = make_selective_dispatcher(
        tmp_path, ["wordcloud"], formats=(fmt,)
    )
    cancelled = asyncio.Event()

    async def stubborn_renderer(*_args, **_kwargs):
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            if fmt == "image":
                return "base64://cmVwb3J0", None
            if fmt == "html":
                return str(tmp_path / "报告.html"), None
            return "迟到正文", None

    if fmt == "image":
        generator.generate_image_report.side_effect = stubborn_renderer
    elif fmt == "html":
        generator.generate_html_report.side_effect = stubborn_renderer
    else:
        del dispatcher._dispatch_text
        adapter.get_platform_name = lambda: "telegram"
        generator.generate_markdown_report.side_effect = stubborn_renderer
    monkeypatch.setattr(dispatcher, "_ORDINARY_DELIVERY_TIMEOUT_SECONDS", 0.01)

    assert not await asyncio.wait_for(dispatcher.dispatch("123", {}, "bot"), timeout=1)

    assert cancelled.is_set()
    adapter.send_forward_msg.assert_awaited_once()
    sender.send_image_smart.assert_not_awaited()
    sender.send_file.assert_not_awaited()
    sender.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_entrypoint_format_override_preserves_first_ordinary_format_only(
    tmp_path,
):
    dispatcher, adapter, _, generator = make_selective_dispatcher(
        tmp_path, ["wordcloud"], formats=("image", "text", "html")
    )
    dispatcher._dispatch_image = AsyncMock(return_value=True)
    dispatcher._dispatch_html = AsyncMock(return_value=True)

    assert await dispatcher.dispatch("123", {}, "bot", output_formats=["image"])

    dispatcher._dispatch_image.assert_awaited_once()
    dispatcher._dispatch_text.assert_not_awaited()
    dispatcher._dispatch_html.assert_not_awaited()
    generator.generate_text_report.assert_not_called()
    adapter.send_forward_msg.assert_awaited_once()


@pytest.mark.asyncio
async def test_entrypoint_format_override_also_limits_selected_report_producers(
    tmp_path,
):
    dispatcher, adapter, _, generator = make_selective_dispatcher(
        tmp_path, ["report"], formats=("image", "text", "html")
    )

    assert await dispatcher.dispatch("123", {}, "bot", output_formats=["text"])

    generator.generate_text_report.assert_called_once()
    generator.generate_image_report.assert_not_awaited()
    generator.generate_html_report.assert_not_awaited()
    assert len(adapter.send_forward_msg.call_args.args[1]) == 1
