"""Typst 方案与旧渲染配置的共存契约。"""

from unittest.mock import Mock

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator
from src.infrastructure.config.rendering_config import parse_rendering_strategies


def test_native_compile_defaults_to_thirty_seconds_and_preserves_explicit_value():
    plans = parse_rendering_strategies([
        {"__template_key": "typst"}, {"__template_key": "strategy"},
        {"__template_key": "typst", "timeout": 15000},
    ])
    assert [plan["timeout"] for plan in plans] == [30000, 20000, 15000]


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
    assert "typst_width" not in runtime
    assert "typst_ppi" not in runtime


@pytest.mark.parametrize("key,value", [("typst_width", 639), ("typst_width", True),
    ("typst_ppi", 289), ("typst_ppi", "144")])
def test_typst_ignores_removed_layout_options(key, value):
    plan = parse_rendering_strategies([{"__template_key": "typst", key: value}])[0]
    assert key not in plan


def test_typst_preserves_explicit_fallback_order():
    plans = parse_rendering_strategies([
        {"__template_key": "custom", "priority": 20},
        {"__template_key": "typst", "priority": 10},
        {"__template_key": "strategy", "priority": 30},
    ])
    assert [p["render_service"] for p in plans] == ["typst", "custom", "astrbot"]


def test_legacy_layout_options_are_removed_and_persisted():
    original = {"__template_key": "typst", "typst_width": 1920, "typst_ppi": 288}
    assert "typst_width" not in parse_rendering_strategies([original])[0]
    assert "typst_ppi" not in parse_rendering_strategies([original])[0]
    assert original["typst_width"] == 1920
    manager = object.__new__(ConfigManager)
    manager.config = {"t2i_rendering": {"t2i_rendering_strategies": [dict(original)]}}
    manager.save_config = Mock()
    migrator = ConfigMigrator(manager)
    assert migrator.migrate_legacy_configs()
    migrated = manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]
    assert "typst_width" not in migrated and "typst_ppi" not in migrated
    assert "typst_width" not in manager.get_t2i_rendering_strategies()[0]
    assert not migrator.migrate_legacy_configs()
    manager.save_config.assert_called_once()


@pytest.mark.parametrize("key,value", [("t2i_viewport_width", "invalid"), ("t2i_viewport_height", None)])
def test_native_runtime_never_reads_browser_layout(key, value):
    manager = object.__new__(ConfigManager)
    manager.config = {"t2i_rendering": {key: value, "t2i_rendering_strategies": [{"__template_key": "typst", "device_scale": "legacy", "request_timeout": "unused", "google_fonts": "unused", "gstatic": "unused"}]}}
    runtime = manager.get_t2i_rendering_strategies()[0]
    assert runtime["render_service"] == "typst"
    assert not {"full_page", "device_scale_factor_level", "viewport_width", "viewport_height", "request_timeout"}.intersection(runtime)


@pytest.mark.parametrize("ppi", [144, 180, 216])
def test_density_round_trips_into_native_runtime_only(ppi):
    manager = object.__new__(ConfigManager)
    manager.config = {"t2i_rendering": {"t2i_rendering_strategies": [
        {"__template_key": "typst", "raster_ppi": ppi},
        {"__template_key": "strategy", "raster_ppi": ppi},
    ]}}
    native, browser = manager.get_t2i_rendering_strategies()
    assert native["raster_ppi"] == ppi
    assert "raster_ppi" not in browser
    assert "typst_width" not in native and "viewport_width" not in native


@pytest.mark.parametrize("value", [72, 145, 217, 288, True, "216", None])
def test_invalid_density_is_rejected_before_rendering(value):
    with pytest.raises(ValueError, match="导出密度"):
        parse_rendering_strategies([{"__template_key": "typst", "raster_ppi": value}])
