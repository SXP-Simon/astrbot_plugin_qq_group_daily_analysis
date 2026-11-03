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
