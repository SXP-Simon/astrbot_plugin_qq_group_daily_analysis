"""漫画模板轮换的持久化、隔离、并发及生成任务快照回归测试。"""

import asyncio
import json
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.services.comic_application_service import ComicApplicationService
from src.domain.value_objects.comic_template_rotation import (
    ComicTemplateRotationSettings,
)
from src.infrastructure.config.comic_template_rotation import ComicTemplateRotationStore
from src.infrastructure.config.config_manager import ConfigManager
from src.shared.comic_prompts import COMIC_STORYBOARD_PROMPTS

POOL = ("classic", "scp_dossier", "pixel_rpg")
TODAY = date(2026, 10, 17)


@pytest.fixture
def managers(monkeypatch, tmp_path):
    """创建共享一个状态目录、可自由配置的配置管理器。"""
    monkeypatch.setattr(
        "src.infrastructure.config.config_manager.StarTools.get_data_dir",
        lambda *_args: tmp_path,
    )
    monkeypatch.setattr(ConfigManager, "_get_comic_template_today", lambda _self: TODAY)

    def create(mode="sequential", scope="global", candidates=POOL, **group):
        manager = object.__new__(ConfigManager)
        manager.config = {
            "daily_comic": {
                "enable_daily_comic": True,
                "comic_template_mode": mode,
                "comic_template_scope": scope,
                "comic_template_candidates": list(candidates),
                **group,
            },
            "prompts": {
                "comic_analysis_prompts": {
                    "comic_storyboard_template": "pixel_rpg",
                    "comic_storyboard_prompt": "用户自定义 ${chat_content}",
                }
            },
        }
        return manager

    return create


def test_legacy_fixed_selection_never_creates_state_and_preserves_config(
    managers, tmp_path
):
    """旧配置保持固定模板，不为预览或生成创建额外状态文件。"""
    manager = managers("fixed")
    del manager.config["daily_comic"]["comic_template_mode"]
    before = deepcopy(manager.config)
    assert manager.select_comic_template().template_id == "pixel_rpg"
    status = manager.get_comic_template_rotation_status()
    assert status["current_template_id"] == "pixel_rpg"
    assert status["next_template_id"] == "pixel_rpg"
    assert not list(tmp_path.iterdir())
    assert manager.config == before


def test_sequential_progress_survives_restart_and_fixed_mode_pauses(managers):
    """每次生成向后预留，重建管理器或暂时固定不会丢失进度。"""
    manager = managers()
    assert manager.select_comic_template().template_id == POOL[0]
    assert managers("fixed").select_comic_template().template_id == "pixel_rpg"
    restarted = managers()
    assert (
        restarted.get_comic_template_rotation_status()["current_template_id"] == POOL[0]
    )
    assert [restarted.select_comic_template().template_id for _ in range(3)] == [
        POOL[1],
        POOL[2],
        POOL[0],
    ]


def test_daily_sequential_uses_calendar_delta_and_restart(managers, monkeypatch):
    """按自然日推进，跳过未生成的日期，重启后当日模板保持一致。"""
    manager = managers("daily_sequential")
    assert manager.select_comic_template().template_id == POOL[0]
    assert manager.select_comic_template().template_id == POOL[0]
    monkeypatch.setattr(
        ConfigManager, "_get_comic_template_today", lambda _self: date(2026, 10, 19)
    )
    restarted = managers("daily_sequential")
    assert restarted.select_comic_template().template_id == POOL[2]
    status = restarted.get_comic_template_rotation_status()
    assert status["current_template_id"] == POOL[2]
    assert status["next_template_id"] == POOL[0]


def test_daily_random_reuses_one_draw_per_day_across_restart(managers, monkeypatch):
    """每日随机选择持久化，同一天多群和重启都复用，次日重新抽取。"""
    choose = Mock(side_effect=[POOL[1], POOL[2]])
    monkeypatch.setattr(
        "src.infrastructure.config.comic_template_rotation.random.choice", choose
    )
    assert managers("daily_random").select_comic_template("1").template_id == POOL[1]
    assert managers("daily_random").select_comic_template("2").template_id == POOL[1]
    assert (
        managers("daily_random").get_comic_template_rotation_status()[
            "next_template_id"
        ]
        == POOL[1]
    )
    assert choose.call_count == 1
    monkeypatch.setattr(
        ConfigManager, "_get_comic_template_today", lambda _self: date(2026, 10, 18)
    )
    manager = managers("daily_random")
    assert manager.get_comic_template_rotation_status()["current_template_id"] is None
    assert choose.call_count == 1
    assert manager.select_comic_template().template_id == POOL[2]
    assert choose.call_count == 2


def test_random_per_generation_allows_repeats_and_is_not_advanced_by_status(
    managers, monkeypatch, tmp_path
):
    """独立随机允许连中，查询状态不会消耗随机数或创建文件。"""
    choose = Mock(return_value=POOL[1])
    monkeypatch.setattr(
        "src.infrastructure.config.comic_template_rotation.random.choice", choose
    )
    manager = managers("random")
    for _ in range(3):
        status = manager.get_comic_template_rotation_status()
        assert status["current_template_id"] is None
        assert status["next_template_id"] is None
    assert not list(tmp_path.iterdir())
    choose.assert_not_called()
    assert [manager.select_comic_template().template_id for _ in range(3)] == [
        POOL[1]
    ] * 3
    before = (tmp_path / "comic_template_rotation_state.json").read_bytes()
    assert manager.get_comic_template_rotation_status()["next_template_id"] is None
    assert (tmp_path / "comic_template_rotation_state.json").read_bytes() == before
    assert choose.call_count == 3


@pytest.mark.parametrize(
    "mode", ["sequential", "daily_sequential", "daily_random", "random", "shuffle"]
)
def test_status_before_selection_does_not_write_or_draw(
    mode, managers, tmp_path, monkeypatch
):
    """所有自动模式首次查询均为只读，不抽签也不落盘。"""
    choose = Mock(side_effect=AssertionError("状态查询不应抽签"))
    monkeypatch.setattr(
        "src.infrastructure.config.comic_template_rotation.random.choice", choose
    )
    monkeypatch.setattr(
        "src.infrastructure.config.comic_template_rotation.random.shuffle", choose
    )
    status = managers(mode).get_comic_template_rotation_status()
    assert status["initialized"] is False
    assert not list(tmp_path.iterdir())
    choose.assert_not_called()


def test_shuffle_uses_whole_pool_and_avoids_cycle_boundary_repeat(
    managers, monkeypatch
):
    """每轮每个候选仅用一次，跨轮边界也不连续重复。"""

    def reverse(items):
        items.reverse()

    shuffle = Mock(side_effect=reverse)
    monkeypatch.setattr(
        "src.infrastructure.config.comic_template_rotation.random.shuffle", shuffle
    )
    manager = managers("shuffle")
    first_cycle = [manager.select_comic_template().template_id for _ in POOL]
    assert set(first_cycle) == set(POOL)
    assert manager.get_comic_template_rotation_status()["next_template_id"] is None
    shuffle.assert_called_once()
    second_cycle = [
        managers("shuffle").select_comic_template().template_id for _ in POOL
    ]
    assert set(second_cycle) == set(POOL)
    assert first_cycle[-1] != second_cycle[0]
    assert shuffle.call_count == 2


def test_shuffle_boundary_repeat_is_swapped_and_single_candidate_is_supported(
    managers, monkeypatch
):
    """洗牌首项与上轮末项相同时交换，单候选列表仍可稳定循环。"""
    monkeypatch.setattr(
        "src.infrastructure.config.comic_template_rotation.random.shuffle",
        lambda _items: None,
    )
    manager = managers("shuffle", candidates=POOL[:2])
    assert [manager.select_comic_template().template_id for _ in range(5)] == [
        POOL[0],
        POOL[1],
        POOL[0],
        POOL[1],
        POOL[0],
    ]
    one = managers("shuffle", candidates=POOL[:1])
    assert [one.select_comic_template().template_id for _ in range(3)] == [POOL[0]] * 3


def test_group_scope_isolates_same_group_number_across_platforms_and_reset(managers):
    """完整 UMO 隔离平台/机器人，同群号不会共享进度，重置仅影响指定会话。"""
    manager = managers(scope="group")
    a, b = "qq-main:GroupMessage:123", "telegram-main:GroupMessage:123"
    assert manager.select_comic_template("123", a).template_id == POOL[0]
    assert manager.select_comic_template("123", a).template_id == POOL[1]
    assert manager.select_comic_template("123", b).template_id == POOL[0]
    status = manager.reset_comic_template_rotation("123", a)
    assert not status["initialized"]
    assert status["next_template_id"] == POOL[0]
    assert manager.select_comic_template("123", b).template_id == POOL[1]


@pytest.mark.parametrize(
    "umo", [None, "", "invalid", "qq:FriendMessage:123", "qq:GroupMessage:999"]
)
def test_group_scope_without_trustworthy_identity_falls_back_without_consumption(
    managers, tmp_path, umo
):
    """缺失完整会话时固定兜底，防止不同平台意外共享群号进度。"""
    manager = managers(scope="group")
    selection = manager.select_comic_template("123", umo)
    assert selection.mode == "fixed"
    assert selection.template_id == "pixel_rpg"
    assert manager.get_comic_template_rotation_status("123", umo)["warning"]
    with pytest.raises(ValueError):
        manager.reset_comic_template_rotation("123", umo)
    assert not list(tmp_path.iterdir())


def test_pool_changes_and_nonfixed_mode_changes_restart_progress(managers):
    """候选顺序或自动模式变更后使用新的首项，避免旧索引指向错误模板。"""
    manager = managers()
    manager.select_comic_template()
    changed = managers(candidates=POOL[::-1])
    assert not changed.get_comic_template_rotation_status()["initialized"]
    assert changed.select_comic_template().template_id == POOL[-1]
    assert managers("daily_sequential").select_comic_template().template_id == POOL[0]


@pytest.mark.parametrize(
    "content",
    [
        "{invalid",
        "[]",
        '{"version": 2, "states": {}}',
        '{"version": 1, "states": {"global": {"mode": "sequential", "candidates": ["classic", "scp_dossier", "pixel_rpg"], "current": {}, "cursor": false, "remaining": [{}]}}}',
    ],
)
def test_corrupt_state_recovers_on_first_generation_without_crashing(
    managers, tmp_path, content
):
    """损坏的文件或单条状态会在真实任务中重建，查询保持只读。"""
    path = tmp_path / "comic_template_rotation_state.json"
    path.write_text(content, encoding="utf-8")
    manager = managers()
    assert manager.get_comic_template_rotation_status()["initialized"] is False
    assert path.read_text(encoding="utf-8") == content
    assert manager.select_comic_template().template_id == POOL[0]
    assert (
        json.loads(path.read_text(encoding="utf-8"))["states"]["global"]["cursor"] == 1
    )


def test_corrupt_daily_anchor_and_shuffle_queue_recover(managers, tmp_path):
    """损坏日期和含不可哈希项的洗牌队列都被边界校验拒绝。"""
    path = tmp_path / "comic_template_rotation_state.json"
    manager = managers("daily_sequential")
    manager.select_comic_template()
    state = json.loads(path.read_text(encoding="utf-8"))
    state["states"]["global"]["anchor_date"] = "not-a-date"
    path.write_text(json.dumps(state), encoding="utf-8")
    assert manager.select_comic_template().template_id == POOL[0]
    shuffle = managers("shuffle")
    shuffle.select_comic_template()
    state = json.loads(path.read_text(encoding="utf-8"))
    state["states"]["global"]["remaining"] = [{}]
    path.write_text(json.dumps(state), encoding="utf-8")
    assert shuffle.select_comic_template().template_id in POOL


@pytest.mark.parametrize(
    "candidates", [[], ["unknown"], ["classic", "classic"], [{}], ["custom"]]
)
def test_invalid_runtime_pool_falls_back_fixed_with_warning(
    managers, tmp_path, candidates
):
    """宿主或手工配置绕过保存校验时安全固定兜底，不消耗进度。"""
    manager = managers(candidates=candidates)
    manager.config["prompts"]["comic_analysis_prompts"]["comic_storyboard_prompt"] = ""
    selection = manager.select_comic_template()
    assert selection.mode == "fixed"
    assert selection.template_id == "pixel_rpg"
    assert manager.get_comic_template_rotation_status()["warning"]
    assert not list(tmp_path.iterdir())


def test_custom_is_opt_in_and_uses_frozen_custom_text(managers):
    """自定义提示词仅在显式加入候选后参与，已选文本不受后续编辑影响。"""
    manager = managers(candidates=("custom", "classic"))
    selected = manager.select_comic_template()
    manager.config["prompts"]["comic_analysis_prompts"]["comic_storyboard_prompt"] = (
        "改后"
    )
    assert selected.template_id == "custom"
    assert selected.prompt == "用户自定义 ${chat_content}"
    assert manager.select_comic_template().prompt == COMIC_STORYBOARD_PROMPTS["classic"]


def test_concurrent_managers_reserve_exactly_one_slot_each(managers, tmp_path):
    """多个管理器/线程并发时共享路径锁，每次任务恰好消耗一个槽位。"""
    barrier = threading.Barrier(12)

    def reserve(_):
        manager = managers()
        barrier.wait(timeout=10)
        return manager.select_comic_template().template_id

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(reserve, range(12)))
    assert Counter(results) == dict.fromkeys(POOL, 4)
    assert (
        managers().get_comic_template_rotation_status()["next_template_id"] == POOL[0]
    )
    assert not list(tmp_path.glob("*.tmp"))


def test_character_override_bypasses_rotation_and_reference_snapshot_is_immutable(
    managers, tmp_path
):
    """角色专属提示词不消费模板进度，参考图和人格在任务开始时冻结。"""
    character = {
        "name": "亚托莉",
        "enable": True,
        "persona_id": "atri",
        "storyboard_prompt": "角色专属",
        "reference_images": ["a.png", "b.webp"],
    }
    manager = managers(comic_characters=[character])
    snapshot = manager.get_comic_generation_snapshot("123", "qq:GroupMessage:123")
    assert snapshot.template.character_override
    assert snapshot.template.prompt == "角色专属"
    assert snapshot.persona_id == "atri"
    character["reference_images"].append("new.png")
    character["persona_id"] = "changed"
    assert snapshot.reference_images == ("a.png", "b.webp")
    assert snapshot.persona_id == "atri"
    assert not list(tmp_path.iterdir())
    character["storyboard_prompt"] = ""
    assert manager.get_comic_generation_snapshot("123").template.template_id == POOL[0]


def test_concurrent_daily_character_snapshot_only_draws_once(
    managers, monkeypatch, tmp_path
):
    """移入工作线程后，每日角色的首次选择仍然原子化，避免多角色和临时文件竞争。"""
    characters = [{"name": name, "enable": True} for name in ("甲", "乙")]
    choice = Mock(side_effect=lambda pool: (time.sleep(0.02), pool[0])[1])
    monkeypatch.setattr(
        "src.infrastructure.config.config_manager.random.choice", choice
    )
    barrier = threading.Barrier(8)

    def snapshot(_):
        manager = managers(
            "fixed", comic_characters=characters, random_daily_comic_character=True
        )
        barrier.wait(timeout=10)
        return manager.get_comic_generation_snapshot("123").character_name

    with ThreadPoolExecutor(max_workers=8) as executor:
        result = list(executor.map(snapshot, range(8)))
    assert result == ["甲"] * 8
    choice.assert_called_once()
    assert not list(tmp_path.glob("*.tmp"))


def test_persist_failure_does_not_return_unreserved_style_or_corrupt_existing_state(
    managers, monkeypatch, tmp_path
):
    """原子替换失败时中止任务并清理临时文件，下次仍从未消耗的模板开始。"""
    manager = managers()
    manager.select_comic_template()
    path = tmp_path / "comic_template_rotation_state.json"
    before = path.read_bytes()
    original = Path.replace
    monkeypatch.setattr(Path, "replace", Mock(side_effect=OSError("磁盘不可写")))
    with pytest.raises(OSError, match="磁盘不可写"):
        manager.select_comic_template()
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
    monkeypatch.setattr(Path, "replace", original)
    assert manager.select_comic_template().template_id == POOL[1]


def test_read_failure_does_not_overwrite_other_scopes(managers, monkeypatch):
    """无法读取状态时中止任务，不能把读取错误当空记录覆盖其他群。"""
    manager = managers()
    monkeypatch.setattr(
        Path, "read_text", Mock(side_effect=PermissionError("无法读取"))
    )
    with pytest.raises(PermissionError):
        manager.select_comic_template()


def test_configured_timezone_is_used_for_template_calendar(monkeypatch):
    """模板日期遵守 TZ，与既有每日角色选择规则一致。"""
    observed = []

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            observed.append(str(tz))
            return cls(2026, 10, 17, 0, 5, tzinfo=tz)

    monkeypatch.setenv("TZ", "Asia/Shanghai")
    monkeypatch.setattr("src.infrastructure.config.config_manager.datetime", Clock)
    assert ConfigManager._get_comic_template_today() == TODAY
    assert observed == ["Asia/Shanghai"]


@pytest.mark.parametrize(
    "timezone", ["/invalid/absolute/path", ":invalid", "invalid/IANA"]
)
def test_invalid_timezone_falls_back_to_system_calendar(monkeypatch, timezone):
    """无效 TZ 包括绝对路径，均安全回退系统本地自然日。"""
    monkeypatch.setenv("TZ", timezone)
    assert (
        ConfigManager._get_comic_template_today() == datetime.now().astimezone().date()
    )


def test_failed_generation_consumes_one_selection_and_retries_reuse_snapshot(managers):
    """分镜失败仍消费槽位，绘图内部重试不改变任务模板或参考图。"""
    manager = managers(drawing_reference_image=["initial.png"])
    manager.get_enable_daily_comic = Mock(return_value=True)
    manager.get_drawing_backend = Mock(return_value="builtin")
    manager.get_drawing_provider_configs = Mock(return_value=[{"api_key": "test"}])
    manager.get_drawing_output_exception_retry_keywords = Mock(
        return_value=["需要重试"]
    )
    seen = []

    async def analyze(topics, umo, *, persona_id, prompt_template):
        assert topics == [] and umo is None and persona_id is None
        seen.append(prompt_template)
        if len(seen) == 1:
            return [], None
        manager.config["daily_comic"]["drawing_reference_image"] = ["changed.png"]
        return [{"scene": "已冻结的分镜"}], None

    attempts = []

    async def draw(prompt, **kwargs):
        attempts.append(prompt)
        assert kwargs["images_data"] == [(b"reference", "image/png")]
        assert (
            manager.get_comic_template_rotation_status()["next_template_id"] == POOL[2]
        )
        if len(attempts) == 1:
            assert prompt == "已冻结的分镜"
            return None, "需要重试"
        assert prompt == "重写后的分镜"
        assert kwargs["disable_retry"] is True
        return b"comic-output", None

    service = ComicApplicationService(
        SimpleNamespace(
            analyze_comic_storyboards=AsyncMock(side_effect=analyze),
            analyze_retry_prompt=AsyncMock(return_value="重写后的分镜"),
        ),
        SimpleNamespace(generate_image=AsyncMock(side_effect=draw)),
        manager,
        Path("unused"),
    )
    service._fetch_reference_image = AsyncMock(return_value=(b"reference", "image/png"))

    async def scenario():
        assert await service.generate_comic([], "123") == (None, None)
        assert await service.generate_comic([], "123") == (b"comic-output", None)

    asyncio.run(scenario())
    assert seen == [
        COMIC_STORYBOARD_PROMPTS[POOL[0]],
        COMIC_STORYBOARD_PROMPTS[POOL[1]],
    ]
    service._fetch_reference_image.assert_awaited_once_with("initial.png")
    assert attempts == ["已冻结的分镜", "重写后的分镜"]


def test_store_scope_key_rejects_group_context_mismatch():
    """平台身份和群号必须来自同一完整会话，禁止查询或重置其他作用域。"""
    settings = ComicTemplateRotationSettings("sequential", "group", POOL, "classic", "")
    assert (
        ComicTemplateRotationStore.scope_key(settings, "123", "qq:GroupMessage:999")
        == ""
    )
    assert (
        ComicTemplateRotationStore.scope_key(settings, "", "qq:GroupMessage:123")
        == "group:qq:GroupMessage:123"
    )
