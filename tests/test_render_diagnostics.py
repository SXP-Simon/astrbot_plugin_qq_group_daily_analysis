"""验证渲染失败原因在日志和任务详情中保持一致。"""

import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from src.infrastructure.reporting import generators
from src.infrastructure.reporting.generators import ReportGenerator
from src.infrastructure.reporting.html_renderer import bind_group_html_renderer
from src.infrastructure.reporting.render_diagnostics import (
    diagnose_non_image_payload,
    summarize_render_error,
)
from src.shared.trace_context import TraceContext


@pytest.mark.parametrize(
    "payload,expected",
    [
        (b"", "空内容"),
        (b"\x00\x01\xff", "无法识别"),
        (b'{"detail": "Timeout"}', "JSON内容，未得到图片：Timeout"),
        (b'{"error": {"reason": "failed"}}', "reason"),
        (
            b"<html><title>Bad Gateway</title></html>",
            "网页内容，未得到图片：Bad Gateway",
        ),
        (b"<html><body>private page content</body></html>", "网页内容，未得到图片。"),
        (b"Internal Server Error", "文字内容，未得到图片：Internal Server Error"),
        (b"Gateway Timeout", "文字内容，未得到图片：Gateway Timeout"),
        (b"TimeoutError", "文字内容，未得到图片：TimeoutError"),
    ],
)
def test_response_diagnosis_only_reports_available_evidence(payload, expected):
    """响应正文不能用来断言 HTTP 状态码、CDN 或浏览器故障。"""
    result = diagnose_non_image_payload(payload)
    assert expected in result
    evidence = result.split("\n排查建议：", 1)[0]
    for unsupported in (
        "HTTP 500",
        "HTTP 502",
        "HTTP 504",
        "CDN",
        "Playwright",
        "private page content",
    ):
        assert unsupported not in evidence


@pytest.mark.parametrize(
    "payload,expected_hint",
    [
        (b"<html><title>Bad Gateway</title></html>", "反向代理"),
        (b'{"detail":"gateway timeout"}', "反向代理"),
        (b"Internal Server Error", "如果日志提到"),
        (b'{"error":"TimeoutError"}', "如果日志显示页面资源加载超时"),
        (b"Request timed out", "渲染服务所在环境"),
        ('{"message":"渲染超时"}'.encode(), "确认资源可达后"),
    ],
)
def test_specific_hints_are_separate_from_reported_error(payload, expected_hint):
    """特定错误保留排查方向，但不把建议写成已经确认的原因。"""
    evidence, hint = diagnose_non_image_payload(payload).split("\n排查建议：")
    assert "未得到图片" in evidence
    assert expected_hint in hint
    assert "HTTP 500" not in evidence
    assert "HTTP 502" not in evidence
    assert "HTTP 504" not in evidence


@pytest.mark.parametrize(
    "payload", [b"unknown error", b"", b"\x00\xff", b'{"error":"failed"}']
)
def test_unknown_response_does_not_get_a_speculative_hint(payload):
    """缺少明确线索时不套用特定故障的建议。"""
    assert "排查建议" not in diagnose_non_image_payload(payload)


@pytest.mark.parametrize(
    "message,secret",
    [
        ("failed https://user:pass@host/path?token=abc", "user:pass"),
        ('{"token": "private-value"}', "private-value"),
        ("Authorization: Bearer private-value", "private-value"),
        ("password=private-value", "private-value"),
        ("api_key='private-value'", "private-value"),
    ],
)
def test_error_summary_masks_credentials(message, secret):
    """常见地址凭据和认证字段不出现在摘要中。"""
    summary = summarize_render_error(message)
    assert secret not in summary
    assert "已隐藏" in summary


def test_summary_limits_length_and_flattens_lines():
    """长响应不会淹没日志和任务详情。"""
    result = diagnose_non_image_payload(b'{"detail":"' + b"x" * 1000 + b'"}')
    assert len(result) < 350
    assert result.endswith("…")
    assert summarize_render_error("first\n\tsecond") == "first second"


@pytest.fixture
def render_setup(monkeypatch):
    """隔离模板准备与网络调用，只执行真实的渲染重试和诊断逻辑。"""
    generator = object.__new__(ReportGenerator)
    generator.config_manager = MagicMock()
    generator.config_manager.get_report_template.return_value = "scrapbook"
    generator.config_manager.get_t2i_rendering_strategies.return_value = [
        {"type": "jpeg", "full_page": True},
        {"type": "png", "full_page": True},
    ]
    generator.html_templates = MagicMock()
    generator.html_templates.render_template.return_value = "<html>report</html>"
    generator._prepare_render_data = AsyncMock(return_value={})
    generator._render_semaphore = asyncio.Semaphore(1)
    log = MagicMock()
    monkeypatch.setattr(generators, "logger", log)
    return generator, log


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        "html",
        "json",
        "empty",
        "empty_bytes",
        "empty_path",
        "unexpected",
        "empty_file",
        "missing",
        "unreadable",
        "timeout",
        "exception",
    ],
)
async def test_failed_attempts_preserve_reason_and_duration(
    render_setup, tmp_path, monkeypatch, kind
):
    """失败原因同时进入每次尝试、最终日志及 Trace，且耗时不会丢失。"""
    generator, log = render_setup
    path = tmp_path / "response.png"
    if kind == "html":
        path.write_bytes(b"<html><title>Bad Gateway</title></html>")
        response, expected = str(path), "Bad Gateway"
    elif kind == "json":
        response, expected = b'{"detail":"render failed"}', "render failed"
    elif kind == "empty":
        response, expected = None, "返回了 None"
    elif kind == "empty_bytes":
        response, expected = b"", "空字节数据"
    elif kind == "empty_path":
        response, expected = "", "空文件路径"
    elif kind == "unexpected":
        response, expected = {"error": "private response"}, "不支持的数据类型：dict"
    elif kind == "empty_file":
        path.write_bytes(b"")
        response, expected = str(path), "图片文件为空"
    elif kind == "missing":
        response, expected = str(path), "文件不存在"
    elif kind == "unreadable":
        response, expected = str(path), "无法读取"
        monkeypatch.setattr(
            Path, "open", MagicMock(side_effect=PermissionError("denied"))
        )
    elif kind == "timeout":
        response, expected = TimeoutError(), "TimeoutError：请求超时"
    else:
        response, expected = RuntimeError(), "RuntimeError：未提供具体原因"
    callback = AsyncMock(side_effect=[response, response])
    with (
        TraceContext(group_id="123", trigger_type="manual") as trace,
        trace.span("RENDER_REPORT"),
    ):
        result = await generator.generate_image_report({}, "123", callback)
    assert result == (None, "<html>report</html>")
    attempts = trace._spans[0]["payload"]["render_attempts"]
    assert len(attempts) == 2
    for index, attempt in enumerate(attempts, 1):
        assert expected in attempt["error"]
        assert attempt["duration_ms"] >= 0
        assert attempt["attempt"] == index
        assert attempt["status"] == "failed"
        assert attempt["error"] in log.warning.call_args_list[index - 1].args[0]
    assert attempts[-1]["error"] in log.error.call_args.args[0]
    assert "最后一个错误: None" not in log.error.call_args.args[0]
    assert "private response" not in log.error.call_args.args[0]
    assert callback.await_count == 2
    assert attempts[-1]["return_type"] == (
        "未返回" if isinstance(response, Exception) else type(response).__name__
    )
    if kind in ("empty_file", "empty_bytes"):
        assert attempts[-1]["returned_bytes"] == 0
    if kind == "missing":
        assert attempts[-1]["file_exists"] is False
    assert "render_service" in trace._spans[0]["payload"]
    # 宿主未暴露 HTTP 等待预算，不能用截图参数代替。
    assert all(attempt["request_timeout_ms"] is None for attempt in attempts)
    assert any("[T2I诊断 v2]" in call.args[0] for call in log.debug.call_args_list)
    log.info.assert_not_called()
    if isinstance(response, Exception):
        assert log.debug.call_args.kwargs["exc_info"] is True
    if kind in ("html", "timeout"):
        assert "\n排查建议：" in attempts[-1]["error"]
    elif kind == "exception":
        assert "排查建议" not in attempts[-1]["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("as_file", [False, True])
async def test_retry_can_still_succeed(render_setup, tmp_path, as_file):
    """首轮失败后仍能返回有效图片，不产生最终失败日志。"""
    generator, log = render_setup
    buffer = BytesIO()
    Image.new("RGB", (1, 1)).save(buffer, format="PNG")
    image = buffer.getvalue()
    if as_file:
        path = tmp_path / "image.png"
        path.write_bytes(image)
        image = str(path)
    callback = AsyncMock(side_effect=[b'{"detail":"temporary failure"}', image])
    with (
        TraceContext(group_id="123", trigger_type="manual") as trace,
        trace.span("RENDER_REPORT"),
    ):
        result, _ = await generator.generate_image_report({}, "123", callback)
    assert result == image if as_file else result.startswith("base64://")
    attempts = trace._spans[0]["payload"]["render_attempts"]
    assert [attempt["status"] for attempt in attempts] == ["failed", "success"]
    assert "temporary failure" in attempts[0]["error"]
    log.error.assert_not_called()
    log.info.assert_called_once()
    assert "图片生成成功" in log.info.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("config_error", [False, True])
async def test_service_diagnostics_are_logged_without_blocking_render(
    render_setup, config_error
):
    """地址进入日志和任务详情，诊断查询失败也不会阻断原渲染调用。"""
    generator, log = render_setup
    calls = []

    class Host:
        context = SimpleNamespace(
            get_config=MagicMock(
                return_value={
                    "t2i_endpoint": "http://user:secret@t2i:8999/text2img?token=private",
                }
            )
        )

        async def html_render(
            self, tmpl, data, return_url=True, options=None, umo=None
        ):
            calls.append(umo)

    host = Host()
    if config_error:
        host.context.get_config.side_effect = RuntimeError("private config")
    callback = bind_group_html_renderer(host.html_render, "123", "bot-a")
    with (
        TraceContext(group_id="123", trigger_type="manual") as trace,
        trace.span("RENDER_REPORT"),
    ):
        await generator.generate_image_report({}, "123", callback)
    assert calls == ["bot-a:GroupMessage:123"] * 2
    service = trace._spans[0]["payload"]["render_service"]
    expected = "RuntimeError" if config_error else "http://t2i:8999/text2img"
    assert expected in service["configured_endpoint"]
    logged = "\n".join(call.args[0] for call in log.debug.call_args_list)
    assert expected in logged
    assert "secret" not in logged and "private" not in logged
    log.info.assert_not_called()
    log.error.assert_called_once()
    assert expected in log.error.call_args.args[0]
    assert "secret" not in log.error.call_args.args[0]
    assert "private" not in log.error.call_args.args[0]


@pytest.mark.asyncio
async def test_cancellation_is_not_retried(render_setup):
    """取消任务继续向上传播，不被当作普通失败吞掉。"""
    generator, log = render_setup
    callback = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await generator.generate_image_report({}, "123", callback)
    callback.assert_awaited_once()
    log.warning.assert_not_called()
