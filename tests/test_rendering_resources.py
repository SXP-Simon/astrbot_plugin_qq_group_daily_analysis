"""同环境资源回退、HTML 导出与自定义图片保留。"""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from test_rendering_strategies import rendering as rendering
from test_template_section_conditional_rendering import create_analysis_result


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["cdn_base_url", "google_fonts", "gstatic"])
async def test_same_environment_rebuilds_html_when_any_resource_changes(
    rendering, changed
):
    manager, generator, png = rendering
    base = {
        "cdn_base_url": "https://one.example",
        "google_fonts": "https://fonts-one.example",
        "gstatic": "https://static-one.example",
    }
    second = {**base, changed: "https://two.example"}
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"priority": 10, **base},
        {"priority": 20, **second},
    ]
    before = deepcopy(manager.config)
    callback = AsyncMock(side_effect=[None, png])
    image, html = await generator.generate_image_report(
        create_analysis_result(), "123", callback
    )
    assert image
    assert callback.await_count == 2
    assert "https://two.example" not in callback.await_args_list[0].args[0]
    assert "https://two.example" in html == callback.await_args_list[1].args[0]
    assert manager.config == before
    for call in callback.await_args_list:
        assert not {
            "resource_urls",
            "cdn_base_url",
            "google_fonts",
            "gstatic",
        }.intersection(call.args[3])


@pytest.mark.asyncio
async def test_html_export_and_custom_images_use_first_round_resources(rendering):
    manager, generator, _ = rendering
    custom = "https://user.example/portrait.png?key=1"
    manager.config["basic"]["profile_mapping_config"] = json.dumps(
        {"sbti": {"ENTP": {"image": custom}}}
    )
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"priority": 20, "cdn_base_url": "https://later.example"},
        {
            "priority": 10,
            "cdn_base_url": "https://first.example",
            "google_fonts": "https://first.example/fonts",
            "gstatic": "https://first.example/static",
        },
    ]
    path, _ = await generator.generate_html_report(create_analysis_result(), "123")
    html = Path(path).read_text(encoding="utf-8")
    assert "https://first.example/gh/" in html
    assert "https://first.example/fonts" in html
    assert "https://first.example/static" in html
    assert "https://later.example" not in html
    assert custom in html


@pytest.mark.asyncio
async def test_round_snapshot_reaches_npm_and_atri_without_changing_custom_override(
    rendering,
):
    manager, generator, _ = rendering
    resources = {
        "cdn_base_url": "https://round.example",
        "google_fonts": "https://round.example/fonts",
        "gstatic": "https://round.example/static",
    }
    for override in (None, "https://custom.example/ATRI"):
        if override:
            manager.config["t2i_rendering"]["t2i_atri_font_mirror"] = override
        data = await generator._prepare_render_data(
            create_analysis_result(), resources=resources
        )
        assert data["t2i_npm_mirror"] == "https://round.example/npm"
        assert data["t2i_atri_font_mirror"] == (
            override or data["cdn_assets_base"] + "/ATRI"
        )
        assert data["t2i_google_fonts_mirror"] == resources["google_fonts"]
        assert data["t2i_gstatic_mirror"] == resources["gstatic"]
