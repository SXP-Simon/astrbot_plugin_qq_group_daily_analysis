"""验证漫画风格配置、资源分组和按真实群会话轮换。"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.domain.value_objects.group_session import GroupSession
from src.infrastructure.analysis.analyzers.comic_analyzer import ComicStoryboardAnalyzer
from src.infrastructure.config import config_manager
from src.infrastructure.config.comic_style_rotation import ComicStyle, list_comic_rotation, reserve_comic_style, reset_comic_rotation
from src.infrastructure.config.config_validation import validate_config_for_save
from src.infrastructure.platform.template_preview.router import TemplatePreviewRouter
from src.shared.comic_presets import COMIC_PRESETS, DEFAULT_COMIC_STORYBOARD_PROMPT

ROOT = Path(__file__).resolve().parents[1]
STYLES = tuple(
    ComicStyle(key, COMIC_PRESETS[key].name, COMIC_PRESETS[key].prompt)
    for key in ("classic", "pixel_rpg", "scrapbook_diary")
)


def test_schema_and_grouped_preview_assets_share_catalog():
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    fields = schema["daily_comic"]["items"]["comic_styles"]
    assert fields["default"][0]["preset_id"] == "classic"
    assert fields["templates"]["style"]["items"]["preset_id"]["options"] == [*COMIC_PRESETS, "custom"]
    assert fields["templates"]["style"]["items"]["prompt_override"]["default"] == ""
    for key in COMIC_PRESETS:
        for name in ("thumbnail.webp", "preview.webp"):
            content = (ROOT / "assets" / "comic_previews" / key / name).read_bytes()
            assert content[:4] == b"RIFF" and content[8:12] == b"WEBP"


def test_style_selection_respects_legacy_role_and_empty_override(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager, "StarTools", Mock(get_data_dir=lambda _: tmp_path))
    manager = object.__new__(config_manager.ConfigManager)
    manager.config = {
        "daily_comic": {
            "comic_style_mode": "sequential",
            "comic_style_scope": "group",
            "comic_styles": [
                {"preset_id": "classic", "enable": False},
                {"preset_id": "pixel_rpg", "prompt_override": "修改后的像素分镜"},
                {"preset_id": "scrapbook_diary", "prompt_override": ""},
            ],
        }
    }
    a = GroupSession("instance-a", "123")
    b = GroupSession("instance-b", "123")
    assert manager.get_comic_character_storyboard_prompt({"storyboard_prompt": "旧角色正文"}, a) == "旧角色正文"
    assert list(tmp_path.iterdir()) == []
    assert manager.get_comic_character_storyboard_prompt(None, a) == "修改后的像素分镜"
    assert manager.get_comic_character_storyboard_prompt(None, b) == "修改后的像素分镜"
    assert manager.get_comic_character_storyboard_prompt(None, a) == COMIC_PRESETS["scrapbook_diary"].prompt
    manager.config["daily_comic"]["comic_styles"] = []
    assert manager.get_comic_character_storyboard_prompt(None, a) == DEFAULT_COMIC_STORYBOARD_PROMPT


def test_custom_style_requires_complete_text_and_joins_rotation(tmp_path, monkeypatch):
    monkeypatch.setattr(config_manager, "StarTools", Mock(get_data_dir=lambda _: tmp_path))
    custom = {"__template_key": "style", "preset_id": "custom", "name": "四格手绘"}
    config = {
        "daily_comic": {
            "comic_style_mode": "sequential",
            "comic_styles": [{"preset_id": "classic"}, custom],
        },
    }
    with pytest.raises(ValueError, match="第 2 个自定义风格请填写名称和分镜提示词"):
        validate_config_for_save(config)

    custom["prompt_override"] = "以四格手绘记录对话。"
    validate_config_for_save(config)
    manager = object.__new__(config_manager.ConfigManager)
    manager.config = config
    assert manager.get_comic_character_storyboard_prompt(None) == DEFAULT_COMIC_STORYBOARD_PROMPT
    assert manager.get_comic_character_storyboard_prompt(None) == custom["prompt_override"]


@pytest.mark.parametrize(
    "text",
    [
        '请用水彩画风。示例 {"scene": "水彩分镜"}',
        '请用水彩画风。示例 {"scene": "水彩分镜"}，话题：{chat_content}',
        '请用水彩画风。示例 {"scene": "水彩分镜"}，话题：${chat_content}',
        '请用水彩画风。示例 {{"scene": "水彩分镜"}}，话题：{chat_content}',
    ],
)
def test_custom_storyboard_preserves_json_and_receives_topics_once(text):
    analyzer = ComicStoryboardAnalyzer(context=Mock(), config_manager=Mock())
    result = analyzer.build_prompt([{"topic": "雨天露营", "detail": "大家搭了帐篷"}], text)
    assert '请用水彩画风。示例 {"scene": "水彩分镜"}' in result
    assert result.count("雨天露营") == 1
    assert "{chat_content}" not in result


def test_sequential_reservations_share_progress_across_threads(tmp_path):
    path = tmp_path / "progress.json"
    today = date(2026, 11, 9)
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(
            lambda _: reserve_comic_style(path, STYLES, "sequential", None, today),
            range(3),
        ))
    assert set(results) == set(STYLES)
    assert reserve_comic_style(path, STYLES, "sequential", None, today) == STYLES[0]


def test_reordered_custom_variants_start_a_new_sequence(tmp_path):
    path = tmp_path / "progress.json"
    today = date(2026, 11, 9)
    styles = (ComicStyle("classic", "同名", "正文甲"), ComicStyle("classic", "同名", "正文乙"))
    assert reserve_comic_style(path, styles, "sequential", None, today) == styles[0]
    assert reserve_comic_style(path, styles[::-1], "sequential", None, today) == styles[1]


def test_daily_modes_follow_calendar_without_double_advancing(tmp_path):
    sequential = tmp_path / "daily.json"
    first = date(2026, 11, 9)
    third = date(2026, 11, 11)
    assert reserve_comic_style(sequential, STYLES, "daily_sequential", None, first) == STYLES[0]
    assert reserve_comic_style(sequential, STYLES, "daily_sequential", None, third) == STYLES[2]
    assert reserve_comic_style(sequential, STYLES, "daily_sequential", None, third) == STYLES[2]
    daily_random = tmp_path / "daily-random.json"
    style = reserve_comic_style(daily_random, STYLES, "daily_random", None, first)
    assert reserve_comic_style(daily_random, STYLES, "daily_random", None, first) == style
    assert reserve_comic_style(daily_random, STYLES, "daily_random", None, third) in STYLES


def test_shuffle_visits_every_candidate_and_avoids_repeat_between_cycles(tmp_path):
    path = tmp_path / "shuffle.json"
    today = date(2026, 11, 9)
    styles = [reserve_comic_style(path, STYLES, "shuffle", None, today) for _ in range(6)]
    assert set(styles[:3]) == set(styles[3:]) == set(STYLES)
    assert styles[2] != styles[3]


@pytest.mark.parametrize("platform", ["aiocqhttp", "discord"])
def test_comic_style_directory_is_read_only_and_has_platform_fallback(platform):
    router = TemplatePreviewRouter()
    event = Mock()
    event.get_platform_name.return_value = platform
    event.get_self_id.return_value = "123"
    asyncio.run(router.view_comic_styles(event, ""))
    event.should_call_llm.assert_called_once_with(False)
    if platform == "aiocqhttp":
        nodes = event.chain_result.call_args.args[0][0].nodes
        assert len(nodes) == 5
        assert "第 1/4 页" in nodes[0].content[0].text
        assert "查看漫画风格 第 2 页" in nodes[0].content[0].text
    else:
        assert COMIC_PRESETS["classic"].name in event.plain_result.call_args.args[0]
        assert "查看漫画风格 序号" in event.plain_result.call_args.args[0]
        event.chain_result.assert_not_called()


def test_rotation_management_resets_only_the_requested_scope(tmp_path):
    path = tmp_path / "rotation.json"
    today = date(2026, 11, 9)
    first = GroupSession("bot-a", "123")
    other = GroupSession("bot-b", "123")
    for session in (first, other, None):
        assert reserve_comic_style(path, STYLES, "sequential", session, today) == STYLES[0]
    entries = list_comic_rotation(path)
    assert {entry["platform_id"] for entry in entries} == {"bot-a", "bot-b", None}
    assert all(entry["last_style_name"] == STYLES[0].name for entry in entries)
    reset_comic_rotation(path, first)
    assert reserve_comic_style(path, STYLES, "sequential", first, today) == STYLES[0]
    assert reserve_comic_style(path, STYLES, "sequential", other, today) == STYLES[1]
    assert reserve_comic_style(path, STYLES, "sequential", None, today) == STYLES[1]
    reset_comic_rotation(path)
    assert {entry["platform_id"] for entry in list_comic_rotation(path)} == {"bot-a", "bot-b"}
    reset_comic_rotation(path, all_scopes=True)
    assert list_comic_rotation(path) == []
