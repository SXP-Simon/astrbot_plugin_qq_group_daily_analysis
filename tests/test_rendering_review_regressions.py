"""渲染配置变更、回退事务性与总等待上限的回归测试。"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from test_rendering_strategies import rendering as rendering
from test_template_section_conditional_rendering import create_analysis_result

from src.infrastructure.reporting import generators
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
async def test_config_change_during_preparation_only_affects_next_report(rendering):
    manager, generator, png = rendering
    started, release = asyncio.Event(), asyncio.Event()

    async def avatar(*_args):
        started.set()
        await release.wait()
        return ""

    generator._preparer_service.avatar_service.get_user_avatar = AsyncMock(
        side_effect=avatar
    )
    render = AsyncMock(return_value=png)
    task = asyncio.create_task(
        generator.generate_image_report(create_analysis_result(), "123", render)
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        config = manager.config["t2i_rendering"]
        config["t2i_rendering_strategies"] = [
            {"environment": "Overseas", "type": "jpeg", "timeout": 12345}
        ]
        config["t2i_mainland_cdn_base_url"] = "https://changed-mainland.example"
        config["t2i_mainland_google_fonts"] = "https://changed-fonts.example"
        release.set()
        assert (await asyncio.wait_for(task, timeout=1))[0]
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    render.assert_awaited_once()
    first_html, _, _, options = render.await_args.args
    assert "https://mainland.example/gh/" in first_html
    assert "https://fonts-mainland.example" in first_html
    assert "changed-mainland.example" not in first_html
    assert options["type"] == "png"
    assert options["timeout"] == 20000
    await generator.generate_image_report(create_analysis_result(), "123", render)
    assert "https://overseas.example/gh/" in render.await_args.args[0]
    assert render.await_args.args[3]["type"] == "jpeg"
    assert render.await_args.args[3]["timeout"] == 12345


@pytest.mark.asyncio
@pytest.mark.parametrize("succeeds", [True, False])
async def test_empty_switched_template_keeps_previous_valid_html(
    rendering, monkeypatch, succeeds
):
    _manager, generator, png = rendering
    real_render = generator._render_prepared_html

    def render_template(template_file, theme, payload):
        if payload["t2i_font_source"] == "Overseas":
            return ""
        return real_render(template_file, theme, payload)

    monkeypatch.setattr(generator, "_render_prepared_html", render_template)
    render = AsyncMock(side_effect=[None, png if succeeds else None])
    image, html = await generator.generate_image_report(
        create_analysis_result(), "123", render
    )
    assert render.await_count == 2
    first_html = render.await_args_list[0].args[0]
    assert first_html
    assert render.await_args_list[1].args[0] == first_html
    assert html == first_html
    assert bool(image) is succeeds


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_at", ["renderer", "fallback_preparation"])
async def test_total_deadline_cancels_waits_and_releases_queue(
    rendering, monkeypatch, blocked_at
):
    _manager, generator, _png = rendering
    monkeypatch.setattr(generators, "_RENDER_TOTAL_TIMEOUT_SECONDS", 0.05)
    trace = TraceContext(trace_id="render-deadline")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    cancelled = asyncio.Event()

    async def block():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    real_prepare = generator._prepare_render_data

    async def prepare(*args, **kwargs):
        if kwargs.get("environment") == "Overseas":
            await block()
        return await real_prepare(*args, **kwargs)

    async def render(*_args):
        if blocked_at == "renderer":
            await block()
        return

    if blocked_at == "fallback_preparation":
        monkeypatch.setattr(generator, "_prepare_render_data", prepare)
    callback = AsyncMock(side_effect=render)
    with trace.span("RENDER_REPORT") as span:
        image, html = await asyncio.wait_for(
            generator.generate_image_report(create_analysis_result(), "123", callback),
            timeout=1,
        )
    assert image is None
    assert html
    assert cancelled.is_set()
    assert callback.await_count == 1
    attempts = span["payload"]["render_attempts"]
    assert len(attempts) == (1 if blocked_at == "renderer" else 2)
    assert "总等待上限" in attempts[-1]["error"]
    await asyncio.wait_for(generator._render_semaphore.acquire(), timeout=0.1)
    generator._render_semaphore.release()
