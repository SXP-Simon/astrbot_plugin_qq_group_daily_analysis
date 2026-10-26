"""自定义 T2I 地址边界、真实 HTTP 契约与多轮回退集成测试。"""

import asyncio
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.shared.trace_context import TraceContext

CASES = json.loads(
    (Path(__file__).parent / "data/t2i_endpoints.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "case",
    json.loads((Path(__file__).parent / "data/rendering_services.json").read_text(encoding="utf-8")),
)
def test_shared_service_presets_and_legacy_contract(case):
    original = deepcopy(case["plan"])
    if case["expected"] is None:
        with pytest.raises(ValueError):
            parse_rendering_strategies([case["plan"]])
    else:
        plan = parse_rendering_strategies([case["plan"]])[0]
        assert {key: plan[key] for key in case["expected"]} == case["expected"]
    assert case["plan"] == original


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
        if state.get("stream"):
            response = web.StreamResponse(status=state["status"])
            await response.prepare(request)
            try:
                for chunk in state["body"]:
                    await response.write(chunk)
                await response.write_eof()
            except ConnectionResetError:
                pass
            return response
        return web.Response(status=state["status"], body=state["body"])

    app = web.Application()
    app.router.add_post("/text2img/generate", generate)
    app.router.add_post("/private-key/text2img/generate", generate)
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
    assert "Chromium not ready" not in str(caught.value)
    assert "服务日志" in str(caught.value)
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
    assert attempts[0 if custom_first else 1]["render_service"][
        "configured_endpoint"
    ] == endpoint.removesuffix("/text2img")


@pytest.mark.asyncio
@pytest.mark.parametrize("marker", [{"render_service": "custom"}, {"__template_key": "custom"}])
async def test_custom_service_does_not_require_host_callback(rendering, service, marker):
    manager, generator, _png = rendering
    endpoint, _state, messages, _started = service
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {**marker, "service_endpoint": endpoint}
    ]
    assert (
        await generator.generate_image_report(create_analysis_result(), "123", None)
    )[0]
    assert len(messages) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"\x89PNG\r\n\x1a\ninvalid", b"\xff\xd8invalid"])
async def test_corrupt_image_signatures_are_rejected(service, body):
    endpoint, state, _, _ = service
    state["body"] = body
    with pytest.raises(ValueError, match="损坏"):
        await render_custom_t2i(endpoint, "html", {})


@pytest.mark.asyncio
async def test_valid_jpeg_is_decoded_and_truncated_jpeg_is_rejected(service):
    endpoint, state, _, _ = service
    output = BytesIO()
    Image.new("RGB", (32, 32)).save(output, "JPEG")
    state["body"] = output.getvalue()
    assert await render_custom_t2i(endpoint, "html", {}) == state["body"]
    state["body"] = state["body"][:-10]
    with pytest.raises(ValueError, match="损坏"):
        await render_custom_t2i(endpoint, "html", {})


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_declared_and_chunked_images_are_bounded(service, monkeypatch, stream):
    endpoint, state, _, _ = service
    monkeypatch.setattr(
        "src.infrastructure.reporting.custom_t2i_client._MAX_RESPONSE_BYTES", 65536
    )
    body = b"\x89PNG\r\n\x1a\n" + b"x" * 131072
    state.update(body=[body[:32768], body[32768:]] if stream else body, stream=stream)
    with pytest.raises(ValueError, match="32 MiB"):
        await render_custom_t2i(endpoint, "html", {})


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 503])
async def test_escaped_and_partial_token_body_is_not_exposed(service, status):
    endpoint, state, _, _ = service
    # 既覆盖 JSON 转义，也覆盖截取样本时只剩 Token 一部分的情况。
    state.update(
        status=status, body=(b'{"message":"\\u0073ecret' + b"x" * 4080 + b"secret")
    )
    with pytest.raises((ValueError, RuntimeError)) as caught:
        await render_custom_t2i(endpoint, "html", {}, "secret")
    assert "u0073" not in str(caught.value)
    assert "xxxx" not in str(caught.value)


@pytest.mark.asyncio
async def test_unauthenticated_error_keeps_useful_diagnosis(service):
    endpoint, state, _, _ = service
    state.update(status=503, body=b'{"message":"Chromium not ready"}')
    with pytest.raises(RuntimeError, match="Chromium not ready"):
        await render_custom_t2i(endpoint, "html", {})


@pytest.mark.asyncio
async def test_cancelled_custom_attempt_is_recorded_once_and_releases_queue(
    rendering, service, monkeypatch
):
    manager, generator, _ = rendering
    endpoint, state, _, started = service
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {
            "render_service": "custom",
            "service_endpoint": endpoint,
            "service_token": "secret",
        }
    ]
    state["delay"] = 0.1
    trace = TraceContext(trace_id="cancel-custom")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    with trace.span("RENDER_REPORT") as span:
        task = asyncio.create_task(
            generator.generate_image_report(create_analysis_result(), "123", None)
        )
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    attempts = span["payload"]["render_attempts"]
    assert len(attempts) == 1
    assert attempts[0]["status"] == "cancelled"
    assert attempts[0]["duration_ms"] >= 0
    state["delay"] = 0
    assert (
        await asyncio.wait_for(
            generator.generate_image_report(create_analysis_result(), "123", None), 2
        )
    )[0]


@pytest.mark.asyncio
async def test_custom_path_is_used_but_not_recorded_in_trace(
    rendering, service, monkeypatch
):
    manager, generator, _ = rendering
    endpoint, _, messages, _ = service
    origin = endpoint.removesuffix("/text2img")
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {
            "render_service": "custom",
            "service_endpoint": origin + "/private-key/text2img",
        }
    ]
    trace = TraceContext(trace_id="private-path")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    with trace.span("RENDER_REPORT") as span:
        assert (
            await generator.generate_image_report(create_analysis_result(), "123", None)
        )[0]
    assert messages[0]["path"] == "/private-key/text2img/generate"
    assert "private-key" not in json.dumps(span)
    assert (
        span["payload"]["render_attempts"][0]["render_service"]["configured_endpoint"]
        == origin
    )


@pytest.mark.asyncio
async def test_dispatcher_reaches_custom_generator_without_host_callback(rendering):
    manager, generator, _ = rendering
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"render_service": "custom", "service_endpoint": "http://127.0.0.1:8999"}
    ]
    generator.generate_image_report = AsyncMock(return_value=(None, None))
    dispatcher = ReportDispatcher(manager, generator, MagicMock())
    dispatcher._dispatch_text = AsyncMock(return_value=True)
    await dispatcher._dispatch_image("123", create_analysis_result(), "bot")
    generator.generate_image_report.assert_awaited_once()
    assert generator.generate_image_report.await_args.args[2] is None


@pytest.mark.asyncio
async def test_pixel_limit_is_checked_before_accepting_image(service, monkeypatch):
    endpoint, state, _, _ = service
    output = BytesIO()
    Image.new("RGB", (16, 16)).save(output, "PNG")
    state["body"] = output.getvalue()
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 200)
    with pytest.raises(ValueError, match="过大"):
        await render_custom_t2i(endpoint, "html", {})


@pytest.mark.asyncio
async def test_cancelled_environment_preparation_records_current_attempt(
    rendering, monkeypatch
):
    _, generator, _ = rendering
    entered = asyncio.Event()
    real_prepare = generator._prepare_render_data

    async def prepare(*args, **kwargs):
        if kwargs.get("environment") == "Overseas":
            entered.set()
            await asyncio.Event().wait()
        return await real_prepare(*args, **kwargs)

    monkeypatch.setattr(generator, "_prepare_render_data", prepare)
    trace = TraceContext(trace_id="cancel-prepare")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    callback = AsyncMock(return_value=None)
    with trace.span("RENDER_REPORT") as span:
        task = asyncio.create_task(
            generator.generate_image_report(create_analysis_result(), "123", callback)
        )
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert [item["status"] for item in span["payload"]["render_attempts"]] == [
        "failed",
        "cancelled",
    ]
    callback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("corrupt", [b"\x89PNG\r\n\x1a\ninvalid", b"\xff\xd8invalid"])
async def test_corrupt_custom_image_falls_back_to_host(
    rendering, service, monkeypatch, corrupt
):
    manager, generator, png = rendering
    endpoint, state, _, _ = service
    state["body"] = corrupt
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"priority": 10, "render_service": "custom", "service_endpoint": endpoint},
        {"priority": 20, "render_service": "astrbot"},
    ]
    trace = TraceContext(trace_id="corrupt-fallback")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    host = AsyncMock(return_value=png)
    with trace.span("RENDER_REPORT") as span:
        assert (
            await generator.generate_image_report(create_analysis_result(), "123", host)
        )[0]
    host.assert_awaited_once()
    attempts = span["payload"]["render_attempts"]
    assert [item["status"] for item in attempts] == ["failed", "success"]
    assert "损坏" in attempts[0]["error"]
