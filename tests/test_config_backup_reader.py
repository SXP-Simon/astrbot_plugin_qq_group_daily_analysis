"""历史 JSON 备份不依赖当前 Schema，且只允许读取备份目录。"""

import json

import pytest

from src.infrastructure.config.config_backup_reader import ConfigBackupReader


def test_metadata_and_nested_values_are_read_without_current_schema(tmp_path):
    content = {"plugin_version": "v1.2.3", "backed_up_at": "2026-10-26T12:00:00", "config": {"removed_key": [False, 0, None, {"text": "line one\nline two"}]}}
    name = "plugin_config_old.json"
    (tmp_path / name).write_text(json.dumps(content), encoding="utf-8-sig")
    reader = ConfigBackupReader(tmp_path)
    detail = reader.read(name)
    assert detail["content"] == content
    assert detail["backup"]["kind"] == "upgrade"
    assert detail["backup"]["plugin_version"] == "v1.2.3"
    assert detail["backup"]["saved_at"] == content["backed_up_at"]
    assert reader.list_backups() == [detail["backup"]]


@pytest.mark.parametrize("document", [{"config": {"old": True}}, [1, False, None], "text", None])
def test_missing_metadata_is_not_guessed_from_filename(tmp_path, document):
    (tmp_path / "plugin_config_v9_20260101.json").write_text(json.dumps(document), encoding="utf-8")
    result = ConfigBackupReader(tmp_path).read("plugin_config_v9_20260101.json")
    assert result["content"] == document
    assert result["backup"]["plugin_version"] is None
    assert result["backup"]["saved_at"] is None


def test_comic_migration_and_corrupt_files_can_coexist(tmp_path):
    (tmp_path / "comic_character_migration_old.json").write_text('{"migrated_at":"2026-10-25T13:00:00","config":{"old":[1]}}', encoding="utf-8")
    (tmp_path / "broken.json").write_text("{broken", encoding="utf-8")
    items = {item["filename"]: item for item in ConfigBackupReader(tmp_path).list_backups()}
    assert items["comic_character_migration_old.json"]["kind"] == "comic_migration"
    assert items["comic_character_migration_old.json"]["saved_at"] == "2026-10-25T13:00:00"
    assert items["broken.json"]["error"]


@pytest.mark.parametrize("name", ["../secret.json", "..\\secret.json", "/tmp/secret.json", "", "other.txt"])
def test_path_traversal_is_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        ConfigBackupReader(tmp_path).read(name)


def test_links_size_and_non_json_numbers_are_rejected(tmp_path, monkeypatch):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    folder = tmp_path / "backups"
    folder.mkdir()
    try:
        (folder / "link.json").symlink_to(outside)
    except OSError:
        pass
    else:
        with pytest.raises(ValueError):
            ConfigBackupReader(folder).read("link.json")
    (folder / "big.json").write_text('"' + "x" * 32 + '"', encoding="utf-8")
    monkeypatch.setattr("src.infrastructure.config.config_backup_reader.MAX_BACKUP_BYTES", 16)
    with pytest.raises(ValueError, match="8 MiB"):
        ConfigBackupReader(folder).read("big.json")
    (folder / "nan.json").write_text("NaN", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        ConfigBackupReader(folder).read("nan.json")
