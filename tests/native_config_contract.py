"""独立运行真实 AstrBot 配置契约验证，避免 Pytest 的宿主离线桩掩盖差异。

将宿主和插件根目录加入 PYTHONPATH，在实际 AstrBot 环境运行本文件。
"""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from astrbot.api import AstrBotConfig
from astrbot.dashboard.services.config_service import ConfigDisplayService

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator

PLUGIN_ROOT = Path(__file__).parents[1]


class NativeConfigurationContract(unittest.TestCase):
    """使用真实文件、真实宿主校验与原生配置读取服务。"""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "plugin_config.json"
        self.schema = json.loads(
            (PLUGIN_ROOT / "_conf_schema.json").read_text(encoding="utf-8")
        )

    def load(self, group, snapshot=None):
        """装配真实宿主配置。

        Args:
            group: 本场景的图片渲染配置。

        Returns:
            持有真实 AstrBotConfig 的插件配置管理器。
        """
        self.path.write_text(json.dumps({"t2i_rendering": group}), encoding="utf-8")
        data_dir = Path(self.directory.name) / "plugin_data"
        data_dir.mkdir(exist_ok=True)
        class Tools:
            @staticmethod
            def get_data_dir(_name):
                return data_dir
        if snapshot is not None:
            (data_dir / "upgrade_protection_state.json").write_text(json.dumps({"version": "v1.0.0", "schema_fingerprint": "previous-schema", "config": {"t2i_rendering": snapshot}}), encoding="utf-8")
        manager = object.__new__(ConfigManager)
        manager.StarTools = Tools
        manager._migrator = ConfigMigrator(manager, star_tools=Tools)
        manager.config = AstrBotConfig(
            config_path=str(self.path), schema=deepcopy(self.schema)
        )
        return manager

    def test_host_cleanup_removes_old_schema_keys_and_migration_reads_protected_snapshot(self):
        group = {"t2i_mainland_cdn_base_url": "https://legacy.example", "t2i_rendering_strategies": [{"__template_key": "strategy", "environment": "Mainland"}]}
        manager = self.load(group, snapshot=group)
        self.assertNotIn("t2i_mainland_cdn_base_url", manager.config["t2i_rendering"])
        manager._migrator.run_all_migrations()
        self.assertEqual(manager.get_t2i_cdn_base_url(), "https://legacy.example")
        self.assertEqual(manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]["__template_key"], "mainland")
        self.assertEqual(len(list((Path(self.directory.name) / "plugin_data/config_backups").glob("plugin_config_*.json"))), 1)

    def test_injected_default_round_does_not_override_protected_global_cdn(self):
        group = {"t2i_cdn_base_url": "https://legacy-global.example"}
        manager = self.load(group, snapshot=group)
        manager._migrator.run_all_migrations()
        self.assertEqual(manager.get_t2i_cdn_base_url(), "https://legacy-global.example")
        self.assertNotIn("t2i_cdn_base_url", manager.config["t2i_rendering"])

    def test_missing_protection_history_uses_defaults_after_host_cleanup(self):
        manager = self.load({"t2i_cdn_base_url": "https://unrecoverable.example"})
        manager._migrator.run_all_migrations()
        self.assertEqual(manager.get_t2i_cdn_base_url(), "https://cdn.jsdmirror.com")
        self.assertNotIn("t2i_cdn_base_url", manager.config["t2i_rendering"])

    def test_removed_comic_reference_migrates_from_protection_after_real_host_cleanup(self):
        manager = self.load({})
        data_dir = manager.StarTools.get_data_dir("verify")
        relative = "files/daily_comic/drawing_reference_image/old.png"
        source = data_dir / relative
        source.parent.mkdir(parents=True)
        source.write_bytes(b"reference-image")
        old = {"daily_comic": {"drawing_reference_image": [relative]}}
        self.path.write_text(json.dumps(old), encoding="utf-8")
        manager.config = AstrBotConfig(config_path=str(self.path), schema=deepcopy(self.schema))
        self.assertNotIn("drawing_reference_image", manager.config["daily_comic"])
        (data_dir / "upgrade_protection_state.json").write_text(json.dumps({"version": "v1.0.0", "schema_fingerprint": "old-schema", "config": old}), encoding="utf-8")
        with patch("src.infrastructure.config.config_manager.StarTools", manager.StarTools):
            manager._migrator.run_all_migrations()
        group = manager.config["daily_comic"]
        self.assertNotIn("drawing_reference_image", group)
        self.assertEqual(len(group["comic_characters"]), 1)
        self.assertEqual((data_dir / group["comic_characters"][0]["reference_images"][0]).read_bytes(), b"reference-image")

    def test_custom_service_preset_keeps_local_endpoint_and_resource_selection_on_reload(self):
        fields = self.schema["t2i_rendering"]["items"]["t2i_rendering_strategies"]["templates"]["custom"]["items"]
        draft = {key: field["default"] for key, field in fields.items()}
        draft["__template_key"] = "custom"
        manager = self.load({"t2i_rendering_strategies": [draft]})
        for environment, font in (("Overseas", "https://fonts.googleapis.com"), ("Mainland", "https://fonts.loli.net")):
            raw = manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]
            raw["environment"] = environment
            manager.save_config()
            manager.config = AstrBotConfig(config_path=str(self.path), schema=deepcopy(self.schema))
            plan = manager.get_t2i_rendering_strategy_config()[0]
            self.assertEqual(plan["__template_key"], "custom")
            self.assertEqual(plan["render_service"], "custom")
            self.assertEqual(plan["request_timeout"], 40000)
            self.assertEqual(plan["timeout"], 20000)
            self.assertEqual(plan["service_endpoint"], "http://127.0.0.1:8999/text2img")
            self.assertEqual(plan["google_fonts"], font)
            self.assertEqual(manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]["google_fonts"], "")

    def test_host_cleanup_preserves_old_custom_service_until_migration(self):
        original = {
            "__template_key": "mainland", "render_service": "custom",
            "environment": "Mainland", "service_endpoint": "http://render:8999/text2img",
            "service_token": "secret", "priority": 20,
            "cdn_base_url": "https://cdn.example", "google_fonts": "https://fonts.example", "gstatic": "https://static.example",
        }
        manager = self.load({"t2i_rendering_strategies": [original]})
        self.assertTrue(ConfigMigrator(manager).migrate_legacy_configs())
        reloaded = AstrBotConfig(config_path=str(self.path), schema=deepcopy(self.schema))
        original.pop("render_service")
        self.assertEqual(reloaded["t2i_rendering"]["t2i_rendering_strategies"], [{**original, "__template_key": "custom", "request_timeout": 40000}])

    def test_native_custom_mode_and_webui_save_share_persisted_values_and_choices(self):
        manager = self.load(
            {
                "t2i_rendering_strategies": [
                    {
                        "cdn_base_url": "__custom__",
                        "custom_cdn_base_url": " https://native.example/ ",
                    }
                ]
            }
        )
        self.assertTrue(ConfigMigrator(manager).migrate_legacy_configs())
        plan = manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]
        self.assertEqual(plan["cdn_base_url"], "https://native.example")
        plan["cdn_base_url"] = "https://webui.example"
        manager.save_config()
        metadata = SimpleNamespace(name="verify", config=manager.config, i18n={})
        service = object.__new__(ConfigDisplayService)
        with patch(
            "astrbot.dashboard.services.config_service.star_registry", [metadata]
        ):
            native = service.get_plugin_config("verify")
        self.assertIs(native["config"], manager.config)
        self.assertEqual(
            native["config"]["t2i_rendering"]["t2i_rendering_strategies"][0][
                "cdn_base_url"
            ],
            "https://webui.example",
        )
        templates = native["metadata"]["verify"]["items"]["t2i_rendering"]["items"][
            "t2i_rendering_strategies"
        ]["templates"]
        for template in templates.values():
            self.assertIn(
                "https://webui.example", template["items"]["cdn_base_url"]["options"]
            )
        reloaded = AstrBotConfig(
            config_path=str(self.path), schema=deepcopy(self.schema)
        )
        self.assertEqual(
            reloaded["t2i_rendering"]["t2i_rendering_strategies"][0]["cdn_base_url"],
            "https://webui.example",
        )


    def test_native_save_then_reload_persists_priority_order_and_keeps_existing_rounds(self):
        manager = self.load({"t2i_rendering_strategies": [
            {"__template_key": "custom", "name": "最后", "priority": 30, "service_token": "secret"},
            {"__template_key": "strategy", "name": "同级甲", "priority": 10},
            {"__template_key": "mainland", "name": "同级乙", "priority": 10},
        ]})
        # 原生配置保存后会重载插件，在初始化迁移阶段整理顺序。
        manager.config.save_config()
        manager._migrator.run_all_migrations()
        persisted = json.loads(self.path.read_text(encoding="utf-8-sig"))["t2i_rendering"]["t2i_rendering_strategies"]
        self.assertEqual([plan["name"] for plan in persisted], ["同级甲", "同级乙", "最后"])
        self.assertEqual(persisted[-1]["service_token"], "secret")
        reloaded = AstrBotConfig(config_path=str(self.path), schema=deepcopy(self.schema))
        self.assertEqual(reloaded["t2i_rendering"]["t2i_rendering_strategies"], persisted)
        self.assertFalse(manager._migrator.migrate_legacy_configs())

    def test_native_initial_config_has_two_defaults_but_keeps_user_single_round(self):
        manager = self.load({})
        manager._migrator.run_all_migrations()
        plans = manager.get_t2i_rendering_strategy_config()
        self.assertEqual([(plan["environment"], plan["priority"]) for plan in plans], [("Overseas", 10), ("Mainland", 20)])
        manager = self.load({"t2i_rendering_strategies": [{"__template_key": "custom", "name": "自用", "priority": 3}]})
        manager._migrator.run_all_migrations()
        self.assertEqual(len(manager.get_t2i_rendering_strategy_config()), 1)


    def test_custom_wait_budget_saves_and_reloads_independently(self):
        manager = self.load({"t2i_rendering_strategies": [{"__template_key": "custom", "timeout": 20000, "request_timeout": 70000}]})
        manager._migrator.run_all_migrations()
        manager.save_config()
        manager.config = AstrBotConfig(config_path=str(self.path), schema=deepcopy(self.schema))
        plan = manager.get_t2i_rendering_strategy_config()[0]
        self.assertEqual((plan["timeout"], plan["request_timeout"]), (20000, 70000))
        self.assertEqual(manager.get_t2i_rendering_strategies()[0]["request_timeout"], 70000)
        templates = self.schema["t2i_rendering"]["items"]["t2i_rendering_strategies"]["templates"]
        self.assertEqual(templates["custom"]["items"]["request_timeout"]["default"], 40000)
        for kind in ("strategy", "mainland"):
            self.assertNotIn("request_timeout", templates[kind]["items"])


if __name__ == "__main__":
    unittest.main()
