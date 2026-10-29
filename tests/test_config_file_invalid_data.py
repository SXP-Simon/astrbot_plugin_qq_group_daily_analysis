"""上传和旧参考图迁移必须拒绝无效 Base64。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from test_config_file_paths import file_roots as file_roots

from src.infrastructure.webui.routes import config_routes as route_module
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data", ["@@@@", "data:image/png;base64,@@@@", "data:image/png;base64,"]
)
async def test_invalid_upload_does_not_create_file(file_roots, monkeypatch, data):
    monkeypatch.setattr(
        route_module,
        "request",
        MagicMock(
            query={},
            files=None,
            json=AsyncMock(
                return_value={"file_data": data, "filename": "reference.png"}
            ),
        ),
    )
    response = await ConfigRoutes(None).api_upload_config_file()
    assert response["status_code"] == 400
    assert not list(file_roots[0].rglob("*.png"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data", ["data:image/png;base64,@@@@", "data:image/png;base64,"]
)
async def test_invalid_migrated_reference_does_not_save_config(
    file_roots, monkeypatch, data
):
    original = {"basic": {"max_topics": 3}}
    manager = SimpleNamespace(config=original.copy(), save_config=MagicMock())
    request_config = {
        "daily_comic": {"comic_characters": [{"reference_images": [data]}]}
    }
    monkeypatch.setattr(
        route_module,
        "request",
        MagicMock(query={}, json=AsyncMock(return_value={"config": request_config})),
    )
    response = await ConfigRoutes(
        SimpleNamespace(config_manager=manager)
    ).api_save_config()
    assert response["status_code"] == 400
    assert manager.config == original
    manager.save_config.assert_not_called()
