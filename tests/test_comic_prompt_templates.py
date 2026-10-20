"""内置漫画风格选择、自定义保留与角色继承回归测试。"""

import json
import re
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.infrastructure.analysis.analyzers.comic_analyzer import ComicStoryboardAnalyzer
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_migrator import ConfigMigrator
from src.shared.comic_prompts import (
    COMIC_PROMPT_PREVIEWS,
    COMIC_STORYBOARD_PROMPTS,
    DEFAULT_COMIC_STORYBOARD_PROMPT,
)


def test_catalog_contains_all_fourteen_builtin_styles_and_preview_whitelist():
    """固定目录覆盖全部风格，预览仅允许同名的本地 WebP 文件。"""
    expected_ids = [
        "classic",
        "scp_dossier",
        "noir_detective",
        "pixel_rpg",
        "cyberpunk_hud",
        "showa_kidan",
        "steampunk_blueprint",
        "alchemist_botanical",
        "wasteland_radio",
        "ukiyo_e",
        "golden_age_comic",
        "deep_sea_log",
        "phantom_thief",
        "scrapbook_diary",
    ]
    assert list(COMIC_STORYBOARD_PROMPTS) == expected_ids
    expected_previews = {key: f"{key}.webp" for key in expected_ids}
    assert expected_previews == COMIC_PROMPT_PREVIEWS


@pytest.mark.parametrize("template", COMIC_STORYBOARD_PROMPTS)
def test_builtin_prompt_keeps_runtime_placeholders_and_complete_scene_contract(
    template,
):
    """新增模板保留运行时变量与完整场景约束，不携带导出伪引用。"""
    prompt = COMIC_STORYBOARD_PROMPTS[template]
    assert set(re.findall(r"\$\{([^}]+)\}", prompt)) == {
        "topic_count",
        "chat_content",
    }
    assert "Panel 1" in prompt
    assert "Background Context" in prompt
    assert "scene" in prompt
    assert "JSON" in prompt
    assert "[cite:" not in prompt
    assert "Plaintext" not in prompt
    assert prompt.endswith(("。", "\n"))


def test_new_template_labels_follow_their_prompt_text():
    """手稿和深海模板的标题约定以实际输出正文为准。"""
    assert "PROJECT #1" in COMIC_STORYBOARD_PROMPTS["steampunk_blueprint"]
    assert "BLUEPRINT #" not in COMIC_STORYBOARD_PROMPTS["steampunk_blueprint"]
    assert "SONAR #1" in COMIC_STORYBOARD_PROMPTS["deep_sea_log"]
    assert "DEPTH #" not in COMIC_STORYBOARD_PROMPTS["deep_sea_log"]
    assert "便利贴对白、相纸白边标题" in COMIC_STORYBOARD_PROMPTS["scrapbook_diary"]


@pytest.mark.parametrize("template", COMIC_STORYBOARD_PROMPTS)
def test_selected_preset_reaches_analyzer_without_changing_custom(template):
    manager = object.__new__(ConfigManager)
    manager.config = {
        "prompts": {
            "comic_analysis_prompts": {
                "comic_storyboard_template": template,
                "comic_storyboard_prompt": "用户保留的自定义草稿",
            }
        },
    }
    before = deepcopy(manager.config)
    prompt = manager.get_comic_character_storyboard_prompt(None)
    analyzer = ComicStoryboardAnalyzer(Mock(), manager)
    rendered = analyzer.build_prompt(
        [{"topic": "排查故障", "detail": "仍在测试"}], prompt
    )
    assert prompt == COMIC_STORYBOARD_PROMPTS[template]
    assert "${topic_count}" not in rendered
    assert "${chat_content}" not in rendered
    assert "排查故障" in rendered and "仍在测试" in rendered
    assert "Panel 1" in rendered
    assert manager.config == before


@pytest.mark.parametrize("selection", [None, "custom", "unknown"])
def test_legacy_custom_and_unknown_selection_keep_user_text(selection):
    manager = object.__new__(ConfigManager)
    values = {"comic_storyboard_prompt": "我的模板 ${chat_content}"}
    if selection is not None:
        values["comic_storyboard_template"] = selection
    manager.config = {"prompts": {"comic_analysis_prompts": values}}
    assert manager.get_comic_storyboard_prompt() == "我的模板 ${chat_content}"


@pytest.mark.parametrize("custom", ["", "  ", None, 123])
def test_empty_or_invalid_custom_uses_classic(custom):
    manager = object.__new__(ConfigManager)
    manager.config = {
        "prompts": {
            "comic_analysis_prompts": {
                "comic_storyboard_template": "custom",
                "comic_storyboard_prompt": custom,
            }
        }
    }
    assert manager.get_comic_storyboard_prompt() == DEFAULT_COMIC_STORYBOARD_PROMPT


@pytest.mark.parametrize(
    "character",
    [
        None,
        {},
        {"storyboard_prompt": ""},
        {"storyboard_prompt": None},
    ],
)
def test_empty_character_prompts_inherit_global(character):
    manager = object.__new__(ConfigManager)
    manager.config = {
        "prompts": {
            "comic_analysis_prompts": {
                "comic_storyboard_template": "noir_detective",
            }
        }
    }
    assert (
        manager.get_comic_character_storyboard_prompt(character)
        == COMIC_STORYBOARD_PROMPTS["noir_detective"]
    )


@pytest.mark.parametrize("override", ["专属内容", DEFAULT_COMIC_STORYBOARD_PROMPT])
def test_real_character_override_wins_over_global_preset(override):
    manager = object.__new__(ConfigManager)
    manager.config = {
        "prompts": {
            "comic_analysis_prompts": {
                "comic_storyboard_template": "pixel_rpg",
            }
        }
    }
    assert (
        manager.get_comic_character_storyboard_prompt({"storyboard_prompt": override})
        == override.strip()
    )


def test_stock_prompt_inheritance_migration_runs_once_and_keeps_later_override(
    tmp_path,
):
    """升级仅清理一次旧默认文本，之后用户手动填写的原版全文不会再被忽略。"""

    class StoredConfig(dict):
        save_config = Mock()

    characters = [
        {"name": "旧默认", "storyboard_prompt": DEFAULT_COMIC_STORYBOARD_PROMPT},
        {"name": "自定义", "storyboard_prompt": "用户文本"},
        {"name": "继承", "storyboard_prompt": ""},
    ]
    manager = object.__new__(ConfigManager)
    manager.config = StoredConfig(
        {
            "daily_comic": {"comic_characters": characters},
            "prompts": {
                "comic_analysis_prompts": {
                    "comic_storyboard_template": "noir_detective"
                }
            },
        }
    )
    star_tools = Mock()
    star_tools.get_data_dir.return_value = tmp_path
    ConfigMigrator(manager, star_tools).migrate_comic_prompt_template_inheritance()
    assert characters[0]["storyboard_prompt"] == ""
    assert characters[1]["storyboard_prompt"] == "用户文本"
    assert characters[2]["storyboard_prompt"] == ""
    assert (
        manager.get_comic_character_storyboard_prompt(characters[0])
        == COMIC_STORYBOARD_PROMPTS["noir_detective"]
    )
    state_path = tmp_path / "comic_prompt_template_migration.json"
    assert json.loads(state_path.read_text(encoding="utf-8")) == {"completed": True}
    backup = next(
        (tmp_path / "config_backups").glob("comic_character_migration_*.json")
    )
    assert (
        json.loads(backup.read_text(encoding="utf-8"))["config"]["comic_characters"][0][
            "storyboard_prompt"
        ]
        == DEFAULT_COMIC_STORYBOARD_PROMPT
    )
    manager.config.save_config.assert_called_once()

    characters[0]["storyboard_prompt"] = DEFAULT_COMIC_STORYBOARD_PROMPT
    ConfigMigrator(manager, star_tools).migrate_comic_prompt_template_inheritance()
    assert characters[0]["storyboard_prompt"] == DEFAULT_COMIC_STORYBOARD_PROMPT
    assert (
        manager.get_comic_character_storyboard_prompt(characters[0])
        == DEFAULT_COMIC_STORYBOARD_PROMPT.strip()
    )
    manager.config.save_config.assert_called_once()


@pytest.mark.parametrize("failure", ["backup", "save"])
def test_inheritance_migration_failure_preserves_prompt_and_retries(
    tmp_path, monkeypatch, failure
):
    """备份或保存失败时保留原文和未完成状态，后续重载可安全重试。"""

    class StoredConfig(dict):
        save_config = Mock()

    character = {"storyboard_prompt": DEFAULT_COMIC_STORYBOARD_PROMPT}
    manager = object.__new__(ConfigManager)
    manager.config = StoredConfig({"daily_comic": {"comic_characters": [character]}})
    star_tools = Mock()
    star_tools.get_data_dir.return_value = tmp_path
    migrator = ConfigMigrator(manager, star_tools)
    if failure == "backup":
        monkeypatch.setattr(
            migrator, "write_comic_config_backup", Mock(return_value=False)
        )
    else:
        manager.config.save_config.side_effect = OSError("磁盘已满")
    migrator.migrate_comic_prompt_template_inheritance()
    assert character["storyboard_prompt"] == DEFAULT_COMIC_STORYBOARD_PROMPT
    assert not (tmp_path / "comic_prompt_template_migration.json").exists()
    manager.config.save_config.side_effect = None
    ConfigMigrator(manager, star_tools).migrate_comic_prompt_template_inheritance()
    assert character["storyboard_prompt"] == ""
    assert (tmp_path / "comic_prompt_template_migration.json").exists()


def test_empty_upgrade_is_marked_before_future_explicit_classic_prompt(tmp_path):
    """首次加载没有旧默认文本时也记录完成，避免以后误清用户手动输入。"""
    manager = object.__new__(ConfigManager)
    manager.config = {"daily_comic": {"comic_characters": []}}
    star_tools = Mock()
    star_tools.get_data_dir.return_value = tmp_path
    ConfigMigrator(manager, star_tools).migrate_comic_prompt_template_inheritance()
    character = {"storyboard_prompt": DEFAULT_COMIC_STORYBOARD_PROMPT}
    manager.config["daily_comic"]["comic_characters"].append(character)
    ConfigMigrator(manager, star_tools).migrate_comic_prompt_template_inheritance()
    assert character["storyboard_prompt"] == DEFAULT_COMIC_STORYBOARD_PROMPT


def test_first_migration_preserves_explicit_inheritance(tmp_path):
    character = {"name": "新角色", "storyboard_prompt": ""}
    manager = Mock()
    manager._get_group.return_value = {"comic_characters": [character]}
    manager.get_comic_storyboard_prompt.return_value = COMIC_STORYBOARD_PROMPTS[
        "pixel_rpg"
    ]
    star_tools = Mock()
    star_tools.get_data_dir.return_value = tmp_path
    ConfigMigrator(
        manager, star_tools=star_tools
    ).migrate_daily_comic_character_prompts()
    assert character["storyboard_prompt"] == ""
    manager.save_config.assert_not_called()


def test_catalog_matches_schema_and_reviewed_document():
    root = Path(__file__).parents[1]
    schema = json.loads((root / "_conf_schema.json").read_text(encoding="utf-8"))
    fields = schema["prompts"]["items"]["comic_analysis_prompts"]["items"]
    catalog = json.loads(
        (root / "src/shared/comic_prompt_templates.json").read_text(encoding="utf-8")
    )
    assert fields["comic_storyboard_template"]["options"] == [
        *COMIC_STORYBOARD_PROMPTS,
        "custom",
    ]
    assert fields["comic_storyboard_template"]["default"] == "custom"
    assert fields["comic_storyboard_template"]["labels"] == [
        *[entry["name"] for entry in catalog.values()],
        "自定义",
    ]
    assert (
        fields["comic_storyboard_prompt"]["default"] == DEFAULT_COMIC_STORYBOARD_PROMPT
    )
    prompts = re.findall(
        r"```text\n(.*?)\n```",
        (root / "docs/COMIC_PROMPT_TEMPLATES.md").read_text(encoding="utf-8"),
        re.S,
    )
    assert prompts == [
        COMIC_STORYBOARD_PROMPTS[key]
        for key in COMIC_STORYBOARD_PROMPTS
        if key != "classic"
    ]
