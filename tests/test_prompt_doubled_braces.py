"""旧版提示词残留的 {{ / }} 转义：默认值、模板升级与配置迁移。"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.infrastructure.config.config_migrator import ConfigMigrator
from src.utils.template_utils import (
    unescape_doubled_braces,
    upgrade_str_format_template,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[1]

# 对应版本 _conf_schema.json 中的原始默认值。
HISTORICAL_PROMPTS = json.loads(
    (PLUGIN_ROOT / "tests/data/historical_analysis_prompts.json").read_text(
        encoding="utf-8"
    )
)
LEGACY_TOPIC_PROMPT = HISTORICAL_PROMPTS["v5.9.0/topic_prompt"]


def _prompt_defaults():
    schema = json.loads((PLUGIN_ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    for group_key, group in schema["prompts"]["items"].items():
        for key, field in group["items"].items():
            if isinstance(field.get("default"), str):
                yield f"{group_key}.{key}", field["default"]


@pytest.mark.parametrize(("name", "default"), list(_prompt_defaults()))
def test_default_prompts_have_no_str_format_escapes(name, default):
    # string.Template 不处理 {{，残留会原样发给模型并被照抄成非法 JSON
    assert "{{" not in default, name
    assert "}}" not in default, name


@pytest.mark.parametrize(
    "template_key",
    ["v5.9.0/topic_prompt", "v6.0.1/quality_v2_prompt"],
)
def test_upgrade_restores_doubled_braces_in_dollar_template(template_key):
    template = HISTORICAL_PROMPTS[template_key]
    expected = template.replace("{{", "{").replace("}}", "}")

    assert upgrade_str_format_template(template) == (expected, True)
    assert upgrade_str_format_template(expected) == (expected, False)


@pytest.mark.parametrize(
    "template",
    [
        # 正常书写的 JSON，嵌套对象结尾的 }} 不能被改成 }
        '${messages_text}\n[{"a": {"b": 1}}]',
        '${messages_text}\n{"title": "x", "dimensions": [{"name": "a"}]}',
        # 没有大括号
        "${messages_text}",
        "",
        # 混用：存在单独的 {，说明不是转义模板
        '${messages_text}\n{{"a": 1}} {"b": 2}',
    ],
)
def test_unescape_leaves_normal_templates_untouched(template):
    assert unescape_doubled_braces(template) == (template, False)


def test_unescape_halves_nested_escaped_closing_braces():
    restored, changed = unescape_doubled_braces('${x}\n{{"a": {{"b": 1}}}}')

    assert changed is True
    assert restored == '${x}\n{"a": {"b": 1}}'


def test_str_format_template_upgrade_is_unchanged():
    template = HISTORICAL_PROMPTS["v4.9.11/topic_prompt"]
    expected = template.format(
        max_topics="${max_topics}", messages_text="${messages_text}"
    )

    assert upgrade_str_format_template(template) == (expected, True)
    assert upgrade_str_format_template(expected) == (expected, False)


def _migrator(prompts):
    config = {"prompts": prompts}
    cm = SimpleNamespace(
        get_group=lambda name: config.get(name, {}),
        save_config=Mock(),
    )

    def set_topic(value):
        config["prompts"]["topic_analysis_prompts"]["topic_prompt"] = value
        cm.save_config()

    cm.set_topic_analysis_prompt = set_topic
    migrator = object.__new__(ConfigMigrator)
    migrator.cm = cm
    return migrator, config, cm


def test_migration_cleans_saved_prompt_and_schemes():
    custom = '自定义方案 ${max_topics}\n[ {{"topic": "x"}} ]\n${messages_text}'
    migrator, config, cm = _migrator(
        {
            "topic_analysis_prompts": {
                "topic_prompt": LEGACY_TOPIC_PROMPT,
                "topic_prompt_schemes": [
                    {"name": None, "text": LEGACY_TOPIC_PROMPT, "selected": True},
                    {"name": "自定义", "text": custom, "selected": False},
                ],
            }
        }
    )

    changed = migrator.upgrade_config_item(
        "topic_analysis_prompts", "topic_prompt", cm.set_topic_analysis_prompt
    )

    group = config["prompts"]["topic_analysis_prompts"]
    assert changed is True
    assert group["topic_prompt"] == LEGACY_TOPIC_PROMPT.replace("{{", "{").replace(
        "}}", "}"
    )
    assert all("{{" not in row["text"] for row in group["topic_prompt_schemes"])
    assert group["topic_prompt_schemes"][1]["text"] == (
        '自定义方案 ${max_topics}\n[ {"topic": "x"} ]\n${messages_text}'
    )
    # 选中方案的正文与分析器读取的字段保持一致
    assert group["topic_prompt_schemes"][0]["text"] == group["topic_prompt"]
    assert cm.save_config.called


def test_migration_is_noop_for_clean_prompts():
    clean = HISTORICAL_PROMPTS["v5.9.1/topic_prompt"]
    migrator, config, cm = _migrator(
        {
            "topic_analysis_prompts": {
                "topic_prompt": clean,
                "topic_prompt_schemes": [
                    {"name": None, "text": clean, "selected": True}
                ],
            }
        }
    )

    changed = migrator.upgrade_config_item(
        "topic_analysis_prompts", "topic_prompt", cm.set_topic_analysis_prompt
    )

    assert changed is False
    assert config["prompts"]["topic_analysis_prompts"]["topic_prompt"] == clean
    cm.save_config.assert_not_called()
