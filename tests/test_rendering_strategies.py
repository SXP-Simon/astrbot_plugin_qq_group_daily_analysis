"""渲染方案优先级、资源隔离及 HTML 导出的集成回归。"""

import asyncio
import json
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image
from test_template_section_conditional_rendering import create_analysis_result

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting.generators import ReportGenerator
from src.infrastructure.reporting.render_data_preparer import RenderDataPreparer
from src.shared.trace_context import TraceContext


def make_rendering_plan(environment, **options):
    suffix = environment.lower()
    return {"environment": environment, "cdn_base_url": f"https://{suffix}.example", "google_fonts": f"https://fonts-{suffix}.example", "gstatic": f"https://static-{suffix}.example", **options}


@pytest.fixture
def rendering(tmp_path, monkeypatch):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    manager = object.__new__(ConfigManager)
    manager.config = {
        "basic": {"report_template": "HatsuneMiku", "profile_display_mode": "sbti"},
        "t2i_rendering": {
            "t2i_rendering_strategies": [
                make_rendering_plan("Mainland", name="最终尝试", priority=30),
                make_rendering_plan("Overseas", name="海外回退", priority=20),
                make_rendering_plan("Mainland", name="内地优先", priority=10),
            ],
        },
    }
    generator = ReportGenerator(manager, tmp_path)
    avatars = MagicMock()
    avatars.get_user_avatar = AsyncMock(return_value="")
    visualizer = MagicMock()
    visualizer.get_hourly_chart_data.return_value = []
    generator._preparer_service = RenderDataPreparer(
        manager,
        avatars,
        generator.html_templates,
        visualizer,
        generator._profile_asset_manifest,
    )
    buffer = BytesIO()
    Image.new("RGB", (2, 2)).save(buffer, format="PNG")
    return manager, generator, buffer.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("succeeds", [True, False])
async def test_default_tries_overseas_then_mainland_only_on_failure(
    rendering, succeeds
):
    manager, generator, png = rendering
    manager.config["t2i_rendering"].pop("t2i_rendering_strategies")
    render = AsyncMock(return_value=png if succeeds else None)
    image, html = await generator.generate_image_report(
        create_analysis_result(), "123", render
    )
    assert render.await_count == (1 if succeeds else 2)
    assert bool(image) is succeeds
    assert html == render.await_args.args[0]
    assert "https://cdn.jsdmirror.com/gh/" in html
    assert "https://fonts.googleapis.com" in render.await_args_list[0].args[0]
    if not succeeds:
        assert "https://fonts.loli.net" in render.await_args_list[1].args[0]
    assert all(call.args[3]["timeout"] == 20000 for call in render.await_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "empty", "non_image"])
async def test_fallback_rebuilds_resources_and_returns_matching_html(
    rendering, failure
):
    manager, generator, png = rendering
    original = deepcopy(manager.config)
    calls = []

    async def render(html, _data, _return_url, options):
        calls.append((html, deepcopy(options)))
        if len(calls) == 1:
            if failure == "timeout":
                raise TimeoutError("页面资源加载超时")
            return None if failure == "empty" else b"<html>502 Bad Gateway</html>"
        return png

    image, returned_html = await generator.generate_image_report(
        create_analysis_result(),
        "123",
        render,
    )
    assert image.startswith("base64://")
    assert len(calls) == 2
    for (html, options), location in zip(calls, ("mainland", "overseas"), strict=True):
        assert f"https://{location}.example/gh/" in html
        assert f"https://fonts-{location}.example" in html
        assert f"https://static-{location}.example" in html
        assert f"https://{location}.example/gh/SXP-Simon/profile_assets" in html
        assert "resource_environment" not in options
        assert "environment" not in options
        assert "priority" not in options
    assert returned_html == calls[-1][0]
    assert manager.config == original


@pytest.mark.asyncio
async def test_priority_and_three_attempts_keep_input_order_unchanged(rendering):
    manager, generator, _png = rendering
    original = deepcopy(manager.config)
    seen = []

    async def render(html, *_args):
        seen.append("Mainland" if "fonts-mainland.example" in html else "Overseas")
        return

    image, html = await generator.generate_image_report(
        create_analysis_result(), "123", render
    )
    assert image is None
    assert seen == ["Mainland", "Overseas", "Mainland"]
    assert "fonts-mainland.example" in html
    assert manager.config == original


@pytest.mark.asyncio
async def test_success_and_cancellation_do_not_start_later_strategies(rendering):
    _manager, generator, png = rendering
    render = AsyncMock(return_value=png)
    assert (
        await generator.generate_image_report(create_analysis_result(), "123", render)
    )[0]
    render.assert_awaited_once()
    cancelled = AsyncMock(side_effect=asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        await generator.generate_image_report(
            create_analysis_result(), "123", cancelled
        )
    cancelled.assert_awaited_once()


@pytest.mark.asyncio
async def test_independent_html_uses_highest_priority_resources(rendering):
    manager, generator, _png = rendering
    original = deepcopy(manager.config)
    path, _sidecar = await generator.generate_html_report(
        create_analysis_result(), "123"
    )
    html = Path(path).read_text(encoding="utf-8")
    assert "https://mainland.example/gh/" in html
    assert "https://fonts-mainland.example" in html
    assert "https://overseas.example" not in html
    assert manager.config == original


@pytest.mark.asyncio
async def test_custom_profile_images_survive_environment_switch(rendering):
    manager, generator, png = rendering
    custom = "https://custom.example/portrait.png?version=1"
    manager.config["basic"]["profile_mapping_config"] = json.dumps(
        {
            "sbti": {"ENTP": {"image": custom}},
        }
    )
    seen = []

    async def render(html, *_args):
        seen.append(html)
        return None if len(seen) == 1 else png

    await generator.generate_image_report(create_analysis_result(), "123", render)
    assert len(seen) == 2
    assert all(custom in html for html in seen)


@pytest.mark.asyncio
async def test_switching_environment_does_not_affect_concurrent_report(rendering):
    manager, generator, png = rendering
    generator._render_semaphore = asyncio.Semaphore(2)
    original = deepcopy(manager.config)
    fallback_started, release = asyncio.Event(), asyncio.Event()
    first_calls = []

    async def first_render(html, *_args):
        first_calls.append(html)
        if len(first_calls) == 1:
            return None
        fallback_started.set()
        await release.wait()
        return png

    first = asyncio.create_task(
        generator.generate_image_report(create_analysis_result(), "123", first_render)
    )
    try:
        await asyncio.wait_for(fallback_started.wait(), timeout=1)
        assert manager.config == original
        second_render = AsyncMock(return_value=png)
        await asyncio.wait_for(
            generator.generate_image_report(
                create_analysis_result(), "456", second_render
            ),
            timeout=1,
        )
        second_html = second_render.await_args.args[0]
        assert "https://mainland.example/gh/" in second_html
        assert "https://overseas.example" not in second_html
        release.set()
        assert (await asyncio.wait_for(first, timeout=1))[0]
    finally:
        release.set()
        if not first.done():
            first.cancel()
        await asyncio.gather(first, return_exceptions=True)


@pytest.mark.asyncio
async def test_trace_records_each_attempt_environment(rendering, monkeypatch):
    _manager, generator, png = rendering
    trace = TraceContext(trace_id="strategy-test")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    render = AsyncMock(side_effect=[None, png])
    with trace.span("RENDER_REPORT") as span:
        await generator.generate_image_report(
            create_analysis_result(),
            "123",
            render,
            template_theme="HatsuneMiku",
        )
    attempts = span["payload"]["render_attempts"]
    assert [item["resource_environment"] for item in attempts] == [
        "Mainland",
        "Overseas",
    ]
    assert [item["status"] for item in attempts] == ["failed", "success"]
