import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.infrastructure.analysis.analyzers.topic_analyzer import TopicAnalyzer
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.config.config_validation import validate_config_for_save
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


def topic_config(text, schemes=None):
    group = {"topic_prompt": text}
    if schemes is not None:
        group["topic_prompt_schemes"] = schemes
    return {"prompts": {"topic_analysis_prompts": group}}


@pytest.mark.parametrize(
    ("group", "field", "required"),
    [
        ("topic_analysis_prompts", "topic_prompt", ("messages_text", "max_topics")),
        ("user_title_analysis_prompts", "user_title_prompt", ("users_text",)),
        (
            "golden_quote_analysis_prompts",
            "golden_quote_v2_prompt",
            ("messages_text", "max_golden_quotes"),
        ),
        ("quality_analysis_prompts", "quality_v2_prompt", ("messages_text",)),
        ("quality_analysis_prompts", "quality_summary_prompt", ("reviews_text",)),
    ],
)
def test_new_scheme_requires_declared_input(group, field, required):
    def config(text):
        return {
            "prompts": {
                group: {
                    field: "升级前的内容",
                    f"{field}_schemes": [
                        {"name": None, "text": "升级前的内容", "selected": True},
                        {"name": "新的方案", "text": text, "selected": False},
                    ],
                }
            }
        }

    previous = {"prompts": {group: {field: "升级前的内容"}}}
    valid = " ".join(f"${{{variable}}}" for variable in required)
    for variable in required:
        token = f"${{{variable}}}"
        with pytest.raises(ValueError, match=f"必填变量.*{variable}"):
            validate_config_for_save(config(valid.replace(token, f"${token}")), previous)
    validate_config_for_save(config(valid + '，示例 JSON {"a": 1}'), previous)
    with pytest.raises(ValueError, match="不支持变量"):
        validate_config_for_save(config(valid + " ${unknown_input}"), previous)


@pytest.mark.asyncio
async def test_save_and_reload_keep_original_and_switch_effective_prompt(tmp_path):
    original = "用户升级前编辑过的提示词"
    custom = "最多 ${max_topics} 个话题：${messages_text}"
    config_file = tmp_path / "config.json"
    manager = object.__new__(ConfigManager)
    manager.config = topic_config(original)
    manager.save_config = lambda: config_file.write_text(
        json.dumps(manager.config, ensure_ascii=False), encoding="utf-8"
    )
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    analyzer = TopicAnalyzer(None, manager)
    messages = [{"time": "20:01", "sender": "小林", "user_id": "10001", "content": "明晚测试"}]
    # 与原样升级前的配置一起提交其他设置，不应要求补写原正文。
    validate_config_for_save({**manager.config, "basic": {}}, manager.config)
    rows = [
        {"name": None, "text": original, "selected": False},
        {"name": "偏技术", "text": custom, "selected": True},
    ]
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"config": topic_config(custom, rows)})
        assert (await routes.api_save_config())["status_code"] == 200
        manager.config = json.loads(config_file.read_text(encoding="utf-8"))
        assert manager.config == topic_config(custom, rows)
        assert analyzer.build_prompt(messages).endswith("个话题：[20:01] [10001]: 明晚测试")

        # 模拟宿主纯文本编辑当前方案。之后切回原有配置时，保留外部编辑。
        external = "从宿主编辑过的自定义方案"
        manager.config["prompts"]["topic_analysis_prompts"]["topic_prompt"] = external
        restored_rows = [
            {**rows[0], "selected": True},
            {**rows[1], "selected": False, "text": external},
        ]
        request.json.return_value = {"config": topic_config(original, restored_rows)}
        assert (await routes.api_save_config())["status_code"] == 200
        assert json.loads(config_file.read_text(encoding="utf-8")) == topic_config(
            original, restored_rows
        )
        assert analyzer.build_prompt(messages) == original

        invalid_rows = [{**restored_rows[0], "selected": True}, {**restored_rows[1], "selected": True}]
        request.json.return_value = {"config": topic_config(original, invalid_rows)}
        assert (await routes.api_save_config())["status_code"] == 400
        assert manager.config == topic_config(original, restored_rows)

        manager.save_config = Mock(side_effect=OSError("磁盘不可写"))
        request.json.return_value = {"config": topic_config(external, [
            {**restored_rows[0], "selected": False},
            {**restored_rows[1], "selected": True},
        ])}
        assert (await routes.api_save_config())["status_code"] == 500
        manager.save_config.assert_called_once()
        assert manager.config == topic_config(original, restored_rows)
