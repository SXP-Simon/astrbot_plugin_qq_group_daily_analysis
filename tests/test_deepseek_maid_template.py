import base64
import json
import re
from pathlib import Path

import pytest

from src.infrastructure.reporting.templates import HTMLTemplates
from test_template_section_conditional_rendering import MockConfigManager


def test_maid_theme_registered_in_all_selection_entry_points():
    """检查内置名称、配置选择器和前端画廊采用同一主题标识。"""
    root = Path(__file__).resolve().parents[1]
    templates = HTMLTemplates(MockConfigManager("deepseek_maid"))
    item = next(t for t in templates.get_available_templates() if t["id"] == "deepseek_maid")
    assert item["has_image"] and item["has_html"]
    assert not item["is_custom"]
    schema = json.loads((root / "_conf_schema.json").read_text(encoding="utf-8"))
    assert "deepseek_maid" in schema["basic"]["items"]["report_template"]["options"]
    frontend = (root / "dashboard/src/entities/report/model/templates.ts").read_text(encoding="utf-8")
    assert 'key: "deepseek_maid"' in frontend
    assert 'id: "deepseek_maid"' in frontend


@pytest.mark.parametrize("hide_names", [False, True])
def test_maid_identity_visibility_and_plain_text_escaping(hide_names):
    """隐私模式不泄露姓名，昵称和金句中的 HTML 保持普通文本。"""
    templates = HTMLTemplates(MockConfigManager("deepseek_maid"))
    marker = "秘密昵称"
    portraits = templates.render_template(
        "user_title_item.html",
        template_theme="deepseek_maid",
        hide_user_names=hide_names,
        titles=[{"name": marker + "<script>x</script>", "title": "热心群友", "mbti": "INTP", "reason": "认真参与讨论"}],
    )
    quotes = templates.render_template(
        "quote_item.html",
        template_theme="deepseek_maid",
        hide_user_names=hide_names,
        quotes=[{"sender": marker, "content": "<script>alert(1)</script> & 一个普通的群聊金句", "reason": ""}],
    )
    assert portraits and quotes
    assert "<script>" not in portraits + quotes
    assert "&lt;script&gt;" in quotes
    if hide_names:
        assert marker not in portraits + quotes
        assert "匿名群友" in portraits + quotes
    else:
        assert marker in portraits + quotes


def test_maid_character_is_self_contained_and_has_all_face_layers():
    """原角色图层与完整扣盆造型均内嵌有效 PNG，不依赖远程图片。"""
    templates = HTMLTemplates(MockConfigManager("deepseek_maid"))
    character = templates.render_template(
        "image_template.html", template_theme="deepseek_maid",
        current_date="2026年10月3日", current_datetime="2026-10-03 12:00:00",
        message_count=10, participant_count=2, total_characters=100, emoji_count=3,
        most_active_period="12:00", total_tokens=0, prompt_tokens=0, completion_tokens=0,
    )
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/infrastructure/reporting/templates/deepseek_maid/inline_assets.html").read_text(encoding="utf-8")
    layers = re.findall(r'href="data:image/png;base64,([^"]+)"', source)
    assert len(layers) == 7
    assert all(base64.b64decode(layer).startswith(b"\x89PNG\r\n\x1a\n") for layer in layers)
    assert "https://" not in source
    assert "<script" not in source
    assert character.startswith("<!DOCTYPE html>")
    assert len(re.findall(r'href="data:image/png;base64,', character)) == 7
    assert 'href="#maid-pose-open"' in character


@pytest.mark.parametrize("message_count,pose,prop", [(0, "sleep", False), (10, "open", False), (1500, "basin", True)])
def test_maid_work_state_uses_message_count_without_inventing_stats(message_count, pose, prop):
    """角色的休眠和扣盆是固定小剧场，报告始终保留真实消息计数。"""
    templates = HTMLTemplates(MockConfigManager("deepseek_maid"))
    output = templates.render_template(
        "image_template.html", template_theme="deepseek_maid",
        current_date="2026年10月3日", current_datetime="2026-10-03 12:00:00",
        message_count=message_count, participant_count=2, total_characters=100,
        emoji_count=3, most_active_period="12:00", total_tokens=0,
        prompt_tokens=0, completion_tokens=0,
    )
    hero = re.search(r'<header class="hero">(.*?)</header>', output, re.S).group(1)
    assert 'href="#maid-pose-' + pose + '"' in hero
    assert "{:,}".format(message_count) in output
    assert ('aria-label="扣着铁盆的鲸鱼女仆娘"' in hero) is prop


@pytest.mark.parametrize("total,prompt,completion", [(0, 0, 0), (3000, 2000, 1000), (123456789, 123456700, 89)])
def test_maid_rice_receipt_preserves_token_units_and_missing_data(total, prompt, completion):
    """饭票只显示已有 Token 数量，不虚构价格、米饭换算或缺失数据。"""
    templates = HTMLTemplates(MockConfigManager("deepseek_maid"))
    output = templates.render_template(
        "html_template.html", template_theme="deepseek_maid",
        current_date="2026年10月3日", current_datetime="2026-10-03 12:00:00",
        message_count=10, participant_count=2, total_characters=100,
        emoji_count=3, most_active_period="12:00", total_tokens=total,
        prompt_tokens=prompt, completion_tokens=completion,
    )
    assert 'data-meme="rice-tokens"' in output
    assert "Token 消耗" in output
    expected = "本次暂无 Token 消耗记录" if total == 0 else "{:,}".format(total)
    assert expected in output
    assert "人民币" not in output and "饱腹度" not in output
