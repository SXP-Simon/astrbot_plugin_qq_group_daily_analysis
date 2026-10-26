"""渲染方案解析、旧配置兼容与资源环境选择。"""

from copy import deepcopy

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.rendering_config import parse_rendering_strategies


def test_legacy_two_rounds_and_profile_fallback_are_read_only():
    manager = object.__new__(ConfigManager)
    manager.config = {
        "t2i_rendering": {
            "t2i_r1_quality": 95,
            "t2i_r2_timeout": 120000,
            "t2i_font_source": "Mainland",
            "t2i_cdn_base_url": "https://legacy.example/",
        }
    }
    before = deepcopy(manager.config)
    plans = manager.get_t2i_rendering_strategies()
    assert [item["quality"] for item in plans] == [95, 80]
    assert [item["resource_environment"] for item in plans] == ["Mainland", "Mainland"]
    assert plans[1]["timeout"] == 120000
    assert manager.get_t2i_cdn_base_url("Overseas") == "https://legacy.example"
    assert manager.config == before


def test_same_priority_preserves_order_and_unknown_fields():
    raw = [{"name": "A", "future": {"keep": 1}}, {"name": "B", "priority": 10}]
    original = deepcopy(raw)
    assert [item["name"] for item in parse_rendering_strategies(raw)] == ["A", "B"]
    assert raw == original


@pytest.mark.parametrize("environment", ["Mainland", "Overseas"])
@pytest.mark.parametrize("empty", [None, "", " \t "])
def test_blank_profile_cdn_inherits_legacy_address(environment, empty):
    manager = object.__new__(ConfigManager)
    manager.config = {
        "t2i_rendering": {
            "t2i_cdn_base_url": "https://legacy.example/",
            f"t2i_{environment.lower()}_cdn_base_url": empty,
        }
    }
    assert manager.get_t2i_cdn_base_url(environment) == "https://legacy.example"


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        [None],
        [{"priority": True}],
        [{"environment": "Local"}],
        [{"quality": 101}],
        [{"timeout": 0}],
        [{"type": "gif"}],
        [{"device_scale": "wrong"}],
        [{"name": 1}],
    ],
)
def test_invalid_rendering_strategies_are_rejected(value):
    with pytest.raises(ValueError):
        parse_rendering_strategies(value)
