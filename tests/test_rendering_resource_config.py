"""每轮资源契约、预设和旧配置升级迁移。"""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator
from src.infrastructure.config.rendering_config import (
    DEFAULT_RENDERING_RESOURCES,
    parse_rendering_strategies,
)

CASES = json.loads(
    (Path(__file__).parent / "data/rendering_resources.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", CASES)
def test_shared_resource_address_contract(case):
    before = deepcopy(case["plan"])
    if case["expected"] is None:
        with pytest.raises(ValueError):
            parse_rendering_strategies([case["plan"]])
    else:
        plan = parse_rendering_strategies([case["plan"]])[0]
        assert {
            key: plan[key] for key in ("cdn_base_url", "google_fonts", "gstatic")
        } == case["expected"]
    assert case["plan"] == before


def test_schema_has_three_presets_and_two_initial_host_rounds():
    fields = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )["t2i_rendering"]["items"]
    strategies = fields["t2i_rendering_strategies"]
    assert [(plan["environment"], plan["priority"]) for plan in strategies["default"]] == [("Overseas", 10), ("Mainland", 20)]
    assert set(strategies["templates"]) == {"strategy", "mainland", "custom"}
    for key, environment in (("strategy", "Overseas"), ("mainland", "Mainland")):
        items = strategies["templates"][key]["items"]
        defaults = {name: field["default"] for name, field in items.items()}
        plan = parse_rendering_strategies([defaults])[0]
        assert plan["environment"] == environment
        assert plan["priority"] == (10 if environment == "Overseas" else 20)
        assert {
            name: plan[name] for name in DEFAULT_RENDERING_RESOURCES[environment]
        } == DEFAULT_RENDERING_RESOURCES[environment]
        for name in ("render_service", "service_endpoint", "service_token"):
            assert name not in items
    custom = strategies["templates"]["custom"]["items"]
    assert "render_service" not in custom
    assert custom["service_endpoint"]["default"] == "http://127.0.0.1:8999/text2img"
    assert "condition" not in custom["service_endpoint"]
    assert not custom["environment"].get("invisible")
    assert not any(name.startswith(("t2i_mainland_", "t2i_overseas_")) for name in fields)
    assert "t2i_cdn_base_url" not in fields


def test_startup_migration_preserves_legacy_addresses_and_explicit_new_values():
    manager = object.__new__(ConfigManager)
    manager.config = {
        "t2i_rendering": {
            "t2i_mainland_cdn_base_url": " https://old.example/ ",
            "t2i_mainland_google_fonts": "https://old.example/fonts/",
            "t2i_mainland_gstatic": "https://old.example/static/",
            "t2i_rendering_strategies": [
                {"environment": "Mainland", "priority": 20, "future": [1]},
                {
                    "environment": "Mainland",
                    "priority": 10,
                    "cdn_base_url": "https://new.example",
                },
            ],
        }
    }
    manager.save_config = Mock()
    migrator = ConfigMigrator(manager)
    assert migrator.migrate_legacy_configs()
    plans = manager.config["t2i_rendering"]["t2i_rendering_strategies"]
    assert [item["priority"] for item in plans] == [10, 20]
    assert plans[1]["cdn_base_url"] == "https://old.example"
    assert plans[1]["google_fonts"] == "https://old.example/fonts"
    assert plans[0]["cdn_base_url"] == "https://new.example"
    assert plans[1]["future"] == [1]
    manager.save_config.assert_called_once()
    assert not migrator.migrate_legacy_configs()
    manager.save_config.assert_called_once()


def test_startup_migration_does_not_partially_modify_invalid_plans():
    manager = object.__new__(ConfigManager)
    manager.config = {
        "t2i_rendering": {"t2i_rendering_strategies": [{}, {"priority": False}]}
    }
    before = deepcopy(manager.config)
    manager.save_config = Mock()
    assert not ConfigMigrator(manager).migrate_legacy_configs()
    assert manager.config == before
    manager.save_config.assert_not_called()


@pytest.mark.parametrize("template", ["strategy", "mainland"])
def test_old_custom_round_moves_to_custom_template_without_losing_configuration(template):
    manager = object.__new__(ConfigManager)
    original = {
        "__template_key": template,
        "environment": "Mainland",
        "render_service": "custom",
        "service_endpoint": "https://render.example/proxy/text2img",
        "service_token": "secret",
        "cdn_base_url": "https://cdn.example",
        "google_fonts": "https://fonts.example/css",
        "gstatic": "https://static.example/fonts",
        "priority": 30,
        "future": [1],
    }
    manager.config = {"t2i_rendering": {"t2i_rendering_strategies": [deepcopy(original)]}}
    manager.save_config = Mock()
    migrator = ConfigMigrator(manager)
    assert migrator.migrate_legacy_configs()
    assert manager.config["t2i_rendering"]["t2i_rendering_strategies"] == [
        {**{key: value for key, value in original.items() if key != "render_service"}, "__template_key": "custom", "request_timeout": 40000}
    ]
    assert not migrator.migrate_legacy_configs()
    manager.save_config.assert_called_once()
