"""WebUI 自定义 T2I 测试入口：未保存配置、真实 HTTP、失败和取消。"""

import asyncio
import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image
from test_custom_t2i_service import service as service

from src.infrastructure.webui.routes import config_routes
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.fixture
def probe(monkeypatch):
    request = MagicMock(json=AsyncMock())
    monkeypatch.setattr(config_routes, "request", request)
    # 固定适配层的返回形态，测试不依赖宿主是否安装 Quart。
    monkeypatch.setattr(
        config_routes, "json_response", lambda data, **kwargs: {"data": data, **kwargs}
    )
    monkeypatch.setattr(
        config_routes,
        "error_response",
        lambda message, **kwargs: {"message": message, **kwargs},
    )
    config_manager = MagicMock()
    routes = ConfigRoutes(analysis_service=MagicMock(config_manager=config_manager))
    return routes, request, config_manager


@pytest.mark.asyncio
@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
async def test_unsaved_endpoint_and_token_render_real_image_without_saving(
    probe, service, image_format
):
    routes, request, config_manager = probe
    endpoint, state, messages, _ = service
    output = BytesIO()
    Image.new("RGB", (2, 2)).save(output, image_format)
    state["body"] = output.getvalue()
    request.json.return_value = {
        "service_endpoint": f" {endpoint}/generate/ ",
        "service_token": " current-token ",
        "timeout": 12000,
        "request_timeout": 24000,
        "html": "<script>不应提交任意页面</script>",
        "render_service": "custom",
    }
    result = await routes.api_test_t2i()
    data = result["data"]["data"]
    assert result["data"]["status"] == "ok"
    assert result["headers"] == {"Cache-Control": "no-store"}
    assert base64.b64decode(data["image_data_url"].split(",", 1)[1]) == state["body"]
    assert data["image_data_url"].startswith(f"data:image/{image_format.lower()};base64,")
    assert data["elapsed_ms"] >= 0
    assert "current-token" not in str(result)
    assert len(messages) == 1
    assert messages[0]["auth"] == "Bearer current-token"
    payload = messages[0]["payload"]
    assert "T2I 渲染测试" in payload["html"]
    assert "不应提交任意页面" not in payload["html"]
    assert "http://" not in payload["html"] and "https://" not in payload["html"]
    assert payload["json"] is False
    assert payload["options"] == {
        "type": "png",
        "full_page": False,
        "viewport_width": 480,
        "viewport_height": 180,
        "device_scale_factor_level": "normal",
        "timeout": 12000,
    }
    assert config_manager.mock_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        "bad",
        {"service_endpoint": "bad"},
        {"service_token": "secret\n"},
        {"timeout": True},
        {"request_timeout": 999},
        {"service_endpoint": "x" * 2049},
    ],
)
async def test_invalid_draft_never_calls_service(probe, monkeypatch, body):
    routes, request, _ = probe
    request.json.return_value = body
    render = AsyncMock()
    monkeypatch.setattr(config_routes, "render_custom_t2i", render)
    response = await routes.api_test_t2i()
    assert response["status_code"] == 400
    render.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_json_returns_400(probe):
    routes, request, _ = probe
    request.json.side_effect = ValueError("invalid JSON")
    assert (await routes.api_test_t2i())["status_code"] == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body",
    [
        (401, b"secret-token"),
        (500, b"failed"),
        (200, b"<html>error</html>"),
        (200, b"\x89PNG\r\n\x1a\nbroken"),
    ],
)
async def test_failed_service_does_not_report_success_or_echo_token(
    probe, service, status, body
):
    routes, request, _ = probe
    endpoint, state, _, _ = service
    state.update(status=status, body=body)
    request.json.return_value = {
        "service_endpoint": endpoint,
        "service_token": "secret-token",
    }
    response = await routes.api_test_t2i()
    assert response["status_code"] == 502
    assert "secret-token" not in str(response)
    assert "image_data_url" not in str(response)


@pytest.mark.asyncio
async def test_timeout_and_cancellation(probe, service):
    routes, request, _ = probe
    endpoint, state, _, started = service
    state["delay"] = 1.1
    request.json.return_value = {"service_endpoint": endpoint, "request_timeout": 1000}
    response = await routes.api_test_t2i()
    assert response["status_code"] == 502
    assert "超过 1 秒" in response["message"]
    started.clear()
    request.json.return_value["request_timeout"] = 10000
    task = asyncio.create_task(routes.api_test_t2i())
    await asyncio.wait_for(started.wait(), 10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_defaults_and_unexpected_errors_do_not_expose_draft(probe, monkeypatch):
    routes, request, _ = probe
    request.json.return_value = {}
    render = AsyncMock(side_effect=Exception("private-url secret-token"))
    monkeypatch.setattr(config_routes, "render_custom_t2i", render)
    response = await routes.api_test_t2i()
    assert response["status_code"] == 502
    assert "private-url" not in str(response) and "secret-token" not in str(response)
    args, kwargs = render.call_args
    assert args[0] == "http://127.0.0.1:8999/text2img"
    assert args[2]["timeout"] == 20000
    assert args[3] == ""
    assert kwargs == {"request_timeout_ms": 40000}


@pytest.mark.asyncio
@pytest.mark.parametrize("as_path", [False, True])
@pytest.mark.parametrize("target", [{}, {"group_id": "123", "platform_id": "onebot_1"}])
async def test_astrbot_probe_uses_same_callback_and_group_binding(probe, tmp_path, monkeypatch, as_path, target):
    routes, request, config_manager = probe
    output = BytesIO()
    Image.new("RGB", (3, 2)).save(output, "PNG")
    png = output.getvalue()
    image_path = tmp_path / "host.png"
    image_path.write_bytes(png)
    calls = []

    async def host_render(html, data, return_url, options, umo=None):
        calls.append((html, data, return_url, options, umo))
        return str(image_path) if as_path else png

    routes.analysis_service.html_render = host_render
    custom = AsyncMock()
    monkeypatch.setattr(config_routes, "render_custom_t2i", custom)
    request.json.return_value = {"render_service": "astrbot", "timeout": 12000, **target}
    result = await routes.api_test_t2i()
    assert base64.b64decode(result["data"]["data"]["image_data_url"].split(",")[1]) == png
    html, data, return_url, options, umo = calls[0]
    assert "T2I 渲染测试" in html and "http" not in html
    assert data == {} and return_url is False and options["timeout"] == 12000
    assert umo == ("onebot_1:GroupMessage:123" if target else None)
    assert image_path.read_bytes() == png
    assert result["headers"] == {"Cache-Control": "no-store"}
    config_manager.save_config.assert_not_called()
    custom.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_astrbot_callback_without_umo_still_works(probe):
    routes, request, _ = probe
    output = BytesIO()
    Image.new("RGB", (3, 2)).save(output, "JPEG")

    async def legacy(html, data, return_url, options):
        return output.getvalue()

    routes.analysis_service.html_render = legacy
    request.json.return_value = {"render_service": "astrbot", "platform_id": "old", "group_id": "1"}
    result = await routes.api_test_t2i()
    assert result["data"]["data"]["image_data_url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [None, "", b"", b"<html>private-token</html>", b"\x89PNG\r\n\x1a\nbroken", "missing/private-token.png", 123])
async def test_astrbot_bad_response_never_reports_success(probe, output):
    routes, request, _ = probe
    routes.analysis_service.html_render = AsyncMock(return_value=output)
    request.json.return_value = {"render_service": "astrbot"}
    result = await routes.api_test_t2i()
    assert result["status_code"] == 502
    assert "image_data_url" not in str(result) and "private-token" not in str(result)


@pytest.mark.asyncio
async def test_astrbot_oversized_response_is_rejected_before_decoding(probe, tmp_path):
    routes, request, _ = probe
    path = tmp_path / "huge.png"
    with path.open("wb") as stream:
        stream.truncate(32 * 1024 * 1024 + 1)
    routes.analysis_service.html_render = AsyncMock(return_value=str(path))
    request.json.return_value = {"render_service": "astrbot"}
    assert (await routes.api_test_t2i())["status_code"] == 502


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [
    {"render_service": "other"}, {"render_service": []},
    {"render_service": "astrbot", "group_id": "1"},
    {"render_service": "astrbot", "platform_id": "onebot"},
    {"group_id": 1, "platform_id": "onebot"},
    {"group_id": "1", "platform_id": "bad\n"},
])
async def test_invalid_service_or_partial_target_never_renders(probe, body):
    routes, request, _ = probe
    routes.analysis_service.html_render = AsyncMock()
    request.json.return_value = body
    assert (await routes.api_test_t2i())["status_code"] == 400
    routes.analysis_service.html_render.assert_not_awaited()


@pytest.mark.asyncio
async def test_astrbot_unavailable_and_exception_do_not_expose_credentials(probe):
    routes, request, _ = probe
    request.json.return_value = {"render_service": "astrbot"}
    routes.analysis_service.html_render = None
    assert (await routes.api_test_t2i())["status_code"] == 503
    for error in [RuntimeError("http://user:private-token@host/"), OSError("private-token")]:
        routes.analysis_service.html_render = AsyncMock(side_effect=error)
        result = await routes.api_test_t2i()
        assert result["status_code"] == 502 and "private-token" not in str(result)


@pytest.mark.asyncio
async def test_astrbot_timeout_and_cancellation(probe, monkeypatch):
    routes, request, _ = probe
    started = asyncio.Event()

    async def wait_for_render(*_):
        started.set()
        await asyncio.sleep(10)

    routes.analysis_service.html_render = wait_for_render
    request.json.return_value = {"render_service": "astrbot"}
    monkeypatch.setattr(config_routes, "asyncio", SimpleNamespace(timeout=lambda _: asyncio.timeout(0.01), to_thread=asyncio.to_thread))
    assert (await routes.api_test_t2i())["status_code"] == 502
    started.clear()
    monkeypatch.setattr(config_routes, "asyncio", asyncio)
    task = asyncio.create_task(routes.api_test_t2i())
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
