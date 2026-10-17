"""日报、漫画与词云发送提示的内容区分、开关和实际链路回归。"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.handlers.comic_command_handler import ComicCommandHandler
from src.application.services.wordcloud_delivery_service import WordCloudDeliveryService
from src.domain.value_objects.wordcloud import WordCloudData, WordFrequency
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.messaging.message_sender import MessageSender
from src.infrastructure.persistence.wordcloud_store import WordCloudStore
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.shared import trace_context
from src.shared.trace_context import TraceContext


@pytest.fixture(autouse=True)
def fixed_caption_time(monkeypatch):
    """固定提示时间，并隔离其他用例残留的追踪上下文。"""
    monkeypatch.setattr(
        trace_context,
        "datetime",
        SimpleNamespace(now=lambda: datetime(2026, 10, 17, 4, 26, 25)),
    )
    monkeypatch.setattr(TraceContext, "current", lambda: None)


def config(show):
    """复用真实配置 getter，避免将开关逻辑替换为桩。"""
    result = object.__new__(ConfigManager)
    result.config = {"basic": {"show_report_caption": show}}
    return result


def caption_from_call(call):
    """统一读取适配器支持的位置或关键字 caption 参数。"""
    return call.args[2] if len(call.args) > 2 else call.kwargs.get("caption", "")


@pytest.mark.parametrize(
    "kind,title",
    [
        ("report", "📊 每日群聊分析报告已生成"),
        ("comic", "🎨 每日群漫画已生成"),
        ("wordcloud", "☁️ 群聊词云已生成"),
    ],
)
def test_generated_caption_content_and_existing_default(kind, title):
    assert TraceContext.make_report_caption(kind) == title + " | 10-17 04:26:25"
    assert (
        TraceContext.make_report_caption()
        == "📊 每日群聊分析报告已生成 | 10-17 04:26:25"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("show", [True, False])
@pytest.mark.parametrize("source", ["bytes", "fallback_url"])
async def test_comic_bytes_and_url_fallback_share_comic_caption(tmp_path, show, source):
    adapter = SimpleNamespace(send_image=AsyncMock(return_value=True))
    bot_manager = SimpleNamespace(get_adapter=Mock(return_value=adapter))
    generated = (
        (b"\x89PNG\r\n\x1a\ncomic", None)
        if source == "bytes"
        else (None, "https://example.com/comic.png")
    )
    handler = ComicCommandHandler(
        config(show),
        bot_manager,
        SimpleNamespace(generate_comic=AsyncMock(return_value=generated)),
        SimpleNamespace(),
        plugin_data_dir=tmp_path,
    )
    await handler._trigger_comic_generation([], "123", "bot", "bot:GroupMessage:123")
    adapter.send_image.assert_awaited_once()
    caption = caption_from_call(adapter.send_image.call_args)
    assert caption == ("🎨 每日群漫画已生成 | 10-17 04:26:25" if show else "")
    assert "群聊分析报告" not in caption
    if source == "fallback_url":
        assert adapter.send_image.call_args.args[1] == generated[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("show", [True, False])
@pytest.mark.parametrize("entry", ["report", "independent", "retry"])
async def test_wordcloud_caption_reaches_real_message_sender_for_all_entry_points(
    tmp_path, show, entry
):
    manager = config(show)
    adapter = SimpleNamespace(send_image=AsyncMock(return_value=True))
    sender = MessageSender(
        SimpleNamespace(get_adapter=Mock(return_value=adapter)), manager
    )
    delivery = WordCloudDeliveryService(
        manager,
        SimpleNamespace(render=AsyncMock(return_value=b"wordcloud")),
        WordCloudStore(tmp_path / "wordcloud.db"),
        sender,
    )
    data = WordCloudData((WordFrequency("高性能", 8, 6),), group_id="123")
    if entry == "report":
        assert await delivery.send_with_report(data, "123", "bot")
    elif entry == "retry":
        delivery.store.save("bot:GroupMessage:123", "cache", data, "cached")
        assert await delivery.send(
            delivery.store.latest("bot:GroupMessage:123"), "123", "bot", force=True
        )
    else:
        assert await delivery.send(data, "123", "bot", force=True)
    adapter.send_image.assert_awaited_once()
    assert caption_from_call(adapter.send_image.call_args) == (
        "☁️ 群聊词云已生成 | 10-17 04:26:25" if show else ""
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("show", [True, False])
async def test_report_followed_by_wordcloud_keeps_distinct_captions(tmp_path, show):
    manager = config(show)
    adapter = SimpleNamespace(
        send_image=AsyncMock(return_value=True),
        get_platform_name=lambda: "onebot",
    )
    sender = MessageSender(
        SimpleNamespace(get_adapter=Mock(return_value=adapter)), manager
    )
    generator = SimpleNamespace(
        data_dir=tmp_path,
        generate_image_report=AsyncMock(
            return_value=("base64://cmVwb3J0", "<html>日报</html>")
        ),
    )
    dispatcher = ReportDispatcher(manager, generator, sender)
    dispatcher.set_html_render(AsyncMock())
    dispatcher.wordcloud_delivery = WordCloudDeliveryService(
        manager,
        SimpleNamespace(render=AsyncMock(return_value=b"wordcloud")),
        WordCloudStore(tmp_path / "wordcloud.db"),
        sender,
    )
    data = WordCloudData((WordFrequency("高性能", 8, 6),), group_id="123")
    assert await dispatcher.dispatch("123", {"wordcloud": data}, "bot")
    captions = [caption_from_call(call) for call in adapter.send_image.call_args_list]
    assert captions == (
        [
            "📊 每日群聊分析报告已生成 | 10-17 04:26:25",
            "☁️ 群聊词云已生成 | 10-17 04:26:25",
        ]
        if show
        else ["", ""]
    )
