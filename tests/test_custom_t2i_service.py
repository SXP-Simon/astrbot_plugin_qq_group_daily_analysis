"""自定义 T2I 地址边界、真实 HTTP 契约与多轮回退集成测试。"""

import asyncio
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiohttp import web
from PIL import Image
from test_rendering_strategies import rendering as rendering
from test_template_section_conditional_rendering import create_analysis_result

from src.infrastructure.config.rendering_config import (
    normalize_t2i_endpoint,
    parse_rendering_strategies,
)
from src.infrastructure.reporting.custom_t2i_client import render_custom_t2i
from src.shared.trace_context import TraceContext

CASES = json.loads(
    (Path(__file__).parent / "data/t2i_endpoints.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("value,expected", CASES["valid"])
def test_endpoint_normalization(value, expected):
    assert normalize_t2i_endpoint(value) == expected
    plan = parse_rendering_strategies(
        [{"render_service": "custom", "service_endpoint": value}]
    )[0]
    assert plan["service_endpoint"] == expected


@pytest.mark.parametrize("value", CASES["invalid"])
def test_invalid_endpoint_is_rejected(value):
    with pytest.raises(ValueError):
        normalize_t2i_endpoint(value)
    with pytest.raises(ValueError):
        parse_rendering_strategies(
            [{"render_service": "custom", "service_endpoint": value}]
        )


@pytest.mark.parametrize(
    "value",
    [
        {"render_service": "local"},
        {"service_endpoint": 1},
        {"service_token": 1},
        {"service_token": "secret\r\nInjected: yes"},
        {"service_token": "密钥"},
    ],
)
def test_invalid_service_fields_are_rejected(value):
    with pytest.raises(ValueError):
        parse_rendering_strategies([value])


def test_old_plans_keep_host_default_and_inactive_endpoint():
    plan = parse_rendering_strategies([{"service_endpoint": "尚未填写完整"}])[0]
    assert plan["render_service"] == "astrbot"
    assert plan["service_endpoint"] == "尚未填写完整"
    assert plan["service_token"] == ""


@pytest_asyncio.fixture
async def service():
    """临时 HTTP 服务复现两种 T2I 的公开协议，不启动 Chromium。"""
    output = BytesIO()
    Image.new("RGB", (2, 2)).save(output, "PNG")
    state = {"status": 200, "body": output.getvalue(), "delay": 0}
    messages = []
    started = asyncio.Event()

    async def generate(request):
        messages.append(
            {
                "path": request.path,
                "payload": await request.json(),
                "auth": request.headers.get("Authorization"),
            }
        )
        started.set()
        if state["delay"]:
            await asyncio.sleep(state["delay"])
        return web.Response(status=state["status"], body=state["body"])

    app = web.Application()
    app.router.add_post("/text2img/generate", generate)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        endpoint = f"http://127.0.0.1:{runner.addresses[0][1]}/text2img"
        yield endpoint, state, messages, started
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_real_http_uses_html_binary_response_bearer_and_direct_connection(
    service, monkeypatch
):
    endpoint, state, messages, _started = service
    for variable in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(variable, "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    options = {
        "type": "png",
        "full_page": True,
        "timeout": 20000,
        "device_scale_factor_level": "high",
    }
    before = deepcopy(options)
    result = await render_custom_t2i(
        endpoint + "/generate/", "<html>{{原样内容}}</html>", options, "my-secret"
    )
    assert result == state["body"]
    assert messages == [
        {
            "path": "/text2img/generate",
            "payload": {
                "html": "<html>{{原样内容}}</html>",
                "json": False,
                "options": options,
            },
            "auth": "Bearer my-secret",
        }
    ]
    assert options == before


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 401, 413, 503])
async def test_status_and_non_image_errors_are_useful_and_redact_token(service, status):
    endpoint, state, _messages, _started = service
    state.update(status=status, body=b'{"message":"my-secret Chromium not ready"}')
    with pytest.raises((ValueError, RuntimeError)) as caught:
        await render_custom_t2i(endpoint, "html", {}, "my-secret")
    assert "my-secret" not in str(caught.value)
    assert "Chromium not ready" in str(caught.value)
    if status != 200:
        assert f"HTTP {status}" in str(caught.value)
    if status == 401:
        assert "Token" in str(caught.value)


@pytest.mark.asyncio
async def test_per_attempt_timeout_and_cancellation_are_preserved(service):
    endpoint, state, _messages, started = service
    state["delay"] = 0.1
    with pytest.raises(TimeoutError):
        await render_custom_t2i(endpoint, "html", {"timeout": 10})
    started.clear()
    task = asyncio.create_task(render_custom_t2i(endpoint, "html", {}))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("custom_first", [True, False])
async def test_host_and_custom_service_fallback_preserves_resources_and_records_service(
    rendering, service, monkeypatch, custom_first
):
    manager, generator, png = rendering
    endpoint, state, messages, _started = service
    custom = {
        "render_service": "custom",
        "service_endpoint": endpoint + "/generate",
        "service_token": "my-secret",
        "environment": "Overseas",
        "priority": 10 if custom_first else 20,
    }
    host = {"priority": 20 if custom_first else 10, "environment": "Mainland"}
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [host, custom]
    original = deepcopy(manager.config)
    if custom_first:
        state.update(status=503, body=b'{"message":"Chromium not ready"}')
    render = AsyncMock(return_value=png if custom_first else None)
    trace = TraceContext(trace_id="custom-service")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    with trace.span("RENDER_REPORT") as span:
        image, html = await generator.generate_image_report(
            create_analysis_result(), "123", render
        )
    assert image
    render.assert_awaited_once()
    assert len(messages) == 1
    assert "https://overseas.example/gh/" in messages[0]["payload"]["html"]
    assert "https://mainland.example/gh/" in render.await_args.args[0]
    assert html == (
        render.await_args.args[0] if custom_first else messages[0]["payload"]["html"]
    )
    for options in (messages[0]["payload"]["options"], render.await_args.args[3]):
        assert not {
            "render_service",
            "service_endpoint",
            "service_token",
            "resource_environment",
        }.intersection(options)
    assert manager.config == original
    assert "my-secret" not in json.dumps(span, ensure_ascii=False)
    attempts = span["payload"]["render_attempts"]
    assert [item["status"] for item in attempts] == ["failed", "success"]
    assert (
        attempts[0 if custom_first else 1]["render_service"]["configured_endpoint"]
        == endpoint
    )


@pytest.mark.asyncio
async def test_custom_service_does_not_require_host_callback(rendering, service):
    manager, generator, _png = rendering
    endpoint, _state, messages, _started = service
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"render_service": "custom", "service_endpoint": endpoint}
    ]
    assert (
        await generator.generate_image_report(create_analysis_result(), "123", None)
    )[0]
    assert len(messages) == 1
