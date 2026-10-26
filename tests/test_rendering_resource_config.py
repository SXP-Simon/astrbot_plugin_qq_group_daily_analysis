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


def test_schema_has_two_editable_presets_and_only_one_initial_round():
    fields = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )["t2i_rendering"]["items"]
    strategies = fields["t2i_rendering_strategies"]
    assert len(strategies["default"]) == 1
    for key, environment in (("strategy", "Overseas"), ("mainland", "Mainland")):
        items = strategies["templates"][key]["items"]
        defaults = {name: field["default"] for name, field in items.items()}
        plan = parse_rendering_strategies([defaults])[0]
        assert plan["environment"] == environment
        assert {
            name: plan[name] for name in DEFAULT_RENDERING_RESOURCES[environment]
        } == DEFAULT_RENDERING_RESOURCES[environment]
        assert items["render_service"]["options"] == ["astrbot", "custom"]
    assert all(
        field.get("invisible")
        for name, field in fields.items()
        if name.startswith(("t2i_mainland_", "t2i_overseas_"))
    )


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
    assert [item["priority"] for item in plans] == [20, 10]
    assert plans[0]["cdn_base_url"] == "https://old.example"
    assert plans[0]["google_fonts"] == "https://old.example/fonts"
    assert plans[1]["cdn_base_url"] == "https://new.example"
    assert plans[0]["future"] == [1]
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
