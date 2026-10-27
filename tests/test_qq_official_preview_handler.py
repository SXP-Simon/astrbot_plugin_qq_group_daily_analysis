"""QQ 官方预览的请求协议、按钮语义与权限回退。"""

import sys
import logging
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.infrastructure.platform.template_preview.qq_official_preview_handler import (
    QQOfficialTemplatePreviewHandler,
)


class Result:
    def __init__(self, kind, value):
        self.kind, self.value = kind, value
        self.markdown = self.t2i = None

    def use_markdown(self, enabled):
        self.markdown = enabled
        return self

    def use_t2i(self, enabled):
        self.t2i = enabled
        return self


@pytest.fixture
def preview(monkeypatch):
    http = ModuleType("botpy.http")
    http.Route = lambda method, path, **params: SimpleNamespace(
        method=method, path=path, params=params
    )
    messages = ModuleType("botpy.types.message")
    messages.KeyboardPayload = dict
    messages.MarkdownPayload = dict
    monkeypatch.setitem(sys.modules, "botpy.http", http)
    monkeypatch.setitem(sys.modules, "botpy.types.message", messages)
    config = Mock()
    config.get_report_template.return_value = "scrapbook"
    service = Mock()
    service.resolve_template_preview_source.return_value = "demo.webp"
    cache = SimpleNamespace(get_jpeg=AsyncMock(return_value="/cache/demo.jpg"))
    handler = QQOfficialTemplatePreviewHandler(config, service, cache)
    request = AsyncMock(return_value={"id": "reply"})
    event = SimpleNamespace(
        get_platform_name=lambda: "qq_official",
        get_sender_id=lambda: "requester",
        message_obj=SimpleNamespace(
            message_id="incoming", raw_message=SimpleNamespace(group_openid="group")
        ),
        bot=SimpleNamespace(
            api=SimpleNamespace(_http=SimpleNamespace(request=request))
        ),
        plain_result=lambda text: Result("plain", text),
        image_result=lambda path: Result("image", path),
    )
    event.sent = []
    event.send = AsyncMock(side_effect=lambda result: event.sent.append(result))
    return handler, event, request


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "path", "params", "v2"),
    [
        (
            {"group_openid": "group"},
            "/v2/groups/{group_openid}/messages",
            {"group_openid": "group"},
            True,
        ),
        ({}, "/v2/users/{openid}/messages", {"openid": "requester"}, True),
        (
            {"channel_id": "channel"},
            "/channels/{channel_id}/messages",
            {"channel_id": "channel"},
            False,
        ),
        (
            {"channel_id": "channel", "guild_id": "guild", "direct_message": True},
            "/dms/{guild_id}/messages",
            {"guild_id": "guild"},
            False,
        ),
    ],
)
async def test_native_routes_and_command_buttons(preview, raw, path, params, v2):
    handler, event, request = preview
    event.message_obj.raw_message = SimpleNamespace(**raw)
    handled, results = await handler.handle_view_templates(
        event, "qq", ["scrapbook", "ATRI"], "ATRI"
    )
    assert handled and results == []
    results = event.sent
    assert len(results) == 1
    assert (results[0].kind, results[0].value) == ("image", "/cache/demo.jpg")
    assert results[0].markdown is False and results[0].t2i is False
    route = request.call_args.args[0]
    payload = request.call_args.kwargs["json"]
    assert route.method == "POST" and route.path == path and route.params == params
    assert payload["msg_id"] == "incoming"
    assert ("msg_type" in payload) is v2
    assert ("msg_seq" in payload) is v2
    if v2:
        assert payload["msg_type"] == 2 and payload["msg_seq"] > 10000
    assert "ATRI" in payload["markdown"]["content"]
    buttons = payload["keyboard"]["content"]["rows"][0]["buttons"]
    assert [b["action"]["data"] for b in buttons] == [
        "/查看模板 1",
        "/查看模板 1",
        "/设置模板 2",
    ]
    for button in buttons:
        action = button["action"]
        assert action["type"] == 2
        assert action["permission"]["specify_user_ids"] == ["requester"]
        assert not action.get("enter", False)
    handler.config_manager.set_report_template.assert_not_called()
    handler.template_service.resolve_template_preview_source.assert_called_once_with(
        "ATRI"
    )
    handler.image_cache.get_jpeg.assert_awaited_once_with("demo.webp")


@pytest.mark.asyncio
async def test_button_permission_failure_retries_only_markdown(preview):
    handler, event, request = preview
    request.side_effect = [RuntimeError("没有按钮权限"), {"id": "reply"}]
    _, results = await handler.handle_view_templates(event, "qq", ["scrapbook"])
    assert results == []
    results = event.sent
    assert len(results) == 1 and results[0].kind == "image"
    first, second = [call.kwargs["json"] for call in request.call_args_list]
    assert "keyboard" in first and "keyboard" not in second
    assert second["msg_seq"] == first["msg_seq"] + 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["permission", "no_bot", "old_sdk"])
async def test_native_unavailable_keeps_plain_and_jpeg(preview, monkeypatch, failure):
    handler, event, request = preview
    if failure == "permission":
        request.side_effect = RuntimeError("不允许发送原生 markdown")
    elif failure == "no_bot":
        event.bot = None
    else:
        monkeypatch.setitem(
            sys.modules, "botpy.types.message", ModuleType("botpy.types.message")
        )
    _, results = await handler.handle_view_templates(event, "qq", ["scrapbook"])
    assert results == []
    results = event.sent
    assert [result.kind for result in results] == ["plain", "image"]
    assert "/设置模板 1" not in results[0].value
    assert "/设置模板 序号" in results[0].value
    assert all(result.markdown is False and result.t2i is False for result in results)
    assert request.call_count == (2 if failure == "permission" else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [False, True])
async def test_image_unavailable_does_not_prevent_selection(preview, missing):
    handler, event, _ = preview
    if missing:
        handler.template_service.resolve_template_preview_source.return_value = None
    else:
        handler.image_cache.get_jpeg.side_effect = ValueError("不是图片")
    handled, results = await handler.handle_view_templates(event, "qq", ["scrapbook"])
    assert handled and results == []
    results = event.sent
    assert handled and results[0].kind == "plain"
    assert "预览图" in results[0].value
    handler.config_manager.set_report_template.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_empty_list_and_other_platform(preview):
    handler, event, request = preview
    event.get_platform_name = lambda: "qq_official_webhook"
    assert handler.supports(event)
    handled, results = await handler.handle_view_templates(event, "qq", [])
    assert handled and results[0].t2i is False
    request.assert_not_called()
    event.get_platform_name = lambda: "aiocqhttp"
    assert await handler.handle_view_templates(event, "qq", ["scrapbook"]) == (
        False,
        [],
    )


@pytest.mark.asyncio
async def test_success_waits_for_image_send_and_only_logs_debug(preview, caplog):
    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    handler, event, _ = preview
    assert await handler.handle_view_templates(event, "qq", ["scrapbook"]) == (True, [])
    event.send.assert_awaited_once()
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "QQ 原生发送开始" in messages
    assert "QQ 原生接口返回成功" in messages
    assert "QQ 宿主发送调用完成（非送达回执）" in messages
    assert not [record for record in caplog.records if record.levelno >= logging.INFO]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["native", "prepare", "image", "plain"])
async def test_failures_are_warnings_without_sensitive_error_body(
    preview, caplog, stage
):
    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    handler, event, request = preview
    secret = (
        "Bearer private-token https://user:pass@example.test/private-path?token=secret"
    )
    if stage == "native":
        request.side_effect = RuntimeError(secret)
    elif stage == "prepare":
        handler.image_cache.get_jpeg.side_effect = ValueError(secret)
    elif stage == "image":
        event.send.side_effect = RuntimeError(secret)
    else:
        event.bot = None
        event.send.side_effect = [RuntimeError(secret), None]
    assert await handler.handle_view_templates(event, "qq", ["scrapbook"]) == (True, [])
    messages = "\n".join(record.getMessage() for record in caplog.records)
    warnings = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
    )
    assert warnings
    if stage == "native":
        assert "将使用普通文字和图片" in warnings
    elif stage == "prepare":
        assert "图片准备失败" in warnings
    else:
        assert f"kind={stage}" in warnings
        assert "QQ 发送失败" in warnings
    assert not [record for record in caplog.records if record.levelno == logging.INFO]
    for sensitive in ["private-token", "user:pass", "private-path", "token=secret"]:
        assert sensitive not in messages


@pytest.mark.asyncio
async def test_empty_native_response_is_observable_and_falls_back(preview, caplog):
    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    handler, event, request = preview
    request.return_value = None
    await handler.handle_view_templates(event, "qq", ["scrapbook"])
    assert event.send.await_count == 2
    assert any(
        record.levelno == logging.WARNING and "QQ 接口未返回结果" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_permission_rejection_has_actionable_warning_without_sdk_body(
    preview, caplog
):
    class ForbiddenError(RuntimeError):
        pass

    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    handler, event, request = preview
    request.side_effect = ForbiddenError("Authorization: Bearer secret-response-token")
    await handler.handle_view_templates(event, "qq", ["scrapbook"])
    warnings = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
    )
    assert "QQ 接口拒绝访问，请检查消息及按钮权限" in warnings
    assert "secret-response-token" not in caplog.text
    assert [result.kind for result in event.sent] == ["plain", "image"]


@pytest.mark.asyncio
@pytest.mark.parametrize("native_fails", [False, True])
async def test_settings_to_real_qq_router_awaits_cached_image(
    preview, tmp_path, caplog, native_fails
):
    from PIL import Image

    from src.application.handlers.settings_command_handler import SettingsCommandHandler
    from src.infrastructure.platform.template_preview.image_cache import (
        PreviewImageCache,
    )
    from src.infrastructure.platform.template_preview.router import (
        TemplatePreviewRouter,
    )

    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    qq, event, request = preview
    source = tmp_path / "demo.webp"
    Image.new("RGB", (20, 16), "green").save(source)
    qq.template_service.resolve_template_preview_source.return_value = str(source)
    qq.template_service.list_available_templates.return_value = ["scrapbook"]
    qq.image_cache = PreviewImageCache(tmp_path / "cache")
    if native_fails:
        request.side_effect = RuntimeError("private SDK response")
    event.should_call_llm = Mock()
    router = TemplatePreviewRouter([qq], qq.template_service, qq.image_cache)
    settings = SettingsCommandHandler(
        qq.config_manager, qq.template_service, router, Mock(), context=Mock()
    )
    assert [
        result async for result in settings.handle_view_templates(event, "qq")
    ] == []
    assert event.send.await_count == (2 if native_fails else 1)
    image = event.sent[-1]
    assert image.kind == "image"
    with Image.open(image.value) as decoded:
        assert decoded.format == "JPEG" and decoded.size == (20, 16)
    qq.template_service.build_template_preview_nodes.assert_not_called()
    assert any(
        "handler=QQOfficialTemplatePreviewHandler supported=True" in record.getMessage()
        for record in caplog.records
    )
    assert not [record for record in caplog.records if record.levelno == logging.INFO]
