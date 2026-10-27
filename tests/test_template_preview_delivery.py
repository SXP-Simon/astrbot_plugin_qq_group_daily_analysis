"""预览路由与 Telegram 实际传给发送接口的图片内容。"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image as PillowImage

from src.infrastructure.platform.template_preview import (
    router,
    telegram_preview_handler,
)
from src.infrastructure.platform.template_preview.image_cache import PreviewImageCache
from src.infrastructure.platform.template_preview.router import TemplatePreviewRouter
from src.infrastructure.platform.template_preview.telegram_preview_handler import (
    TelegramTemplatePreviewHandler,
    _PreviewSession,
)


class PreviewImage:
    def __init__(self, file):
        self.file, self.url = file, None

    @classmethod
    def fromFileSystem(cls, path):
        return cls(path)


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["", "2", "ATRI"])
async def test_merged_forward_keeps_nodes_and_converts_images(
    tmp_path, monkeypatch, selection
):
    monkeypatch.setattr(router, "Image", PreviewImage)
    source = tmp_path / "demo.webp"
    PillowImage.new("RGB", (16, 16), "blue").save(source)
    nodes = SimpleNamespace(
        nodes=[
            SimpleNamespace(content=["header"]),
            SimpleNamespace(content=["1. scrapbook", PreviewImage(str(source))]),
            SimpleNamespace(content=["2. ATRI", PreviewImage(str(source))]),
        ]
    )
    service = Mock()
    service.config_provider.get_report_template.return_value = "scrapbook"
    service.build_template_preview_nodes.return_value = nodes
    service.parse_template_input.return_value = ("ATRI", None)
    event = SimpleNamespace(
        get_self_id=lambda: "bot",
        get_platform_name=lambda: "aiocqhttp",
        chain_result=lambda chain: chain,
    )
    handler = TemplatePreviewRouter(
        template_service=service, image_cache=PreviewImageCache(tmp_path / "cache")
    )
    handled, results = await handler.handle_view_templates(
        event, "qq", ["scrapbook", "ATRI"], selection
    )
    assert handled and results[0] == [nodes]
    assert len(nodes.nodes) == (2 if selection else 3)
    if selection:
        assert nodes.nodes[1].content[0] == "2. ATRI"
    for node in nodes.nodes[1:]:
        path = Path(node.content[1].file)
        assert path.read_bytes().startswith(b"\xff\xd8\xff")
    assert len(list((tmp_path / "cache").glob("*.jpg"))) == 1


@pytest.mark.asyncio
async def test_failed_images_keep_text_and_one_warning(monkeypatch):
    monkeypatch.setattr(router, "Image", PreviewImage)
    warning = Mock()
    monkeypatch.setattr(router.logger, "warning", warning)
    nodes = SimpleNamespace(
        nodes=[
            SimpleNamespace(content=["template", PreviewImage("a"), PreviewImage("b")])
        ]
    )
    service = Mock()
    service.build_template_preview_nodes.return_value = nodes
    cache = SimpleNamespace(get_jpeg=AsyncMock(side_effect=ValueError("读取失败")))
    handler = TemplatePreviewRouter(template_service=service, image_cache=cache)
    event = SimpleNamespace(
        get_self_id=lambda: "bot",
        get_platform_name=lambda: "aiocqhttp",
        chain_result=lambda chain: chain,
    )
    assert (await handler.handle_view_templates(event, "qq", ["scrapbook"]))[0]
    assert nodes.nodes[0].content[0] == "template"
    assert all(
        "暂时不可用" in component.text for component in nodes.nodes[0].content[1:]
    )
    warning.assert_called_once()


@pytest.mark.asyncio
async def test_unknown_selection_does_not_download():
    service = Mock()
    service.parse_template_input.return_value = (None, "无效序号")
    cache = SimpleNamespace(get_jpeg=AsyncMock())
    result = Mock()
    result.use_markdown.return_value = result
    result.use_t2i.return_value = result
    event = SimpleNamespace(plain_result=Mock(return_value=result))
    handler = TemplatePreviewRouter(template_service=service, image_cache=cache)
    assert await handler.handle_view_templates(event, "qq", ["scrapbook"], "999") == (
        True,
        [result],
    )
    cache.get_jpeg.assert_not_called()
    service.build_template_preview_nodes.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["qq_official", "qq_official_webhook"])
async def test_missing_qq_handler_warns_and_never_builds_nodes(caplog, platform):
    import logging

    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    service = Mock()
    result = Mock()
    result.use_markdown.return_value = result
    result.use_t2i.return_value = result
    event = SimpleNamespace(
        get_platform_name=lambda: platform, plain_result=Mock(return_value=result)
    )
    handler = TemplatePreviewRouter(template_service=service, image_cache=Mock())
    assert await handler.handle_view_templates(event, "qq", ["scrapbook"]) == (
        True,
        [result],
    )
    service.build_template_preview_nodes.assert_not_called()
    assert any(
        record.levelno == logging.WARNING and "路由未命中" in record.getMessage()
        for record in caplog.records
    )
    result.use_markdown.assert_called_once_with(False)
    result.use_t2i.assert_called_once_with(False)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["initial", "fallback", "edit"])
async def test_telegram_all_paths_send_cached_jpeg(tmp_path, monkeypatch, operation):
    monkeypatch.setattr(telegram_preview_handler, "TELEGRAM_RUNTIME_AVAILABLE", True)
    source = tmp_path / "demo.webp"
    PillowImage.new("RGB", (16, 16), "green").save(source)
    config, service = Mock(), Mock()
    config.get_report_template.return_value = "scrapbook"
    service.resolve_template_preview_source.return_value = str(source)
    handler = TelegramTemplatePreviewHandler(
        config, service, PreviewImageCache(tmp_path / "cache")
    )
    monkeypatch.setattr(handler, "_build_keyboard", lambda _: None)
    received = []

    async def send_photo(**kwargs):
        received.append(kwargs["photo"].read())
        return SimpleNamespace(message_id=1)

    client = SimpleNamespace(send_photo=send_photo)
    monkeypatch.setattr(handler, "_get_event_client", lambda *_: client)
    event = SimpleNamespace(get_group_id=lambda: "123", get_sender_id=lambda: "456")
    if operation == "initial":
        assert await handler.send_preview_message(
            event, "tg", ["scrapbook", "ATRI"], "ATRI"
        )
        service.resolve_template_preview_source.assert_called_once_with("ATRI")
    elif operation == "fallback":
        assert await handler.send_preview_image_fallback(event, "tg", "scrapbook")
    else:
        monkeypatch.setattr(
            telegram_preview_handler, "InputMediaPhoto", lambda **kwargs: kwargs
        )

        async def edit_message_media(**kwargs):
            received.append(kwargs["media"]["media"].read())

        query = SimpleNamespace(edit_message_media=edit_message_media)
        session = _PreviewSession("token", "tg", 123, None, 1, 456, ["scrapbook"], 0, 0)
        await handler._edit_preview_message(query, session)
    assert len(received) == 1 and received[0].startswith(b"\xff\xd8\xff")
    assert source.exists()
