"""宿主选择框、自定义地址补项及保存同步的离线回归。"""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator
from src.infrastructure.config.rendering_schema import sync_rendering_schema_options


def test_native_resource_selectors_keep_custom_entry_without_legacy_schema_fields():
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    group = schema["t2i_rendering"]["items"]
    for environment in ("mainland", "overseas"):
        for key in ("cdn_base_url", "google_fonts", "gstatic"):
            assert f"t2i_{environment}_{key}" not in group
    for template_key, template in group["t2i_rendering_strategies"]["templates"].items():
        for key in ("cdn_base_url", "google_fonts", "gstatic"):
            field = template["items"][key]
            assert field["type"] == "string"
            assert field["default"] in field["options"]
            assert "__custom__" in field["options"]
            assert len(field["labels"]) == len(field["options"])
            expected = {key: "__custom__"}
            if template_key == "custom" and key != "cdn_base_url":
                expected["font_mode"] = "network"
            assert template["items"][f"custom_{key}"]["condition"] == expected


def test_saved_custom_addresses_are_selectable_in_all_presets_without_duplicates():
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    config = {
        "t2i_rendering_strategies": [
            {
                "cdn_base_url": "https://saved.example",
                "google_fonts": "https://saved.example/fonts",
                "gstatic": "https://saved.example/static",
            }
        ]
    }
    before = deepcopy(config)
    for _ in range(2):
        sync_rendering_schema_options(schema, config)
    templates = schema["t2i_rendering"]["items"]["t2i_rendering_strategies"][
        "templates"
    ]
    for template in templates.values():
        for key, address in config["t2i_rendering_strategies"][0].items():
            field = template["items"][key]
            assert field["options"].count(address) == 1
            assert (
                field["labels"][field["options"].index(address)]
                == f"自定义 · {address}"
            )
            assert len(field["options"]) == len(field["labels"])
    assert config == before


def test_native_custom_mode_migration_persists_actual_urls_and_refreshes_metadata():
    class NativeConfig(dict):
        pass

    manager = object.__new__(ConfigManager)
    manager.config = NativeConfig(
        {
            "t2i_rendering": {
                "t2i_rendering_strategies": [
                    {
                        "__template_key": "strategy",
                        "environment": "Mainland",
                        "cdn_base_url": "__custom__",
                        "custom_cdn_base_url": " https://native.example/ ",
                    }
                ]
            }
        }
    )
    manager.config.schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    manager.config.save_config = Mock()
    assert ConfigMigrator(manager).migrate_legacy_configs()
    plan = manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]
    assert (
        plan["cdn_base_url"] == plan["custom_cdn_base_url"] == "https://native.example"
    )
    manager.config.save_config.assert_called_once()
    for template in manager.config.schema["t2i_rendering"]["items"][
        "t2i_rendering_strategies"
    ]["templates"].values():
        assert "https://native.example" in template["items"]["cdn_base_url"]["options"]
    assert not ConfigMigrator(manager).migrate_legacy_configs()
    manager.config.save_config.assert_called_once()
