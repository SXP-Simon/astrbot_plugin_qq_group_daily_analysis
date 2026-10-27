"""QQ 官方预览的请求协议、按钮语义与权限回退。"""

import sys
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
    assert handled and len(results) == 1
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
