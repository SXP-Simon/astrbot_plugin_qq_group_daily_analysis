from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from test_template_section_conditional_rendering import create_analysis_result

from src.application.services.template_command_service import TemplateCommandService
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting.render_data_preparer import RenderDataPreparer
from src.infrastructure.reporting.templates import HTMLTemplates
from src.shared.constants import DEFAULT_ATRI_ASSETS_CDN_URL, DEFAULT_CDN_HOST


@pytest.fixture
def config_manager():
    config = object.__new__(ConfigManager)
    config.config = {}
    return config


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, DEFAULT_CDN_HOST),
        (123, DEFAULT_CDN_HOST),
        ("", DEFAULT_CDN_HOST),
        ("  \t", DEFAULT_CDN_HOST),
        (" https://fastly.jsdelivr.net/ \u00a0", "https://fastly.jsdelivr.net"),
        ("https://fastly.jsdelivr.net", "https://fastly.jsdelivr.net"),
        ("https://mirror.example.com///", "https://mirror.example.com"),
        ("http://localhost:8080/", "http://localhost:8080"),
        ("fastly.jsdelivr.net", DEFAULT_CDN_HOST),
        ("https://mirror.example.com/gh/owner/repo", DEFAULT_CDN_HOST),
        ("https://mirror.example.com?query=1", DEFAULT_CDN_HOST),
        ("https://mirror.example.com#fragment", DEFAULT_CDN_HOST),
        ("https://mirror.example.com?", DEFAULT_CDN_HOST),
        ("https://user:password@mirror.example.com", DEFAULT_CDN_HOST),
        ("file:///tmp/assets", DEFAULT_CDN_HOST),
        ("https://[invalid", DEFAULT_CDN_HOST),
    ],
)
def test_cdn_root_normalization(config_manager, value, expected):
    config_manager.config = {"t2i_rendering": {"t2i_rendering_strategies": [{"cdn_base_url": value}]}}
    assert config_manager.get_t2i_cdn_base_url() == expected
    assert config_manager.get_template_assets_base_url().startswith(expected + "/gh/")


@pytest.mark.parametrize("group", [None, 123, "broken", [], False])
def test_malformed_rendering_group_uses_defaults_without_mutation(
    config_manager, group
):
    config_manager.config = {"t2i_rendering": group}
    assert config_manager.get_t2i_cdn_base_url() == DEFAULT_CDN_HOST
    assert config_manager.get_template_assets_base_url().startswith(
        DEFAULT_CDN_HOST + "/gh/"
    )
    assert config_manager.get_t2i_atri_font_mirror().endswith("/ATRI")
    assert config_manager.get_t2i_font_source() == "Overseas"
    assert (
        config_manager.get_t2i_google_fonts_mirror() == "https://fonts.googleapis.com"
    )
    assert config_manager.get_t2i_gstatic_mirror() == "https://fonts.gstatic.com"
    assert config_manager.config["t2i_rendering"] is group


@pytest.mark.parametrize("legacy_mirror", [None, "", DEFAULT_ATRI_ASSETS_CDN_URL])
def test_atri_default_follows_cdn_but_custom_override_is_preserved(
    config_manager, legacy_mirror
):
    assert config_manager.get_t2i_cdn_base_url() == DEFAULT_CDN_HOST
    group = {"t2i_rendering_strategies": [{"cdn_base_url": "https://fastly.jsdelivr.net/"}]}
    if legacy_mirror is not None:
        group["t2i_atri_font_mirror"] = legacy_mirror
    config_manager.config = {"t2i_rendering": group}
    assert config_manager.get_t2i_atri_font_mirror() == (
        config_manager.get_template_assets_base_url() + "/ATRI"
    )
    group["t2i_atri_font_mirror"] = "https://custom.example.com/ATRI/"
    assert (
        config_manager.get_t2i_atri_font_mirror() == "https://custom.example.com/ATRI"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ["HatsuneMiku", "ATRI", "deepseek_maid", "maria"])
async def test_cdn_used_by_main_and_component_templates(config_manager, theme):
    config_manager.config = {
        "basic": {"report_template": theme},
        "t2i_rendering": {"t2i_rendering_strategies": [{"cdn_base_url": "https://fastly.jsdelivr.net/"}]},
    }
    templates = MagicMock(wraps=HTMLTemplates(config_manager))
    avatars = MagicMock()
    avatars.get_user_avatar = AsyncMock(return_value="")
    visualizer = MagicMock()
    visualizer.get_hourly_chart_data.return_value = []
    preparer = RenderDataPreparer(config_manager, avatars, templates, visualizer)

    render_data = await preparer.prepare_render_data(
        create_analysis_result(), template_theme=theme
    )
    assets = config_manager.get_template_assets_base_url()
    expected = {
        "cdn_assets_base": assets,
        "t2i_atri_font_mirror": f"{assets}/ATRI",
        "t2i_miku_assets_mirror": f"{assets}/HatsuneMiku",
        "t2i_deepseek_maid_assets_mirror": f"{assets}/deepseek_maid",
        "t2i_maria_assets_mirror": f"{assets}/maria",
        "t2i_npm_mirror": "https://fastly.jsdelivr.net/npm",
    }
    assert templates.render_template.call_count >= 4
    for key, value in expected.items():
        assert render_data[key] == value
        assert all(
            call.kwargs[key] == value
            for call in templates.render_template.call_args_list
        )
    for template_file in ("image_template.html", "html_template.html"):
        rendered = templates.render_template(
            template_file, template_theme=theme, **render_data
        )
        assert rendered
        assert DEFAULT_CDN_HOST not in rendered


def test_preview_fallback_reads_current_cdn_configuration(
    config_manager, tmp_path: Path
):
    service = TemplateCommandService(str(tmp_path), config_provider=config_manager)
    with (
        patch.object(service, "resolve_template_preview_path", return_value=None),
        patch(
            "src.application.services.template_command_service.Image.fromURL"
        ) as from_url,
    ):
        for host in ("https://fastly.jsdelivr.net/", "https://mirror.example.com/"):
            config_manager.config = {"t2i_rendering": {"t2i_rendering_strategies": [{"cdn_base_url": host}]}}
            service.build_template_preview_nodes(["HatsuneMiku"], "HatsuneMiku", "123")
            from_url.assert_called_with(
                config_manager.get_template_assets_base_url() + "/HatsuneMiku-demo.jpg"
            )
