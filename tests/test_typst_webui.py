"""字体管理与独立渲染测试入口的实际行为检查。"""

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from test_t2i_probe import probe as probe

from src.infrastructure.webui.routes import config_routes


@pytest.mark.asyncio
async def test_typst_probe_uses_plugin_data_and_no_host(probe, tmp_path, monkeypatch):
    routes, request, _ = probe
    monkeypatch.setattr(config_routes.StarTools, "get_data_dir", lambda name: tmp_path)
    output = BytesIO()
    Image.new("RGB", (480, 180), "#39c5bb").save(output, format="PNG")
    renderer = AsyncMock(return_value=output.getvalue())
    monkeypatch.setattr(config_routes, "render_typst_probe", renderer)
    request.json.return_value = {"render_service": "typst", "typst_ppi": 120, "timeout": 30000}
    result = await routes.api_test_t2i()
    assert result["data"]["status"] == "ok"
    assert renderer.await_args.args == (tmp_path, {"render_service": "typst", "timeout": 30000})
    routes.analysis_service.html_render.assert_not_called()


@pytest.mark.asyncio
async def test_font_download_is_serialized_and_uses_managed_directory(probe, tmp_path, monkeypatch):
    routes, request, _ = probe
    monkeypatch.setattr(config_routes.StarTools, "get_data_dir", lambda name: tmp_path)
    entered, finish = asyncio.Event(), asyncio.Event()
    calls = []
    async def download(directory, cdn):
        calls.append((directory, cdn))
        entered.set()
        await finish.wait()
        return {"directory": str(directory / "typst/fonts"), "files": ["Noto.ttf"], "missing": [], "ready": True}
    monkeypatch.setattr(config_routes, "download_typst_fonts", download)
    request.json.return_value = {"cdn_base_url": "https://cdn.jsdelivr.net/", "path": "/not/allowed"}
    task = asyncio.create_task(routes.api_download_typst_fonts())
    await entered.wait()
    duplicate = await routes.api_download_typst_fonts()
    assert duplicate["status_code"] == 409
    finish.set()
    assert (await task)["data"]["data"]["ready"] is True
    assert calls == [(tmp_path, "https://cdn.jsdelivr.net")]


@pytest.mark.asyncio
async def test_font_download_rejects_url_credentials(probe, monkeypatch):
    routes, request, _ = probe
    download = AsyncMock()
    monkeypatch.setattr(config_routes, "download_typst_fonts", download)
    request.json.return_value = {"cdn_base_url": "https://user:secret@example.com"}
    assert (await routes.api_download_typst_fonts())["status_code"] == 400
    download.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine,output,expected", [
    ("typst", "image", ["native", "both"]),
    ("astrbot", "image", ["web", "both"]),
    ("typst", "html", ["web", "both"]),
    ("typst", "configured", ["both"]),
    ("typst", "all", ["web", "native", "both"]),
])
async def test_template_list_filters_actual_capabilities(monkeypatch, engine, output, expected):
    from unittest.mock import MagicMock
    from src.infrastructure.webui.routes import template_routes

    service = MagicMock()
    service.config_manager.get_output_format.return_value = ["image", "html"]
    service.config_manager.get_t2i_rendering_strategies.return_value = [{"render_service": engine}]
    manager = MagicMock()
    manager.get_available_templates.return_value = [
        {"id": "web", "has_image": True, "has_html": True, "has_typst": False},
        {"id": "native", "has_image": False, "has_html": False, "has_typst": True},
        {"id": "both", "has_image": True, "has_html": True, "has_typst": True},
    ]
    routes = template_routes.TemplateRoutes(service)
    monkeypatch.setattr(routes, "_get_html_templates", lambda: manager)
    monkeypatch.setattr(template_routes, "request", MagicMock(query={"render_format": output}))
    monkeypatch.setattr(template_routes, "json_response", lambda value: value)
    response = await routes.api_get_report_templates()
    assert [item["id"] for item in response["data"]] == expected
