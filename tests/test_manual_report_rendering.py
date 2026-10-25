"""手动报告在有无追踪上下文时的渲染行为。"""

from types import SimpleNamespace

import pytest
from test_frontend_stop import HostEvent, StubTaskManager, make_handler
from test_frontend_stop_delivery import DeliveryAdapter, OutputConfig

from src.application.handlers.analysis_command_handler import AnalysisStoppedError
from src.shared import trace_context
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["image", "html"])
@pytest.mark.parametrize("with_trace", [True, False])
@pytest.mark.parametrize("outcome", ["normal", "error", "stop"])
async def test_render_once_with_optional_trace(output, with_trace, outcome, monkeypatch):
    trace = TraceContext(trace_id="render_test") if with_trace else None
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(trace_context, "_active_traces", {})
    calls = []
    error = ValueError("渲染失败") if outcome == "error" else AnalysisStoppedError()

    async def render(*args, **kwargs):
        calls.append((args, kwargs))
        if trace is not None:
            assert len(trace._spans) == 1
            assert trace._spans[0]["status"] == "running"
            assert trace._spans[0]["payload"]["format"] == output
        if outcome != "normal":
            raise error
        return None, None

    generator = SimpleNamespace(
        generate_image_report=render,
        generate_html_report=render,
        generate_text_report=lambda _: "",
    )
    handler = make_handler(
        object(), StubTaskManager(), report_generator=generator, config=OutputConfig(output),
    )
    result = {
        "group_id": "123456", "platform_id": "bot-a",
        "analysis_result": {}, "adapter": DeliveryAdapter(),
    }
    if outcome == "normal":
        [item async for item in handler.send_analysis_report(HostEvent(), result)]
    else:
        with pytest.raises(type(error)) as captured:
            [item async for item in handler.send_analysis_report(HostEvent(), result)]
        assert captured.value is error

    assert len(calls) == 1
    assert calls[0][0][:2] == ({}, "123456")
    assert calls[0][1]["avatar_cache_namespace"] == "bot-a"
    assert calls[0][1]["template_theme"] == "default"
    if output == "html":
        assert calls[0][1]["trace_id"] == (trace.trace_id if trace else None)
    if trace is not None:
        assert trace._spans[0]["duration_ms"] is not None
        if outcome != "stop":
            assert trace._spans[0]["status"] == ("failed" if outcome == "error" else "success")
