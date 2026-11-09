"""
单元测试：Telegram 模板预览交互与路由分发
测试 TelegramTemplatePreviewHandler 与 TemplatePreviewRouter
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from PIL import Image

from astrbot_plugin_qq_group_daily_analysis.src.application.services.template_command_service import (
    TemplateCommandService,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.config.config_manager import (
    ConfigManager,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.platform.template_preview.router import (
    TemplatePreviewRouter,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.platform.template_preview.telegram_preview_handler import (
    TelegramTemplatePreviewHandler,
    _PreviewSession,
)


@pytest.fixture
def mock_config_manager():
    cfg = {
        "basic": {
            "report_template": "scrapbook",
        }
    }
    return ConfigManager(cfg)


@pytest.fixture
def mock_template_service(tmp_path: Path):
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    (tpl_dir / "scrapbook").mkdir()
    (tpl_dir / "ATRI").mkdir()
    (tpl_dir / "HatsuneMiku").mkdir()

    svc = TemplateCommandService(plugin_root=str(tmp_path))
    return svc


@pytest.fixture
def preview_handler(mock_config_manager, mock_template_service):
    return TelegramTemplatePreviewHandler(
        config_manager=mock_config_manager,
        template_service=mock_template_service,
    )


@pytest.fixture
def preview_router(preview_handler):
    return TemplatePreviewRouter(handlers=[preview_handler])


def test_telegram_preview_handler_supports(preview_handler):
    tg_event = SimpleNamespace(
        get_platform_name=Mock(return_value="telegram"),
        platform_meta=SimpleNamespace(name="telegram"),
    )
    qq_event = SimpleNamespace(
        get_platform_name=Mock(return_value="aiocqhttp"),
        platform_meta=SimpleNamespace(name="aiocqhttp"),
    )

    assert preview_handler.supports(tg_event) is True
    assert preview_handler.supports(qq_event) is False


def test_preview_session_dataclass():
    session = _PreviewSession(
        token="token123",
        platform_id="tg_1",
        chat_id=123456,
        message_thread_id=None,
        message_id=999,
        requester_id=1001,
        templates=["scrapbook", "ATRI"],
        index=1,
        created_at=1000.0,
    )
    assert session.current_template == "ATRI"
    assert session.token == "token123"


@pytest.mark.asyncio
async def test_preview_router_delegates(preview_router, preview_handler):
    tg_event = SimpleNamespace(
        get_platform_name=Mock(return_value="telegram"),
        platform_meta=SimpleNamespace(name="telegram"),
    )
    qq_event = SimpleNamespace(
        get_platform_name=Mock(return_value="aiocqhttp"),
        platform_meta=SimpleNamespace(name="aiocqhttp"),
    )

    preview_handler.handle_view_templates = AsyncMock(
        return_value=(True, [{"type": "plain", "text": "tg ok"}])
    )

    # 1. Telegram 事件被 handler 处理
    handled, results = await preview_router.handle_view_templates(
        tg_event, "tg_1", ["scrapbook", "ATRI"]
    )
    assert handled is True
    assert len(results) == 1
    assert results[0]["text"] == "tg ok"

    # 2. QQ 事件不被 Telegram handler 处理
    handled, results = await preview_router.handle_view_templates(
        qq_event, "qq_1", ["scrapbook", "ATRI"]
    )
    assert handled is False
    assert len(results) == 0


@pytest.mark.asyncio
async def test_comic_router_sends_read_only_telegram_gallery_and_edits_image(
    preview_router, preview_handler, tmp_path, monkeypatch
):
    image = tmp_path / "preview.jpg"
    Image.new("RGB", (20, 20)).save(image)
    preview_handler.comic_preview_cache = SimpleNamespace(
        get_preview=AsyncMock(return_value=image)
    )
    client = SimpleNamespace(send_photo=AsyncMock(return_value=SimpleNamespace(message_id=8)))
    monkeypatch.setattr(preview_handler, "_get_event_client", lambda *_: client)
    event = Mock()
    event.get_platform_name.return_value = "telegram"
    event.get_platform_id.return_value = "telegram_1"
    event.get_group_id.return_value = "123"
    event.get_sender_id.return_value = "456"

    assert await preview_router.view_comic_styles(event, "") is None
    payload = client.send_photo.call_args.kwargs
    assert "原版漫画" in payload["caption"]
    buttons = payload["reply_markup"].inline_keyboard[0]
    assert [button.text for button in buttons] == ["←", "→"]
    session = next(iter(preview_handler._sessions.values()))
    query = SimpleNamespace(
        from_user=SimpleNamespace(id=456),
        message=SimpleNamespace(message_id=8, chat_id=123),
        data=buttons[1].callback_data,
        edit_message_media=AsyncMock(),
        answer=AsyncMock(),
    )
    update = SimpleNamespace(callback_query=query)
    await preview_handler._on_callback_query(update, None)
    assert preview_handler.comic_preview_cache.get_preview.call_args.args == (
        session.current_template,
        "preview",
    )
    assert session.index == 1
    query.edit_message_media.assert_awaited_once()

    query.data = query.data.removesuffix(":next") + ":apply"
    await preview_handler._on_callback_query(update, None)
    assert preview_handler.config_manager.get_report_template() == "scrapbook"
    query.answer.assert_awaited_with("漫画预览仅供浏览", show_alert=True)


@pytest.mark.asyncio
async def test_preview_handler_session_cleanup(preview_handler):
    # 模拟过期 session
    import time

    old_session = _PreviewSession(
        token="old_tok",
        platform_id="tg_1",
        chat_id=123,
        message_thread_id=None,
        message_id=1,
        requester_id=1001,
        templates=["scrapbook"],
        index=0,
        created_at=time.time() - 10000,  # 远超 TTL
    )
    fresh_session = _PreviewSession(
        token="fresh_tok",
        platform_id="tg_1",
        chat_id=123,
        message_thread_id=None,
        message_id=2,
        requester_id=1001,
        templates=["scrapbook"],
        index=0,
        created_at=time.time(),
    )

    preview_handler._sessions["old_tok"] = old_session
    preview_handler._sessions["fresh_tok"] = fresh_session

    preview_handler._cleanup_expired_sessions()
    assert "old_tok" not in preview_handler._sessions
    assert "fresh_tok" in preview_handler._sessions


@pytest.mark.asyncio
async def test_preview_handler_register_and_unregister(preview_handler):
    mock_context = SimpleNamespace(
        platform_manager=SimpleNamespace(
            get_insts=Mock(return_value=[]),
        )
    )
    await preview_handler.ensure_callback_handlers_registered(mock_context)
    await preview_handler.unregister_callback_handlers()
    assert len(preview_handler._registered_platform_ids) == 0
