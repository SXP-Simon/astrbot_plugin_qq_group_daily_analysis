"""按插件配置声明校验 WebUI 保存数据，不改写字段或丢弃扩展配置。"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from string import Formatter, Template
from typing import TYPE_CHECKING

from ...shared.comic_presets import COMIC_PRESETS
from ...shared.type_guards import is_object_list, is_string_mapping

if TYPE_CHECKING:
    from collections.abc import Mapping


def validate_config_for_save(
    config: Mapping[str, object], previous: Mapping[str, object] | None = None
) -> None:
    """校验已声明字段的类型、范围和嵌套结构。

    Args:
        config: 尚未写入运行中配置的保存请求。
        previous: 当前配置，允许原样保留升级前已生效的提示词。

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

    prompt_schema = schema.get("prompts")
    if is_string_mapping(prompt_schema):
        _validate_prompt_schemes(
            config.get("prompts"), (previous or {}).get("prompts"), prompt_schema
        )


def _validate_prompt_schemes(
    prompts: object, previous: object, schema: Mapping[str, object]
) -> None:
    """检查分析提示词方案，并确认单选结果与分析器读取的正文一致。

    Args:
        prompts: 待保存的提示词分组。
        previous: 当前已生效的提示词分组。
        schema: 提示词的配置声明。

    Raises:
        ValueError: 方案或提示词变量不合法。
    """
    groups = schema.get("items")
    if not is_string_mapping(prompts) or not is_string_mapping(groups):
        return
    for group_key, group in prompts.items():
        definition = groups.get(group_key)
        if not is_string_mapping(group) or not is_string_mapping(definition):
            continue
        fields = definition.get("items")
        if not is_string_mapping(fields):
            continue
        old_group = previous.get(group_key) if is_string_mapping(previous) else None
        old_group = old_group if is_string_mapping(old_group) else {}
        for key, field in fields.items():
            if not is_string_mapping(field):
                continue
            variables = field.get("prompt_variables")
            if not is_string_mapping(variables):
                continue
            schemes_key = f"{key}_schemes"
            current = group.get(key, field.get("default"))
            old_current = old_group.get(key, field.get("default"))
            rows = group.get(schemes_key, [])
            old_rows = old_group.get(schemes_key, [])
            if current == old_current and rows == old_rows:
                continue
            label = field.get("description") or key
            if not isinstance(current, str) or not is_object_list(rows):
                raise ValueError(f"{label}的正文或方案格式有误")
            saved: dict[str | None, object] = {}
            if is_object_list(old_rows):
                for row in old_rows:
                    if is_string_mapping(row):
                        name = row.get("name")
                        if name is None or isinstance(name, str):
                            saved[name] = (
                                old_current
                                if row.get("selected") is True
                                else row.get("text")
                            )
            selected: list[str] = []
            changed: list[tuple[str, str]] = []
            names: set[str | None] = set()
            for index, row in enumerate(rows):
                if not is_string_mapping(row):
                    raise ValueError(f"{label}第 {index + 1} 项必须是方案")
                name, body, active = (
                    row.get("name"),
                    row.get("text"),
                    row.get("selected"),
                )
                if (
                    "name" not in row
                    or (name is None) != (index == 0)
                    or (
                        name is not None
                        and (not isinstance(name, str) or not name.strip())
                    )
                    or not isinstance(body, str)
                    or not isinstance(active, bool)
                ):
                    raise ValueError(
                        f"{label}第 {index + 1} 项方案的名称、正文或选中状态有误"
                    )
                if name in names:
                    raise ValueError(f"{label}的自定义方案名称不能重复")
                names.add(name)
                if active:
                    selected.append(body)
                if name is None:
                    if body != saved.get(None, old_current):
                        raise ValueError(f"{label}的原有配置不能覆盖，请新建自定义方案")
                elif body != saved.get(name):
                    changed.append((name, body))
            if rows and rows != old_rows and selected != [current]:
                raise ValueError(f"{label}必须选中一个方案，且正文与所选方案一致")
            if current != old_current and (not rows or rows == old_rows):
                changed.append(("当前配置", current))
            for name, body in changed:
                if not body.strip():
                    raise ValueError(f"{label} · {name}：请填写提示词正文")
                identifiers = set(Template(body).get_identifiers())
                missing = [
                    f"${{{variable}}}"
                    for variable, metadata in variables.items()
                    if is_string_mapping(metadata)
                    and metadata.get("required") is True
                    and variable not in identifiers
                ]
                unknown = [
                    f"${{{variable}}}"
                    for variable in sorted(identifiers - variables.keys())
                ]
                if missing:
                    raise ValueError(
                        f"{label} · {name}：请插入必填变量 {'、'.join(missing)}"
                    )
                if unknown:
                    raise ValueError(
                        f"{label} · {name}：不支持变量 {'、'.join(unknown)}"
                    )


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
    elif (
        kind == "text"
        and path.rsplit(".", 1)[-1] in ("prompt_override", "storyboard_prompt")
        and isinstance(value, str)
        and value.strip()
    ):
        if "$" in value:
            used = set(Template(value).get_identifiers())
        else:
            if re.search(
                r"\{(?:chat_content|topic_count|max_count)(?:!|:|\.|\[)", value
            ):
                raise ValueError(f"{label}请改用不带格式修饰的变量，便于检查和预览。")
            try:
                value.format(chat_content="", topic_count=0, max_count=0)
                used = {key for _, key, _, _ in Formatter().parse(value) if key}
            except (ValueError, KeyError, IndexError, AttributeError, TypeError):
                # 旧正文中的单层 JSON 花括号不参与变量替换。
                used = set(
                    re.findall(
                        r"(?<!\{)\{(chat_content|topic_count|max_count)\}(?!\})",
                        value,
                    )
                )
        if "max_count" in used:
            used.add("topic_count")
        missing = [
            f"${{{key}}}" for key in ("chat_content", "topic_count") if key not in used
        ]
        if missing:
            raise ValueError(f"{label}请插入必填变量 {'、'.join(missing)}")
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
        comic_style_names: set[str] = set()
        for index, item in enumerate(value):
            if kind == "template_list":
                if not is_string_mapping(item):
                    raise ValueError(f"{label}第 {index + 1} 项必须是配置对象")
                if path == "daily_comic.comic_styles":
                    preset_id, alias, prompt = (
                        item.get("preset_id"),
                        item.get("name"),
                        item.get("prompt_override"),
                    )
                    if preset_id == "custom" and any(
                        not isinstance(text, str) or not text.strip()
                        for text in (alias, prompt)
                    ):
                        raise ValueError(
                            f"{label}第 {index + 1} 个自定义风格请填写名称和分镜提示词"
                        )
                    preset = (
                        COMIC_PRESETS.get(preset_id)
                        if isinstance(preset_id, str)
                        else None
                    )
                    name = alias.strip() if isinstance(alias, str) else ""
                    if not name and preset:
                        name = preset.name
                    if name:
                        if name in comic_style_names:
                            raise ValueError(
                                f"{label}第 {index + 1} 个方案的名称「{name}」已使用，请更换名称"
                            )
                        comic_style_names.add(name)
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
