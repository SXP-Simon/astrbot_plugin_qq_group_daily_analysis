"""每轮资源的配置投影与保存校验。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.rendering_config import parse_rendering_strategies
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
@pytest.mark.parametrize("template", ["strategy", "custom"])
async def test_custom_entry_save_normalizes_value_or_rejects_before_mutation(
    key, address, template
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
                            {"__template_key": template, key: "__custom__", f"custom_{key}": address}
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


@pytest.mark.asyncio
async def test_custom_service_preset_save_and_read_keep_environment_defaults_editable():
    manager = object.__new__(ConfigManager)
    manager.config = {}
    manager.save_config = Mock()
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    for environment, font in (("Overseas", "https://fonts.googleapis.com"), ("Mainland", "https://fonts.loli.net")):
        draft = {
            "__template_key": "custom", "environment": environment,
            "cdn_base_url": "", "google_fonts": "", "gstatic": "https://my-static.example",
        }
        with patch("src.infrastructure.webui.routes.config_routes.request") as request:
            request.json = AsyncMock(return_value={"config": {"t2i_rendering": {"t2i_rendering_strategies": [draft]}}})
            assert (await routes.api_save_config())["status_code"] == 200
        stored = manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]
        assert stored["__template_key"] == "custom"
        assert "render_service" not in stored
        assert stored["service_endpoint"] == "http://127.0.0.1:8999/text2img"
        assert stored["google_fonts"] == ""
        runtime = parse_rendering_strategies([stored])[0]
        assert runtime["google_fonts"] == font
        assert runtime["gstatic"] == "https://my-static.example"
        response = await routes.api_get_config()
        projected = response["data"]["data"]["config"]["t2i_rendering"]["t2i_rendering_strategies"][0]
        assert projected["google_fonts"] == projected["cdn_base_url"] == ""


@pytest.mark.asyncio
async def test_legacy_custom_service_read_projects_new_type_without_writing():
    manager = object.__new__(ConfigManager)
    manager.config = {"t2i_rendering": {"t2i_rendering_strategies": [{
        "__template_key": "mainland", "render_service": "custom",
        "service_endpoint": "https://render.example/text2img", "service_token": "secret",
    }]}}
    before = deepcopy(manager.config)
    manager.save_config = Mock()
    response = await ConfigRoutes(SimpleNamespace(config_manager=manager)).api_get_config()
    plan = response["data"]["data"]["config"]["t2i_rendering"]["t2i_rendering_strategies"][0]
    assert plan["__template_key"] == "custom"
    assert plan["environment"] == "Mainland"
    assert plan["service_token"] == "secret"
    assert manager.config == before
    manager.save_config.assert_not_called()
