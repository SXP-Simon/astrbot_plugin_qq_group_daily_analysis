"""按插件配置声明校验 WebUI 保存数据，不改写字段或丢弃扩展配置。"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

from ...shared.type_guards import is_object_list, is_string_mapping

if TYPE_CHECKING:
    from collections.abc import Mapping


def validate_config_for_save(config: Mapping[str, object]) -> None:
    """校验已声明字段的类型、范围和嵌套结构。

    Args:
        config: 尚未写入运行中配置的保存请求。

    Raises:
        ValueError: 字段不符合声明，错误包含具体字段位置。
        OSError: 无法读取插件配置声明。
    """
    schema: object = json.loads(
        (Path(__file__).resolve().parents[3] / "_conf_schema.json").read_text(
            encoding="utf-8"
        )
    )
    if not is_string_mapping(schema):
        raise ValueError("无法读取有效的配置声明，请重新加载插件")
    for key, field in schema.items():
        if key in config and is_string_mapping(field):
            if field.get("type") == "object" and not is_string_mapping(config[key]):
                raise ValueError(
                    f"{field.get('description') or key}（{key}）必须是配置对象"
                )
            _validate_field(config[key], field, key, config)


def _validate_field(
    value: object, field: Mapping[str, object], path: str, scope: Mapping[str, object]
) -> None:
    """递归校验单个字段，允许未声明的扩展键继续原样保存。

    Args:
        value: 配置字段原值。
        field: 配置声明中的类型和约束。
        path: 包含分组和条目序号的字段位置。
        scope: 当前层的同级值，供条件显示规则判断。

    Raises:
        ValueError: 当前字段或子字段格式不正确。
    """
    if value is None or field.get("invisible") or field.get("hidden"):
        return
    condition = field.get("condition")
    if is_string_mapping(condition):
        for key, expected in condition.items():
            actual: object = scope
            for part in key.split("."):
                actual = actual.get(part) if is_string_mapping(actual) else None
            if "." not in key and key not in scope:
                actual = next(
                    (
                        group[key]
                        for group in scope.values()
                        if is_string_mapping(group) and key in group
                    ),
                    None,
                )
            if is_object_list(expected):
                if actual not in expected:
                    return
            elif actual != expected:
                return
    label = f"{field.get('description') or path}（{path}）"
    kind = field.get("type")
    if kind in ("int", "float"):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, float) and not math.isfinite(value))
            or (kind == "int" and isinstance(value, float) and not value.is_integer())
        ):
            raise ValueError(
                f"{label}请填写有效的{'整数' if kind == 'int' else '数字'}"
            )
        for bound, message in (("min", "小于"), ("max", "大于")):
            limit = field.get(bound)
            if isinstance(limit, (int, float)) and (
                (bound == "min" and value < limit) or (bound == "max" and value > limit)
            ):
                raise ValueError(f"{label}不能{message} {limit}")
    elif kind == "bool" and not isinstance(value, bool):
        raise ValueError(f"{label}必须是开关值")
    elif kind in ("string", "text") and not isinstance(value, str):
        raise ValueError(f"{label}必须是文字")
    elif kind in ("string", "text") and path.endswith(".profile_mapping_config"):
        if isinstance(value, str) and value.strip():
            try:
                mapping: object = json.loads(value)
                json.dumps(mapping, allow_nan=False)
            except ValueError as exc:
                raise ValueError(f"{label}请填写有效的 JSON 对象") from exc
            if not is_string_mapping(mapping):
                raise ValueError(f"{label}请填写有效的 JSON 对象")
    elif kind == "object":
        if not is_string_mapping(value):
            raise ValueError(f"{label}必须是配置对象")
        items = field.get("items")
        if is_string_mapping(items):
            for key, child in items.items():
                if key in value and is_string_mapping(child):
                    _validate_field(
                        value[key], child, f"{path}.{key}", {**scope, **value}
                    )
    elif kind in ("list", "template_list"):
        if not is_object_list(value):
            raise ValueError(f"{label}必须是列表")
        templates = field.get("templates")
        for index, item in enumerate(value):
            if kind == "template_list":
                if not is_string_mapping(item):
                    raise ValueError(f"{label}第 {index + 1} 项必须是配置对象")
                if is_string_mapping(templates) and templates:
                    key = item.get("__template_key")
                    if key is None and len(templates) == 1:
                        key = next(iter(templates))
                    template = templates.get(key) if isinstance(key, str) else None
                    if not is_string_mapping(template):
                        raise ValueError(
                            f"{label}第 {index + 1} 项请选择有效的方案类型"
                        )
                    _validate_field(
                        item,
                        {"type": "object", "items": template.get("items", {})},
                        f"{path}[{index + 1}]",
                        item,
                    )
    elif kind == "file" and not (
        isinstance(value, str)
        or (is_object_list(value) and all(isinstance(item, str) for item in value))
    ):
        raise ValueError(f"{label}必须是文件路径或路径列表")
    options = field.get("options")
    # 资源地址及模板名称允许自定义，不用静态预设限制用户已有配置。
    if (
        is_object_list(options)
        and options
        and path.rsplit(".", 1)[-1] not in ("cdn_base_url", "google_fonts", "gstatic")
        and "report_template" not in path.rsplit(".", 1)[-1]
    ):
        choices = value if kind == "list" and is_object_list(value) else [value]
        if any(choice not in options for choice in choices if choice != ""):
            raise ValueError(f"{label}请选择有效的预设选项")
