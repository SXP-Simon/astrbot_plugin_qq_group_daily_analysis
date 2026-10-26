"""验证历史配置备份 API 的只读行为和请求边界。"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.infrastructure.webui.routes.data_management_routes import DataManagementRoutes


@pytest.mark.asyncio
async def test_read_only_routes_list_detail_and_missing_files(tmp_path):
    directory = tmp_path / "config_backups"
    directory.mkdir()
    (directory / "old.json").write_text('{"config":{"old":[1,null]}}', encoding="utf-8")
    before = (directory / "old.json").read_bytes()
    routes = DataManagementRoutes(SimpleNamespace())
    routes._get_plugin_data_dir = lambda: tmp_path
    listing = await routes.api_get_config_backups()
    assert listing["data"]["data"]["items"][0]["filename"] == "old.json"
    with patch("src.infrastructure.webui.routes.data_management_routes.request", SimpleNamespace(query={"filename": "old.json"})):
        detail = await routes.api_get_config_backup()
    assert detail["data"]["data"]["content"] == {"config": {"old": [1, None]}}
    assert (directory / "old.json").read_bytes() == before
    for name, expected in (("../secret.json", 400), ("gone.json", 404)):
        with patch("src.infrastructure.webui.routes.data_management_routes.request", SimpleNamespace(query={"filename": name})):
            assert (await routes.api_get_config_backup())["status_code"] == expected
