"""会话配置前缀选择及宿主读取失败时的边界。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.infrastructure.platform.command_prefix import get_command_prefix


@pytest.mark.parametrize(
    "prefixes, expected",
    [
        (["/"], "/"),
        (["!", "/"], "!"),
        (["", "/"], ""),
        (["/", ""], "/"),
        ([None, 123, "！", "/"], "！"),
        (["分析 ", "/"], "分析 "),
        ([], ""),
        ([None], ""),
        (None, ""),
        ("/", ""),
    ],
)
def test_prefix_follows_host_order_and_preserves_empty(prefixes, expected):
    config = {"wake_prefix": prefixes, "admins_id": ["admin"]}
    context = SimpleNamespace(get_config=Mock(return_value=config))
    event = SimpleNamespace(unified_msg_origin="qq:GroupMessage:bound")
    assert get_command_prefix(context, event) == expected
    context.get_config.assert_called_once_with(umo=event.unified_msg_origin)
    assert config == {"wake_prefix": prefixes, "admins_id": ["admin"]}


@pytest.mark.parametrize("umo", [None, "", 123])
def test_missing_origin_does_not_read_unrelated_default_config(umo):
    context = SimpleNamespace(get_config=Mock(return_value={"wake_prefix": ["/"]}))
    assert get_command_prefix(context, SimpleNamespace(unified_msg_origin=umo)) == ""
    context.get_config.assert_not_called()


def test_missing_or_old_host_api_and_config_error_keep_bare_command():
    event = SimpleNamespace(unified_msg_origin="qq:GroupMessage:bound")
    assert get_command_prefix(None, event) == ""
    assert get_command_prefix(SimpleNamespace(), event) == ""
    context = SimpleNamespace(
        get_config=Mock(side_effect=RuntimeError("profile unavailable"))
    )
    assert get_command_prefix(context, event) == ""
    context.get_config.assert_called_once_with(umo=event.unified_msg_origin)


@pytest.mark.parametrize(
    "method_name",
    [
        "view_templates",
        "set_report_template",
        "set_output_format",
        "analysis_settings",
        "incremental_status",
    ],
)
def test_commands_keep_host_admin_permission_filter(method_name):
    # 测试环境的装饰器桩不保存权限元数据，直接检查真正注册到宿主的装饰器。
    import ast
    from pathlib import Path

    tree = ast.parse(
        (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    )
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == method_name
    )
    assert any(
        isinstance(decorator, ast.Call)
        and ast.unparse(decorator.func) == "filter.permission_type"
        and [ast.unparse(arg) for arg in decorator.args] == ["PermissionType.ADMIN"]
        for decorator in method.decorator_list
    )
