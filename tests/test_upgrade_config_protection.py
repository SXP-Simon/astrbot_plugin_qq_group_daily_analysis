"""升级归档顺序、资源迁移与正常保存后的快照新鲜度。"""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator, LEGACY_RENDERING_RESOURCE_KEYS


@pytest.fixture
def protection(tmp_path, monkeypatch):
    class Config(dict):
        first_deploy = False

        def save_config(self):
            events.append("save")
            (tmp_path / "active.json").write_text(json.dumps(self), encoding="utf-8")

    class Tools:
        @staticmethod
        def get_data_dir(_name):
            return tmp_path

    events = []
    monkeypatch.setattr("src.infrastructure.config.config_manager.StarTools", Tools)
    root = tmp_path / "plugin"
    root.mkdir()
    (root / "metadata.yaml").write_text("version: v2.0.0\n", encoding="utf-8")
    (root / "_conf_schema.json").write_text('{"t2i_rendering":{"type":"object","items":{}}}', encoding="utf-8")
    manager = object.__new__(ConfigManager)
    manager.StarTools = Tools
    manager.config = Config({"t2i_rendering": {"t2i_rendering_strategies": [{"__template_key": "mainland"}, {"cdn_base_url": "https://explicit.example", "priority": 30}]}})
    manager._get_plugin_root = lambda: root
    migrator = ConfigMigrator(manager, star_tools=Tools)
    manager._migrator = migrator
    for method in ("upgrade_prompt_templates", "migrate_daily_comic_character_references", "migrate_daily_comic_character_prompts", "migrate_legacy_comic_storyboard_prompts"):
        setattr(migrator, method, lambda *args: None)
    old = {"version": "v1.0.0", "schema_fingerprint": "old", "config": {"t2i_rendering": {"t2i_cdn_base_url": "https://legacy.example", "t2i_mainland_google_fonts": "https://old-fonts.example", "t2i_mainland_gstatic": "https://old-static.example"}, "unknown": {"old": [False, None]}}}
    state = tmp_path / "upgrade_protection_state.json"
    state.write_text(json.dumps(old), encoding="utf-8")
    return SimpleNamespace(manager=manager, migrator=migrator, state=state, old=old, events=events, directory=tmp_path)


def test_archives_old_snapshot_before_migration_and_only_fills_missing_fields(protection):
    p = protection
    original_save = p.manager.config.save_config

    def save_after_archive():
        backups = list((p.directory / "config_backups").glob("plugin_config_*.json"))
        assert len(backups) == 1
        assert json.loads(backups[0].read_text(encoding="utf-8"))["config"] == p.old["config"]
        assert json.loads(p.state.read_text(encoding="utf-8")) == p.old
        original_save()

    p.manager.config.save_config = save_after_archive
    p.migrator.run_all_migrations()
    plans = p.manager.config["t2i_rendering"]["t2i_rendering_strategies"]
    assert plans[0]["cdn_base_url"] == "https://legacy.example"
    assert plans[0]["google_fonts"] == "https://old-fonts.example"
    assert plans[0]["gstatic"] == "https://old-static.example"
    assert plans[1]["cdn_base_url"] == "https://explicit.example"
    assert [item["priority"] if "priority" in item else 10 for item in plans] == [10, 30]
    assert not set(LEGACY_RENDERING_RESOURCE_KEYS).intersection(p.manager.config["t2i_rendering"])
    state = json.loads(p.state.read_text(encoding="utf-8"))
    assert state["version"] == "v2.0.0"
    assert state["config"] == p.manager.config
    assert state["captured_at"]
    before = deepcopy(p.manager.config)
    p.migrator.run_all_migrations()
    assert p.manager.config == before
    assert len(list((p.directory / "config_backups").glob("*.json"))) == 1


def test_normal_save_refreshes_snapshot_and_failed_save_does_not(protection):
    p = protection
    p.migrator.run_all_migrations()
    p.manager._upgrade_tracking_active = True
    p.manager.config["basic"] = {"value": "latest"}
    p.manager.save_config()
    current = json.loads(p.state.read_text(encoding="utf-8"))
    assert current["config"]["basic"]["value"] == "latest"
    p.manager.config.save_config = Mock(side_effect=OSError("disk full"))
    p.manager.config["basic"]["value"] = "unsaved"
    with pytest.raises(OSError):
        p.manager.save_config()
    assert json.loads(p.state.read_text(encoding="utf-8")) == current


def test_missing_history_uses_defaults_and_reports_limitation(protection, caplog):
    p = protection
    p.state.unlink()
    p.migrator.run_all_migrations()
    assert p.manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]["google_fonts"] == "https://fonts.loli.net"
    assert "旧自定义地址和参考图无法自动恢复" in caplog.text


def test_archive_failure_keeps_previous_snapshot_and_does_not_migrate(protection):
    p = protection
    before = deepcopy(p.manager.config)
    p.manager._write_upgrade_config_backup = Mock(return_value=False)
    p.migrator.run_all_migrations()
    assert p.manager.config == before
    assert json.loads(p.state.read_text(encoding="utf-8")) == p.old
    assert p.events == []


def test_invalid_plan_does_not_replace_recoverable_baseline(protection):
    p = protection
    p.manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [{"priority": -1}]
    p.migrator.run_all_migrations()
    assert json.loads(p.state.read_text(encoding="utf-8")) == p.old


def test_normal_save_does_not_erase_pending_migration_source(protection, caplog):
    p = protection
    p.manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [{"priority": -1}]
    p.migrator.run_all_migrations()
    p.manager._upgrade_tracking_active = True
    p.manager.config["basic"] = {"value": "saved"}
    p.manager.save_config()
    assert json.loads((p.directory / "active.json").read_text(encoding="utf-8"))["basic"]["value"] == "saved"
    assert json.loads(p.state.read_text(encoding="utf-8")) == p.old
    assert "保护快照暂不替换" in caplog.text


@pytest.mark.parametrize("setter,value", [("set_report_template", "HatsuneMiku"), ("set_enable_analysis_reply", True), ("set_filter_bot_messages", False)])
def test_configuration_commands_use_the_same_snapshot_save_path(protection, setter, value):
    p = protection
    p.migrator.run_all_migrations()
    p.manager._upgrade_tracking_active = True
    getattr(p.manager, setter)(value)
    state = json.loads(p.state.read_text(encoding="utf-8"))
    assert state["config"] == p.manager.config
    assert state["config"] == json.loads((p.directory / "active.json").read_text(encoding="utf-8"))


def test_removed_comic_reference_field_is_migrated_from_snapshot(protection):
    p = protection
    source = p.directory / "files/daily_comic/drawing_reference_image/old.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"old-image")
    p.old["config"]["daily_comic"] = {"drawing_reference_image": [source.relative_to(p.directory).as_posix()]}
    p.state.write_text(json.dumps(p.old), encoding="utf-8")
    p.manager.config["daily_comic"] = {"comic_characters": []}
    del p.migrator.migrate_daily_comic_character_references
    p.migrator.run_all_migrations()
    group = p.manager.config["daily_comic"]
    assert "drawing_reference_image" not in group
    assert len(group["comic_characters"]) == 1
    assert (p.directory / group["comic_characters"][0]["reference_images"][0]).read_bytes() == b"old-image"
    assert "drawing_reference_image" not in json.loads(p.state.read_text(encoding="utf-8"))["config"]["daily_comic"]


def test_new_character_selection_is_not_overwritten_by_old_snapshot(protection):
    p = protection
    p.old["config"]["daily_comic"] = {"drawing_reference_image": ["old.png"]}
    p.state.write_text(json.dumps(p.old), encoding="utf-8")
    character = {"name": "current", "reference_images": ["current.png"]}
    p.manager.config["daily_comic"] = {"comic_characters": [character]}
    del p.migrator.migrate_daily_comic_character_references
    p.migrator.run_all_migrations()
    assert p.manager.config["daily_comic"]["comic_characters"] == [character]


def test_saved_order_is_stable_on_disk_and_in_protection_snapshot(protection):
    manager, migrator, state, tmp_path = protection.manager, protection.migrator, protection.state, protection.directory
    migrator.run_all_migrations()
    manager._upgrade_tracking_active = True
    manager.config["t2i_rendering"]["t2i_rendering_strategies"] = [
        {"__template_key": "custom", "name": "最后", "priority": 30, "future": {"keep": True}, "service_token": "secret"},
        {"name": "同级甲", "priority": 5},
        {"name": "同级乙", "priority": 5},
    ]
    manager.save_config()
    persisted = json.loads((tmp_path / "active.json").read_text(encoding="utf-8"))
    plans = persisted["t2i_rendering"]["t2i_rendering_strategies"]
    assert [item["name"] for item in plans] == ["同级甲", "同级乙", "最后"]
    assert plans[-1]["future"] == {"keep": True}
    assert plans[-1]["service_token"] == "secret"
    assert json.loads(state.read_text(encoding="utf-8"))["config"] == persisted
