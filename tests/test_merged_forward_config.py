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
    assert manager.get_merged_forward_timeout() == 600
    assert manager.config == before


@pytest.mark.parametrize("enabled", [False, True])
def test_merge_switch_accepts_only_actual_booleans(enabled: bool):
    """正式布尔值按原意读取。"""
    manager = manager_with_basic({"enable_merged_forward": enabled})

    assert manager.get_enable_merged_forward() is enabled


@pytest.mark.parametrize("enabled", ["false", "true", 0, 1, None, [], {}])
def test_invalid_merge_switch_cannot_enable_forwarding(enabled: object):
    """字符串和数字不能通过真值转换意外启用合并转发。"""
    manager = manager_with_basic({"enable_merged_forward": enabled})

    assert manager.get_enable_merged_forward() is False


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
    """AstrBot 和动态 WebUI 使用相同开关、超时范围及显示条件。"""
    schema_path = Path(__file__).resolve().parents[1] / "_conf_schema.json"
    basic_items = json.loads(schema_path.read_text(encoding="utf-8"))["basic"]["items"]
    switch = basic_items["enable_merged_forward"]
    timeout = basic_items["merged_forward_timeout"]
    manager = manager_with_basic({})

    assert switch["type"] == "bool"
    assert switch["default"] is manager.get_enable_merged_forward()
    assert timeout["type"] == "int"
    assert timeout["default"] == manager.get_merged_forward_timeout()
    assert (timeout["min"], timeout["max"]) == (10, 3600)
    assert timeout["slider"] == {"min": 10, "max": 3600, "step": 10}
    assert timeout["condition"] == {"enable_merged_forward": True}
