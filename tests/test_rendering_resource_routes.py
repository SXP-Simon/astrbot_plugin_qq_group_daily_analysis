"""每轮资源的配置投影与保存校验。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.mark.asyncio
async def test_read_projects_legacy_resources_without_reordering_or_saving():
    manager = object.__new__(ConfigManager)
    manager.config = {
        "t2i_rendering": {
            "t2i_mainland_cdn_base_url": "https://old.example",
            "t2i_rendering_strategies": [
                {"environment": "Mainland", "priority": 20, "future": [1]},
                {"priority": 10},
            ],
        }
    }
    manager.save_config = Mock()
    before = deepcopy(manager.config)
    response = await ConfigRoutes(
        SimpleNamespace(config_manager=manager)
    ).api_get_config()
    plans = response["data"]["data"]["config"]["t2i_rendering"][
        "t2i_rendering_strategies"
    ]
    assert plans[0]["cdn_base_url"] == "https://old.example"
    assert plans[0]["google_fonts"] == "https://fonts.loli.net"
    assert plans[0]["future"] == [1]
    assert [item["priority"] for item in plans] == [20, 10]
    assert manager.config == before
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["cdn_base_url", "google_fonts", "gstatic"])
async def test_invalid_round_resources_reject_save_before_mutation(field):
    manager = SimpleNamespace(config={"future": {"keep": True}}, save_config=Mock())
    before = deepcopy(manager.config)
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={
                "config": {
                    "t2i_rendering": {
                        "t2i_rendering_strategies": [
                            {field: "https://user:pass@example.com"}
                        ]
                    }
                }
            }
        )
        assert (await routes.api_save_config())["status_code"] == 400
    assert manager.config == before
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["cdn_base_url", "google_fonts", "gstatic"])
@pytest.mark.parametrize("address", [" https://custom.example/ ", ""])
async def test_custom_entry_save_normalizes_value_or_rejects_before_mutation(
    key, address
):
    manager = object.__new__(ConfigManager)
    manager.config = {"basic": {"max_topics": 7}}
    manager.save_config = Mock()
    original = deepcopy(manager.config)
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={
                "config": {
                    "t2i_rendering": {
                        "t2i_rendering_strategies": [
                            {key: "__custom__", f"custom_{key}": address}
                        ]
                    }
                }
            }
        )
        response = await ConfigRoutes(
            SimpleNamespace(config_manager=manager)
        ).api_save_config()
    if address:
        assert response["status_code"] == 200
        plan = manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]
        assert plan[key] == plan[f"custom_{key}"] == "https://custom.example"
        manager.save_config.assert_called_once()
    else:
        assert response["status_code"] == 400
        assert manager.config == original
        manager.save_config.assert_not_called()
