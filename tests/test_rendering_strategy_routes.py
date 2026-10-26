"""渲染方案配置读取与保存边界，不触碰真实 AstrBot 配置文件。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.mark.asyncio
@pytest.mark.parametrize("strategies", [None, []])
async def test_read_shows_single_default_strategy_without_persisting(strategies):
    manager = object.__new__(ConfigManager)
    manager.config = {
        "t2i_rendering": {
            "t2i_font_source": "Mainland",
            "t2i_r1_quality": 97,
            "future": {"keep": True},
        }
    }
    if strategies is not None:
        manager.config["t2i_rendering"]["t2i_rendering_strategies"] = strategies
    original = deepcopy(manager.config)
    response = await ConfigRoutes(
        SimpleNamespace(config_manager=manager)
    ).api_get_config()
    body = response["data"]
    if "config" not in body:
        body = body["data"]
    projected = body["config"]["t2i_rendering"]
    assert projected["t2i_rendering_strategies"] == [
        {
            "__template_key": "strategy",
            "name": "默认方案",
            "priority": 10,
            "environment": "Overseas",
            "type": "png",
            "quality": 80,
            "device_scale": "high",
            "timeout": 20000,
        }
    ]
    assert projected["future"] == {"keep": True}
    assert manager.config == original


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key", ["t2i_mainland_cdn_base_url", "t2i_overseas_cdn_base_url"]
)
@pytest.mark.parametrize(
    "value",
    ["bad", 42, "https://host.example/gh/file", "https://user:pass@host.example"],
)
async def test_invalid_environment_cdn_is_rejected_before_saving(key, value):
    manager = SimpleNamespace(config={"old": {"keep": True}}, save_config=Mock())
    original = deepcopy(manager.config)
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={"config": {"t2i_rendering": {key: value}}}
        )
        response = await routes.api_save_config()
    assert response["status_code"] == 400
    assert manager.config == original
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value", [None, {}, [1], [{"environment": "Local"}], [{"priority": -1}]]
)
async def test_invalid_strategy_list_does_not_mutate_config(value):
    manager = SimpleNamespace(config={"old": {"keep": True}}, save_config=Mock())
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={
                "config": {"t2i_rendering": {"t2i_rendering_strategies": value}}
            }
        )
        response = await routes.api_save_config()
    assert response["status_code"] == 400
    assert manager.config == {"old": {"keep": True}}
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_save_normalizes_environment_cdn_and_keeps_strategy_extensions():
    manager = SimpleNamespace(config={}, save_config=Mock())
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    config = {
        "t2i_rendering": {
            "t2i_mainland_cdn_base_url": " https://mainland.example/ ",
            "t2i_overseas_cdn_base_url": "https://overseas.example///",
            "t2i_rendering_strategies": [
                {
                    "__template_key": "strategy",
                    "priority": 20,
                    "environment": "Mainland",
                    "future": [" untouched "],
                }
            ],
        },
        "future": {"data": [None, True]},
    }
    expected = deepcopy(config)
    expected["t2i_rendering"]["t2i_mainland_cdn_base_url"] = "https://mainland.example"
    expected["t2i_rendering"]["t2i_overseas_cdn_base_url"] = "https://overseas.example"
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": config})
        response = await routes.api_save_config()
    assert response["status_code"] == 200
    assert manager.config == expected
    manager.save_config.assert_called_once()
