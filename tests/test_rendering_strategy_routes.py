"""渲染方案配置读取与保存边界，不触碰真实 AstrBot 配置文件。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.rendering_config import DEFAULT_RENDERING_STRATEGY_PRESETS, parse_rendering_strategies
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.mark.asyncio
@pytest.mark.parametrize("strategies", [None, []])
async def test_read_shows_overseas_then_mainland_defaults_without_persisting(strategies):
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
    expected = parse_rendering_strategies(list(DEFAULT_RENDERING_STRATEGY_PRESETS))
    for plan in expected:
        plan.pop("render_service")
    assert projected["t2i_rendering_strategies"] == expected
    assert [(plan["environment"], plan["priority"]) for plan in expected] == [("Overseas", 10), ("Mainland", 20)]
    assert projected["future"] == {"keep": True}
    assert manager.config == original


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "environment", ["Mainland", "Overseas"]
)
@pytest.mark.parametrize(
    "value",
    ["bad", 42, "https://host.example/gh/file", "https://user:pass@host.example"],
)
async def test_invalid_environment_cdn_is_rejected_before_saving(environment, value):
    manager = SimpleNamespace(config={"old": {"keep": True}}, save_config=Mock())
    original = deepcopy(manager.config)
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={"config": {"t2i_rendering": {"t2i_rendering_strategies": [{"environment": environment, "cdn_base_url": value}]}}}
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
                    "cdn_base_url": " https://mainland.example/ ",
                    "future": [" untouched "],
                }
            ],
        },
        "future": {"data": [None, True]},
    }
    expected = deepcopy(config)
    expected["t2i_rendering"].pop("t2i_mainland_cdn_base_url")
    expected["t2i_rendering"].pop("t2i_overseas_cdn_base_url")
    expected["t2i_rendering"]["t2i_rendering_strategies"][0].update({
        "__template_key": "mainland", "service_endpoint": "", "service_token": "",
        "cdn_base_url": "https://mainland.example", "google_fonts": "https://fonts.loli.net", "gstatic": "https://gstatic.loli.net"
    })
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": config})
        response = await routes.api_save_config()
    assert response["status_code"] == 200
    assert manager.config == expected
    manager.save_config.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"service_endpoint": "http://host?token=secret"},
        {"service_endpoint": ""},
        {"service_token": "secret\r\nInjected: yes"},
        {"render_service": "unknown"},
    ],
)
async def test_invalid_custom_service_is_rejected_before_persistence(fields):
    manager = SimpleNamespace(config={"future": {"keep": True}}, save_config=Mock())
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    plan = {
        "render_service": "custom",
        "service_endpoint": "http://127.0.0.1:8999/text2img",
        **fields,
    }
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={
                "config": {"t2i_rendering": {"t2i_rendering_strategies": [plan]}}
            }
        )
        response = await routes.api_save_config()
    assert response["status_code"] == 400
    assert manager.config == {"future": {"keep": True}}
    manager.save_config.assert_not_called()


@pytest.mark.asyncio
async def test_save_sorts_custom_service_without_losing_extensions():
    manager = SimpleNamespace(config={}, save_config=Mock())
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    plans = [
        {
            "render_service": "custom",
            "service_endpoint": " http://127.0.0.1:8999/text2img/generate/ ",
            "service_token": " secret ",
            "priority": 20,
            "future": [1],
        },
        {"priority": 10},
    ]
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(
            return_value={
                "config": {"t2i_rendering": {"t2i_rendering_strategies": plans}}
            }
        )
        response = await routes.api_save_config()
    assert response["status_code"] == 200
    saved = manager.config["t2i_rendering"]["t2i_rendering_strategies"]
    assert [plan["priority"] for plan in saved] == [10, 20]
    assert [{k: v for k, v in plan.items() if k not in ("cdn_base_url", "google_fonts", "gstatic")} for plan in reversed(saved)] == [
        {
            "service_endpoint": "http://127.0.0.1:8999/text2img",
            "service_token": "secret",
            "request_timeout": 40000,
            "__template_key": "custom",
            "environment": "Overseas",
            "priority": 20,
            "future": [1],
        },
        {"priority": 10, "__template_key": "strategy", "environment": "Overseas", "service_endpoint": "", "service_token": ""},
    ]

    assert all(plan["cdn_base_url"] == "https://cdn.jsdmirror.com" for plan in saved)


@pytest.mark.asyncio
async def test_save_empty_list_persists_two_defaults_and_stable_ties_keep_unknown_values():
    manager = SimpleNamespace(config={}, save_config=Mock())
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": {"t2i_rendering": {"t2i_rendering_strategies": []}}})
        assert (await routes.api_save_config())["status_code"] == 200
        plans = manager.config["t2i_rendering"]["t2i_rendering_strategies"]
        assert [(plan["environment"], plan["priority"]) for plan in plans] == [("Overseas", 10), ("Mainland", 20)]
        request.json = AsyncMock(return_value={"config": {"t2i_rendering": {"t2i_rendering_strategies": [
            {"name": "最后", "priority": 30},
            {"name": "甲", "priority": 10, "future": {"keep": True}},
            {"name": "乙", "priority": 10},
        ]}}})
        assert (await routes.api_save_config())["status_code"] == 200
    plans = manager.config["t2i_rendering"]["t2i_rendering_strategies"]
    assert [plan["name"] for plan in plans] == ["甲", "乙", "最后"]
    assert plans[0]["future"] == {"keep": True}
