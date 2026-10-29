"""多次渲染时的诊断记录归属回归。"""

from unittest.mock import AsyncMock

import pytest
from test_rendering_strategies import rendering as rendering
from test_template_section_conditional_rendering import create_analysis_result

from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
async def test_render_attempts_and_success_update_only_latest_render_span(rendering, monkeypatch):
    _manager, generator, png = rendering
    trace = TraceContext(trace_id="two-renders")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    with trace.span("RENDER_REPORT") as previous:
        previous["payload"]["sentinel"] = "前一次渲染"
    callback = AsyncMock(side_effect=[None, png])
    with trace.span("RENDER_REPORT") as current:
        image, _ = await generator.generate_image_report(create_analysis_result(), "123", callback)
    assert image
    assert "render_attempts" not in previous["payload"]
    assert "image_bytes" not in previous["payload"]
    assert [item["status"] for item in current["payload"]["render_attempts"]] == ["failed", "success"]
    assert current["payload"]["image_bytes"] == len(png)
    assert current["payload"]["render_attempt"] == 2
