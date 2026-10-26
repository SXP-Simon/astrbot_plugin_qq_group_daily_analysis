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

    def load(self, group):
        """装配真实宿主配置。

        Args:
            group: 本场景的图片渲染配置。

        Returns:
            持有真实 AstrBotConfig 的插件配置管理器。
        """
        self.path.write_text(json.dumps({"t2i_rendering": group}), encoding="utf-8")
        manager = object.__new__(ConfigManager)
        manager.config = AstrBotConfig(
            config_path=str(self.path), schema=deepcopy(self.schema)
        )
        return manager

    def test_host_cleanup_keeps_legacy_fields_until_migration(self):
        manager = self.load(
            {
                "t2i_mainland_cdn_base_url": "https://legacy.example",
                "t2i_rendering_strategies": [
                    {"__template_key": "strategy", "environment": "Mainland"}
                ],
            }
        )
        self.assertEqual(
            manager.config["t2i_rendering"]["t2i_mainland_cdn_base_url"],
            "https://legacy.example",
        )
        self.assertTrue(ConfigMigrator(manager).migrate_legacy_configs())
        self.assertEqual(manager.get_t2i_cdn_base_url(), "https://legacy.example")
        self.assertEqual(
            manager.config["t2i_rendering"]["t2i_rendering_strategies"][0][
                "__template_key"
            ],
            "mainland",
        )

    def test_injected_default_round_does_not_override_older_global_cdn(self):
        manager = self.load({"t2i_cdn_base_url": "https://legacy-global.example"})
        self.assertTrue(ConfigMigrator(manager).migrate_legacy_configs())
        self.assertEqual(
            manager.get_t2i_cdn_base_url(), "https://legacy-global.example"
        )

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


if __name__ == "__main__":
    unittest.main()
