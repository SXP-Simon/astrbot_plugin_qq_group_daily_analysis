"""配置参考图读取和保存边界的回归测试。"""

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from test_config_file_paths import file_roots as file_roots

from src.infrastructure.webui.routes import config_routes as route_module
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.mark.asyncio
async def test_same_millisecond_uploads_have_independent_files(file_roots, monkeypatch):
    routes = ConfigRoutes(None)
    paths = []
    for contents in (b"first image", b"second image"):
        monkeypatch.setattr(
            route_module,
            "request",
            MagicMock(
                query={},
                files=None,
                json=AsyncMock(
                    return_value={
                        "filename": "reference.png",
                        "file_data": base64.b64encode(contents).decode(),
                    }
                ),
            ),
        )
        result = await routes.api_upload_config_file()
        assert result["status_code"] == 200
        body = result["data"] if "status" in result.get("data", {}) else result
        paths.append(body["data"]["path"])
    assert paths[0] != paths[1]
    assert (file_roots[0] / paths[0]).read_bytes() == b"first image"
    assert (file_roots[0] / paths[1]).read_bytes() == b"second image"


@pytest.mark.asyncio
async def test_reference_image_migration_preserves_same_millisecond_images(
    file_roots, monkeypatch
):
    manager = SimpleNamespace(config={}, save_config=lambda: None)
    images = [
        "data:image/png;base64," + base64.b64encode(data).decode()
        for data in (b"first reference", b"second reference")
    ]
    monkeypatch.setattr(
        route_module,
        "request",
        MagicMock(
            query={},
            json=AsyncMock(
                return_value={
                    "config": {
                        "daily_comic": {
                            "comic_characters": [
                                {"name": "角色", "reference_images": images}
                            ]
                        }
                    }
                }
            ),
        ),
    )
    result = await ConfigRoutes(
        SimpleNamespace(config_manager=manager)
    ).api_save_config()
    assert result["status_code"] == 200
    paths = manager.config["daily_comic"]["comic_characters"][0]["reference_images"]
    assert len(set(paths)) == 2
    assert (file_roots[1] / paths[0]).read_bytes() == b"first reference"
    assert (file_roots[1] / paths[1]).read_bytes() == b"second reference"
