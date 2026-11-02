"""Typst 方案与旧渲染配置的共存契约。"""

from unittest.mock import Mock

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator
from src.infrastructure.config.rendering_config import parse_rendering_strategies


def test_typst_roundtrip_and_runtime_options():
    manager = object.__new__(ConfigManager)
    manager.config = {"t2i_rendering": {"t2i_rendering_strategies": [
        {"__template_key": "typst", "typst_width": 1000, "typst_ppi": 120,
         "timeout": 30000},
    ]}}
    plan = manager.get_t2i_rendering_strategy_config()[0]
    assert plan["render_service"] == "typst"
    assert parse_rendering_strategies([plan]) == [plan]
    runtime = manager.get_t2i_rendering_strategies()[0]
    assert runtime["typst_width"] == 1000
    assert runtime["typst_ppi"] == 120


@pytest.mark.parametrize("key,value", [("typst_width", 639), ("typst_width", True),
    ("typst_ppi", 289), ("typst_ppi", "144")])
def test_typst_rejects_invalid_options(key, value):
    with pytest.raises(ValueError):
        parse_rendering_strategies([{"__template_key": "typst", key: value}])


def test_typst_preserves_explicit_fallback_order():
    plans = parse_rendering_strategies([
        {"__template_key": "custom", "priority": 20},
        {"__template_key": "typst", "priority": 10},
        {"__template_key": "strategy", "priority": 30},
    ])
    assert [p["render_service"] for p in plans] == ["typst", "custom", "astrbot"]


def test_oversized_legacy_width_is_clamped_and_persisted():
    original = {"__template_key": "typst", "typst_width": 1920}
    assert parse_rendering_strategies([original])[0]["typst_width"] == 1280
    assert original["typst_width"] == 1920
    manager = object.__new__(ConfigManager)
    manager.config = {"t2i_rendering": {"t2i_rendering_strategies": [dict(original)]}}
    manager.save_config = Mock()
    migrator = ConfigMigrator(manager)
    assert migrator.migrate_legacy_configs()
    assert manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]["typst_width"] == 1280
    assert manager.get_t2i_rendering_strategies()[0]["typst_width"] == 1280
    assert not migrator.migrate_legacy_configs()
    manager.save_config.assert_called_once()
