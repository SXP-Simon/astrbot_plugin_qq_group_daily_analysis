"""合并转发配置的缺省兼容、严格类型及宿主表单范围。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.infrastructure.config.config_manager import ConfigManager


def manager_with_basic(basic: object) -> ConfigManager:
    """构建不执行迁移和写盘的配置读取器。"""
    manager = object.__new__(ConfigManager)
    manager.config = {"basic": basic}
    return manager


@pytest.mark.parametrize("basic", [{}, None, [], "invalid"])
def test_missing_or_invalid_group_preserves_previous_delivery(basic: object):
    """旧配置及损坏分组均默认关闭合并转发，使用有限等待兜底。"""
    manager = manager_with_basic(basic)
    before = deepcopy(manager.config)

    assert manager.get_enable_merged_forward() is False
    assert manager.get_merged_forward_types() == []
    assert manager.get_merged_forward_timeout() == 600
    assert manager.config == before


@pytest.mark.parametrize("enabled", [False, True])
def test_legacy_merge_switch_preserves_original_meaning(enabled: bool):
    """旧版布尔值保持全选或空选语义，无需读操作写盘。"""
    manager = manager_with_basic({"enable_merged_forward": enabled})
    before = deepcopy(manager.config)

    assert manager.get_enable_merged_forward() is enabled
    assert manager.get_merged_forward_types() == (
        ["report", "wordcloud", "comic"] if enabled else []
    )
    assert manager.config == before


@pytest.mark.parametrize(
    "enabled",
    [
        "false",
        "true",
        0,
        1,
        None,
        {},
        ("report",),
        ["unknown"],
        ["report", "unknown"],
        ["report", "report"],
        [True],
        [False],
        [1],
        [None],
        [[]],
        [{}],
    ],
)
def test_invalid_merge_selection_cannot_enable_forwarding(enabled: object):
    """非法类型、未知结果和重复选项均不能意外启用合并转发。"""
    manager = manager_with_basic({"enable_merged_forward": enabled})
    before = deepcopy(manager.config)

    assert manager.get_enable_merged_forward() is False
    assert manager.get_merged_forward_types() == []
    assert manager.config == before


@pytest.mark.parametrize(
    "selected",
    [
        [],
        ["report"],
        ["wordcloud"],
        ["comic"],
        ["report", "wordcloud"],
        ["report", "comic"],
        ["wordcloud", "comic"],
        ["report", "wordcloud", "comic"],
        ["comic", "report"],
    ],
)
def test_merge_selection_returns_independent_canonical_copy(selected: list[str]):
    """任意组合保留选中语义，返回列表独立于原始配置。"""
    manager = manager_with_basic({"enable_merged_forward": selected})
    before = deepcopy(manager.config)
    expected = [kind for kind in ("report", "wordcloud", "comic") if kind in selected]

    assert manager.get_enable_merged_forward() is bool(selected)
    result = manager.get_merged_forward_types()
    assert result == expected
    result.append("comic")
    assert manager.get_merged_forward_types() == expected
    assert manager.config == before


@pytest.mark.parametrize("timeout", [10, 11, 600, 3599, 3600])
def test_merge_timeout_accepts_bounded_integer_seconds(timeout: int):
    """边界与区间内整数保持原值，不将滑块步长当作输入限制。"""
    manager = manager_with_basic({"merged_forward_timeout": timeout})

    assert manager.get_merged_forward_timeout() == timeout


@pytest.mark.parametrize(
    "timeout", [0, -1, 9, 3601, "600", 600.0, True, False, None, [], {}]
)
def test_invalid_merge_timeout_uses_safe_default_without_mutating(timeout: object):
    """错误类型与越界输入回退默认值，保留原始配置供管理员修复。"""
    manager = manager_with_basic({"merged_forward_timeout": timeout})
    before = deepcopy(manager.config)

    assert manager.get_merged_forward_timeout() == 600
    assert manager.config == before


def test_merge_schema_and_runtime_defaults_match():
    """AstrBot 和动态 WebUI 使用相同多选项、默认值及超时范围。"""
    schema_path = Path(__file__).resolve().parents[1] / "_conf_schema.json"
    basic_items = json.loads(schema_path.read_text(encoding="utf-8"))["basic"]["items"]
    switch = basic_items["enable_merged_forward"]
    timeout = basic_items["merged_forward_timeout"]
    manager = manager_with_basic({})

    assert switch["type"] == "list"
    assert switch["default"] == manager.get_merged_forward_types() == []
    assert switch["options"] == ["report", "wordcloud", "comic"]
    assert switch["labels"] == ["分析报告", "词云", "漫画"]
    assert timeout["type"] == "int"
    assert timeout["default"] == manager.get_merged_forward_timeout()
    assert (timeout["min"], timeout["max"]) == (10, 3600)
    assert timeout["slider"] == {"min": 10, "max": 3600, "step": 10}
    assert "condition" not in timeout
