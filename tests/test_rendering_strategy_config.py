"""渲染方案解析、默认配置与资源环境选择。"""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator
from src.infrastructure.config.rendering_config import (
    DEFAULT_RENDERING_STRATEGY,
    parse_rendering_strategies,
)


def test_removed_round_parameters_do_not_override_default_strategy():
    manager = object.__new__(ConfigManager)
    manager.config = {
        "t2i_rendering": {
            "t2i_r1_quality": 95,
            "t2i_r2_timeout": 120000,
            "t2i_font_source": "Mainland",
            "t2i_cdn_base_url": "https://legacy.example/",
        }
    }
    manager.save_config = Mock()
    ConfigMigrator(manager).migrate_legacy_configs()
    before = deepcopy(manager.config)
    plans = manager.get_t2i_rendering_strategies()
    assert len(plans) == 1
    assert plans[0]["quality"] == 80
    assert plans[0]["type"] == "png"
    assert plans[0]["resource_environment"] == "Overseas"
    assert plans[0]["timeout"] == 20000
    assert manager.get_t2i_font_source() == "Overseas"
    assert manager.get_t2i_cdn_base_url("Overseas") == "https://legacy.example"
    assert manager.config == before


@pytest.mark.parametrize(
    "group",
    [
        {},
        {"t2i_rendering_strategies": []},
        {"t2i_rendering_strategies": [{"environment": "Local"}]},
    ],
)
def test_missing_empty_or_invalid_strategies_use_independent_default(group):
    manager = object.__new__(ConfigManager)
    manager.config = {"t2i_rendering": group}
    before = deepcopy(manager.config)
    plans = manager.get_t2i_rendering_strategy_config()
    assert plans == [DEFAULT_RENDERING_STRATEGY]
    plans[0]["priority"] = 999
    assert manager.get_t2i_rendering_strategy_config() == [DEFAULT_RENDERING_STRATEGY]
    assert manager.config == before


def test_schema_default_matches_runtime_and_removes_old_round_fields():
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    fields = schema["t2i_rendering"]["items"]
    assert not any(key.startswith(("t2i_r1_", "t2i_r2_")) for key in fields)
    assert "t2i_font_source" not in fields
    value = fields["t2i_rendering_strategies"]["default"]
    assert value[0]["__template_key"] == "strategy"
    assert parse_rendering_strategies(value) == [DEFAULT_RENDERING_STRATEGY]
    template_defaults = {
        key: field["default"]
        for key, field in fields["t2i_rendering_strategies"]["templates"]["strategy"][
            "items"
        ].items()
    }
    assert parse_rendering_strategies([{ "name": "海外方案" }]) == parse_rendering_strategies(
        [template_defaults]
    )
    assert template_defaults["timeout"] == DEFAULT_RENDERING_STRATEGY["timeout"]


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
            "t2i_rendering_strategies": [{"environment": environment}],
        }
    }
    manager.save_config = Mock()
    ConfigMigrator(manager).migrate_legacy_configs()
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
