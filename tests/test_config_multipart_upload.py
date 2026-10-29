"""混合 multipart 输入应跳过无效项并继续保存有效文件。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from test_config_file_paths import file_roots as file_roots

from src.infrastructure.webui.routes import config_routes as route_module
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


class UploadedFiles(dict):
    def getlist(self, key):
        return self[key]


@pytest.mark.asyncio
@pytest.mark.parametrize("async_read", [True, False])
async def test_multipart_skips_invalid_lists_and_empty_files(file_roots, monkeypatch, async_read):
    reader = AsyncMock if async_read else Mock
    files = UploadedFiles({
        "invalid": object(),
        "images": [
            SimpleNamespace(filename="empty.png", read=reader(return_value=b"")),
            SimpleNamespace(filename="valid.png", read=reader(return_value=b"image")),
        ],
    })
    monkeypatch.setattr(route_module, "request", MagicMock(query={}, files=files, json=AsyncMock(return_value={})))
    response = await ConfigRoutes(None).api_upload_config_file()
    assert response["status_code"] == 200
    body = response["data"] if "status" in response.get("data", {}) else response
    paths = body["data"]["paths"]
    assert len(paths) == 1
    assert (file_roots[0] / paths[0]).read_bytes() == b"image"
    assert not list(file_roots[0].rglob("*empty.png"))
