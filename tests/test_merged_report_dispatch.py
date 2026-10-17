"""报告、词云与漫画的合并准备、故障隔离和旧发送路径回归。"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.services.merged_forward_delivery import (
    MergedForwardDeliveryService,
    PreparedForwardMessage,
)
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.shared import trace_context
from src.shared.trace_context import TraceContext


@pytest.fixture(autouse=True)
def isolated_trace(monkeypatch):
    """隔离其他测试残留的追踪和持久化仓储。"""
    monkeypatch.setattr(TraceContext, "current", lambda: None)
    monkeypatch.setattr(trace_context, "_global_trace_store", None)


def make_dispatcher(tmp_path, formats=("image",), *, enabled=True):
    """使用真实配置和合并服务，仅替换生成与平台边界。"""
    config = object.__new__(ConfigManager)
    config.config = {
        "basic": {
            "output_format": list(formats),
            "enable_merged_forward": enabled,
            "report_template": "ATRI",
            "show_report_caption": True,
        },
        "html": {"html_output_dir": str(tmp_path)},
    }
    adapter = SimpleNamespace(
        platform_id="bot",
        get_platform_name=lambda: "aiocqhttp",
        bot_self_ids=["42"],
        capabilities=SimpleNamespace(supports_forward_message=True),
        send_forward_msg=AsyncMock(return_value=True),
    )
    bot_manager = SimpleNamespace(get_adapter=Mock(return_value=adapter))
    sender = SimpleNamespace(
        bot_manager=bot_manager,
        send_image_smart=AsyncMock(return_value=True),
        send_file=AsyncMock(return_value=True),
        send_text=AsyncMock(return_value=True),
    )
    generator = SimpleNamespace(
        data_dir=tmp_path,
        generate_image_report=AsyncMock(return_value=("base64://cmVwb3J0", None)),
        generate_html_report=AsyncMock(
            return_value=(str(tmp_path / "报告.html"), None)
        ),
        generate_text_report=Mock(return_value="分析正文"),
        generate_markdown_report=AsyncMock(return_value=("排版正文", None)),
    )
    dispatcher = ReportDispatcher(config, generator, sender)
    dispatcher.set_html_render(AsyncMock())
    dispatcher.merged_delivery = MergedForwardDeliveryService(config, bot_manager)
    return dispatcher, adapter, sender, generator


@pytest.mark.asyncio
async def test_merged_report_wordcloud_comic_sent_once_after_all_ready(tmp_path):
    dispatcher, adapter, sender, _ = make_dispatcher(tmp_path, ("image", "text"))
    archive = AsyncMock()
    dispatcher._try_upload_image = archive
    dispatcher.wordcloud_delivery = SimpleNamespace(
        prepare_for_report=AsyncMock(
            return_value=[
                PreparedForwardMessage("wordcloud", image_url="base64://Y2xvdWQ=")
            ]
        ),
        send_with_report=AsyncMock(),
    )
    dispatcher.comic_handler = SimpleNamespace(
        prepare_for_report=AsyncMock(
            return_value=[
                PreparedForwardMessage("comic", image_url="base64://Y29taWM=")
            ]
        )
    )
    assert await dispatcher.dispatch("123", {}, "bot")
    adapter.send_forward_msg.assert_awaited_once()
    assert len(adapter.send_forward_msg.call_args.args[1]) == 4
    dispatcher.wordcloud_delivery.prepare_for_report.assert_awaited_once_with(
        None, "123", "bot"
    )
    dispatcher.comic_handler.prepare_for_report.assert_awaited_once_with(
        "123", "bot", {}
    )
    archive.assert_awaited_once_with("123", "base64://cmVwb3J0", "bot")
    dispatcher.wordcloud_delivery.send_with_report.assert_not_awaited()
    sender.send_image_smart.assert_not_awaited()
    sender.send_text.assert_not_awaited()
    sender.send_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_image_saves_history_and_defers_upload_until_send(
    tmp_path, monkeypatch
):
    dispatcher, _, sender, _ = make_dispatcher(tmp_path)
    archive = AsyncMock()
    dispatcher._try_upload_image = archive
    trace = TraceContext(trace_id="merged-image", group_id="123")
    trace.metadata["override_template_name"] = "pixel"
    monkeypatch.setattr(TraceContext, "current", lambda: trace)
    nodes = await dispatcher.prepare_report("image", "123", {}, "bot")
    assert len(nodes) == 1
    assert nodes[0].kind == "report"
    assert "每日群聊分析报告已生成" in nodes[0].text
    assert nodes[0].image_url == "base64://cmVwb3J0"
    files = trace.metadata["report_files"]
    assert len(files) == 1
    assert files[0]["format"] == "image"
    assert Path(files[0]["path"]).read_bytes() == b"report"
    dispatcher.report_generator.generate_image_report.assert_awaited_once()
    assert (
        dispatcher.report_generator.generate_image_report.call_args.kwargs[
            "template_theme"
        ]
        == "pixel"
    )
    archive.assert_not_awaited()
    sender.send_image_smart.assert_not_awaited()
    await nodes[0].after_send()
    archive.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("show", [True, False])
async def test_image_caption_switch_preserved(tmp_path, show):
    dispatcher, _, _, _ = make_dispatcher(tmp_path)
    dispatcher.config_manager.config["basic"]["show_report_caption"] = show
    nodes = await dispatcher.prepare_report("image", "123", {}, "bot")
    assert bool(nodes[0].text) is show


@pytest.mark.asyncio
async def test_merged_dispatch_preserves_trace_history_and_result(
    tmp_path, monkeypatch
):
    dispatcher, _, _, _ = make_dispatcher(tmp_path)
    trace = TraceContext(trace_id="merged-dispatch", group_id="123")
    monkeypatch.setattr(TraceContext, "current", lambda: trace)
    assert await dispatcher.dispatch("123", {}, "bot")
    assert trace.metadata["report_files"][0]["format"] == "image"
    spans = [span for span in trace._spans if span["stage_name"] == "DISPATCH_REPORT"]
    assert len(spans) == 1
    assert spans[0]["payload"]["transmission_mode"] == "merged_forward"
    assert spans[0]["payload"]["success"] is True
    assert spans[0]["payload"]["merged_sent_kinds"] == ["report"]


@pytest.mark.asyncio
async def test_image_render_failure_becomes_text_in_same_forward(tmp_path):
    dispatcher, adapter, sender, generator = make_dispatcher(tmp_path)
    generator.generate_image_report.side_effect = RuntimeError("渲染失败")
    assert await dispatcher.dispatch("123", {}, "bot")
    nodes = adapter.send_forward_msg.call_args.args[1]
    assert nodes[0]["data"]["content"] == [
        {"type": "text", "data": {"text": "📊 每日群聊分析报告：\n\n分析正文"}}
    ]
    sender.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_html_url_is_encoded_and_history_preserved(tmp_path, monkeypatch):
    dispatcher, _, sender, generator = make_dispatcher(tmp_path, ("html",))
    html_path = tmp_path / "报告 空格.html"
    html_path.write_text("<html>报告</html>", encoding="utf-8")
    generator.generate_html_report.return_value = (str(html_path), None)
    dispatcher.config_manager.config["html"].update(
        {"html_only_url": True, "html_base_url": "https://example.test/reports/"}
    )
    trace = TraceContext(trace_id="merged-html", group_id="123")
    monkeypatch.setattr(TraceContext, "current", lambda: trace)
    nodes = await dispatcher.prepare_report("html", "123", {}, "bot")
    assert nodes[0].text.endswith(
        "https://example.test/reports/%E6%8A%A5%E5%91%8A%20%E7%A9%BA%E6%A0%BC.html"
    )
    assert trace.metadata["report_files"][0]["path"] == str(html_path.resolve())
    assert trace.metadata["report_files"][0]["format"] == "html"
    sender.send_file.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "only_url,base_url", [(False, ""), (True, ""), (False, "https://example.test")]
)
async def test_html_without_enabled_link_uses_text_and_keeps_file(
    tmp_path, only_url, base_url
):
    dispatcher, adapter, sender, generator = make_dispatcher(tmp_path, ("html",))
    html_path = tmp_path / "报告.html"
    html_path.write_text("<html>历史报告</html>", encoding="utf-8")
    dispatcher.config_manager.config["html"].update(
        {"html_only_url": only_url, "html_base_url": base_url}
    )
    assert await dispatcher.dispatch("123", {}, "bot")
    assert html_path.read_text(encoding="utf-8") == "<html>历史报告</html>"
    assert (
        "分析正文"
        in adapter.send_forward_msg.call_args.args[1][0]["data"]["content"][0]["data"][
            "text"
        ]
    )
    generator.generate_html_report.assert_awaited_once()
    sender.send_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_slow_image_does_not_hide_completed_text_at_deadline(
    tmp_path, monkeypatch
):
    dispatcher, adapter, _, generator = make_dispatcher(tmp_path, ("image", "text"))
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow_image(*_args, **_kwargs):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    generator.generate_image_report.side_effect = slow_image
    monkeypatch.setattr(
        dispatcher.config_manager, "get_merged_forward_timeout", lambda: 0.02
    )
    assert await dispatcher.dispatch("123", {}, "bot")
    assert started.is_set() and cancelled.is_set()
    assert len(adapter.send_forward_msg.call_args.args[1]) == 1
    assert (
        "分析正文"
        in adapter.send_forward_msg.call_args.args[1][0]["data"]["content"][0]["data"][
            "text"
        ]
    )


@pytest.mark.asyncio
async def test_report_failure_does_not_prevent_comic_delivery(tmp_path):
    dispatcher, adapter, _, generator = make_dispatcher(tmp_path, ("text",))
    generator.generate_text_report.side_effect = RuntimeError("报告失败")
    dispatcher.comic_handler = SimpleNamespace(
        prepare_for_report=AsyncMock(
            return_value=[
                PreparedForwardMessage(
                    "comic", text="漫画已完成", image_url="base64://Y29taWM="
                )
            ]
        )
    )
    assert not await dispatcher.dispatch("123", {}, "bot")
    adapter.send_forward_msg.assert_awaited_once()
    assert len(adapter.send_forward_msg.call_args.args[1]) == 1
    assert "漫画" in adapter.send_forward_msg.call_args.args[1][0]["data"]["nickname"]


@pytest.mark.asyncio
async def test_failed_forward_does_not_upload_report(tmp_path):
    dispatcher, adapter, sender, _ = make_dispatcher(tmp_path)
    archive = AsyncMock()
    dispatcher._try_upload_image = archive
    adapter.send_forward_msg.return_value = False
    assert not await dispatcher.dispatch("123", {}, "bot")
    archive.assert_not_awaited()
    sender.send_image_smart.assert_not_awaited()
    sender.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_merge_keeps_serial_formats_then_wordcloud(tmp_path):
    dispatcher, adapter, _, _ = make_dispatcher(
        tmp_path, ("image", "text"), enabled=False
    )
    calls = []

    async def image(*_args):
        calls.append("image")
        await asyncio.sleep(0)
        return True

    async def text(*_args):
        calls.append("text")
        return True

    async def cloud(*_args):
        calls.append("wordcloud")
        return True

    dispatcher._dispatch_image = image
    dispatcher._dispatch_text = text
    dispatcher.wordcloud_delivery = SimpleNamespace(send_with_report=cloud)
    dispatcher.comic_handler = SimpleNamespace(prepare_for_report=AsyncMock())
    assert await dispatcher.dispatch("123", {}, "bot")
    assert calls == ["image", "text", "wordcloud"]
    dispatcher.comic_handler.prepare_for_report.assert_not_awaited()
    adapter.send_forward_msg.assert_not_awaited()
