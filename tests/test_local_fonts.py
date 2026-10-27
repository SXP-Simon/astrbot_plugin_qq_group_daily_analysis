"""自定义 T2I 字体模式：配置边界、内置模板及逐轮隔离。"""

from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from test_rendering_strategies import rendering as rendering
from test_template_section_conditional_rendering import create_analysis_result

from src.infrastructure.config.rendering_config import parse_rendering_strategies
from src.infrastructure.reporting import generators
from src.infrastructure.webui.routes import config_routes

THEMES = sorted(
    p.name
    for p in (
        Path(__file__).parents[1] / "src/infrastructure/reporting/templates"
    ).iterdir()
    if p.is_dir() and (p / "image_template.html").exists()
)


@pytest.mark.parametrize("mode", ["network", "local"])
def test_only_custom_plans_use_font_mode(mode):
    raw = [{"__template_key": "custom", "font_mode": mode}]
    before = deepcopy(raw)
    assert parse_rendering_strategies(raw)[0]["font_mode"] == mode
    assert raw == before
    assert (
        "font_mode"
        not in parse_rendering_strategies(
            [{"__template_key": "strategy", "font_mode": mode}]
        )[0]
    )
    assert (
        parse_rendering_strategies([{"__template_key": "custom"}])[0]["font_mode"]
        == "network"
    )


@pytest.mark.parametrize("mode", [None, "", "offline", True, 0, []])
def test_invalid_custom_font_modes_are_rejected(mode):
    with pytest.raises(ValueError, match="字体"):
        parse_rendering_strategies([{"__template_key": "custom", "font_mode": mode}])


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("mode", ["network", "local"])
async def test_builtin_templates_keep_assets_and_conditionally_load_fonts(
    rendering, monkeypatch, theme, mode
):
    manager, generator, png = rendering
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"__template_key": "custom", "font_mode": mode}
    ]
    render = AsyncMock(return_value=png)
    monkeypatch.setattr(generators, "render_custom_t2i", render)
    image, html = await generator.generate_image_report(
        create_analysis_result(), "123", template_theme=theme
    )
    assert image and html and "<body" in html
    assert "font_mode" not in render.await_args.args[2]
    assert "font-family" in html
    if mode == "local":
        assert "/css2?family=" not in html
        assert "fonts.googleapis.com" not in html and "fonts.gstatic.com" not in html
        assert "xcnahida.cn/fonts/" not in html
        assert ".woff2" not in html
    elif theme == "ATRI":
        assert "LXGWWenKai-Regular.woff2" in html
    elif theme == "BlueArchive":
        assert "xcnahida.cn/fonts/" in html
    else:
        assert "/css2?family=" in html
    if theme == "ATRI":
        assert "/ATRI/file/" in html and ".webp" in html
    if theme == "HatsuneMiku":
        assert "/HatsuneMiku/retouch_" in html
    if theme == "retro_futurism":
        assert 'local("Impact")' in html
    if theme == "BlueArchive" and mode == "local":
        assert 'local("BlueakaBeta2GBK DemiBold")' in html
        assert 'local("BlueakaBeta2GBK")' in html


@pytest.mark.asyncio
@pytest.mark.parametrize("modes", [("network", "local"), ("local", "network")])
async def test_same_resources_rebuild_when_only_font_mode_changes(
    rendering, monkeypatch, modes
):
    manager, generator, png = rendering
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"__template_key": "custom", "font_mode": mode, "priority": index}
        for index, mode in enumerate(modes)
    ]
    original = deepcopy(manager.config)
    render = AsyncMock(side_effect=[RuntimeError("尝试下一轮"), png])
    monkeypatch.setattr(generators, "render_custom_t2i", render)
    image, returned_html = await generator.generate_image_report(
        create_analysis_result(), "123"
    )
    assert image and render.await_count == 2
    for call, mode in zip(render.await_args_list, modes, strict=True):
        assert ("/css2?family=" in call.args[1]) is (mode == "network")
        assert "font_mode" not in call.args[2]
    assert returned_html == render.await_args.args[1]
    assert manager.config == original


@pytest.mark.asyncio
async def test_custom_local_failure_restores_host_online_fonts(rendering, monkeypatch):
    manager, generator, png = rendering
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"__template_key": "custom", "font_mode": "local", "priority": 10},
        {"__template_key": "strategy", "font_mode": "local", "priority": 20},
    ]
    custom = AsyncMock(side_effect=RuntimeError("服务不可用"))
    monkeypatch.setattr(generators, "render_custom_t2i", custom)
    host = AsyncMock(return_value=png)
    assert (
        await generator.generate_image_report(create_analysis_result(), "123", host)
    )[0]
    assert "/css2?family=" not in custom.await_args.args[1]
    assert "/css2?family=" in host.await_args.args[0]
    assert "font_mode" not in host.await_args.args[3]


@pytest.mark.asyncio
async def test_local_image_setting_keeps_html_export_online(rendering):
    manager, generator, _ = rendering
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"__template_key": "custom", "font_mode": "local"}
    ]
    path, _ = await generator.generate_html_report(create_analysis_result(), "123")
    assert "/css2?family=" in Path(path).read_text(encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["network", "local"])
async def test_webui_save_and_load_preserve_font_mode_and_inactive_addresses(
    monkeypatch, mode
):
    manager = MagicMock(config={})
    routes = config_routes.ConfigRoutes(
        analysis_service=MagicMock(config_manager=manager)
    )
    draft = {
        "config": {
            "t2i_rendering": {
                "t2i_rendering_strategies": [
                    {
                        "__template_key": "custom",
                        "font_mode": mode,
                        "google_fonts": "https://saved.example/fonts",
                        "gstatic": "https://saved.example/files",
                    }
                ]
            }
        }
    }
    request = MagicMock(json=AsyncMock(return_value=draft))
    monkeypatch.setattr(config_routes, "request", request)
    monkeypatch.setattr(config_routes, "json_response", lambda data, **_kwargs: data)
    assert (await routes.api_save_config())["status"] == "ok"
    manager.save_config.assert_called_once()
    response = await routes.api_get_config()
    saved = response["data"]["config"]["t2i_rendering"]["t2i_rendering_strategies"][0]
    assert saved["font_mode"] == mode
    assert saved["google_fonts"] == "https://saved.example/fonts"
    assert saved["gstatic"] == "https://saved.example/files"
