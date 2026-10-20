"""旧版合并转发开关的备份、失败回滚和幂等迁移回归。"""

from __future__ import annotations

import json
from copy import deepcopy
from unittest.mock import Mock

import pytest

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator


def stored_manager(config: dict) -> ConfigManager:
    """构建具有独立保存替身、不会执行其他升级过程的配置管理器。"""

    class StoredConfig(dict):
        """提供与宿主配置一致的保存入口。"""

        def save_config(self):
            """由实例上的保存替身替换。"""

    manager = object.__new__(ConfigManager)
    manager.config = StoredConfig(deepcopy(config))
    manager.config.save_config = Mock()
    return manager


@pytest.mark.parametrize("previous", [True, False])
def test_legacy_boolean_migration_backs_up_original_and_runs_once(tmp_path, previous):
    """布尔值先备份再保存，全选或空选含义保持不变，二次执行不写盘。"""
    original = {
        "basic": {"enable_merged_forward": previous, "merged_forward_timeout": 900},
        "unrelated": {"keep": ["原内容"]},
    }
    manager = stored_manager(original)
    tools = Mock()
    tools.get_data_dir.return_value = tmp_path
    migrator = ConfigMigrator(manager, tools)
    manager.config.save_config.side_effect = lambda: assert_backup_before_save(
        tmp_path, original
    )

    assert migrator.migrate_merged_forward_selection() is True
    assert manager.config["basic"] == {
        "enable_merged_forward": ["report", "wordcloud", "comic"] if previous else [],
        "merged_forward_timeout": 900,
    }
    assert manager.config["unrelated"] == original["unrelated"]
    assert migrator.migrate_merged_forward_selection() is False
    manager.config.save_config.assert_called_once()
    assert len(list((tmp_path / "config_backups").glob("plugin_config_*.json"))) == 1


def assert_backup_before_save(tmp_path, original):
    """断言实际落盘前已经存在原始完整配置快照。"""
    backups = list((tmp_path / "config_backups").glob("plugin_config_*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8"))["config"] == original


@pytest.mark.parametrize("failure", ["backup", "save"])
@pytest.mark.parametrize("previous", [True, False])
def test_migration_failure_preserves_old_value_and_allows_retry(
    tmp_path, monkeypatch, failure, previous
):
    """备份失败不变更配置；保存异常恢复旧值，之后重试可成功。"""
    original = {"basic": {"enable_merged_forward": previous}, "other": {"keep": 1}}
    manager = stored_manager(original)
    tools = Mock()
    tools.get_data_dir.return_value = tmp_path
    migrator = ConfigMigrator(manager, tools)
    if failure == "backup":
        monkeypatch.setattr(
            migrator, "write_upgrade_config_backup", Mock(return_value=False)
        )
    else:
        manager.config.save_config.side_effect = OSError("磁盘已满")

    assert migrator.migrate_merged_forward_selection() is False
    assert manager.config == original
    if failure == "backup":
        manager.config.save_config.assert_not_called()
    else:
        manager.config.save_config.assert_called_once()
    assert manager.get_merged_forward_types() == (
        ["report", "wordcloud", "comic"] if previous else []
    )

    manager.config.save_config.reset_mock(side_effect=True)
    assert ConfigMigrator(manager, tools).migrate_merged_forward_selection() is True
    manager.config.save_config.assert_called_once()


@pytest.mark.parametrize(
    "basic",
    [
        {},
        None,
        "invalid",
        [],
        {"enable_merged_forward": []},
        {"enable_merged_forward": ["comic"]},
        {"enable_merged_forward": 1},
        {"enable_merged_forward": "true"},
        {"enable_merged_forward": ["invalid"]},
    ],
)
def test_non_boolean_config_does_not_mutate_or_create_backup(tmp_path, basic):
    """新版配置、缺省和损坏配置保持原样，不触发迁移副作用。"""
    manager = stored_manager({"basic": basic})
    original = deepcopy(manager.config)
    tools = Mock()
    tools.get_data_dir.return_value = tmp_path

    assert ConfigMigrator(manager, tools).migrate_merged_forward_selection() is False
    assert manager.config == original
    manager.config.save_config.assert_not_called()
    tools.get_data_dir.assert_not_called()
    assert not (tmp_path / "config_backups").exists()
