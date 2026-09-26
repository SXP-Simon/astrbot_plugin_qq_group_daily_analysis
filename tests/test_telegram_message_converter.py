import pytest

from src.infrastructure.platform.adapters.telegram_message_converter import (
    TelegramMessageConverter,
)


def test_looks_like_markdown_report_detects_bold_and_headers():
    assert TelegramMessageConverter.looks_like_markdown_report("# 🎯 每日报告") is True
    assert TelegramMessageConverter.looks_like_markdown_report("## 📊 基础统计") is True
    assert TelegramMessageConverter.looks_like_markdown_report("包含 **加粗文本**") is True
    assert TelegramMessageConverter.looks_like_markdown_report("普通通知：任务已完成") is False
    assert (
        TelegramMessageConverter.looks_like_markdown_report(
            "C:/data/report_12345.png"
        )
        is False
    )


def test_escape_html_escapes_special_characters():
    raw = "<a> & <b> 'test' \"quote\""
    escaped = TelegramMessageConverter.escape_html(raw)
    assert "&amp;" in escaped
    assert "&lt;a&gt;" in escaped
    assert "&lt;b&gt;" in escaped
    assert "<" not in escaped
    assert ">" not in escaped


def test_to_telegram_html_converts_markdown_elements():
    md = """# 🎯 群聊日常分析报告
📅 2026年09月26日

## 📊 基础统计
- **消息总数**：100
- **参与人数**：10

## 🏆 群友称号
- **Alice** · INTJ
  > 活跃发言积极参与

## 💬 群圣经
- **1. "今天天气真好"** — Bob
  > 每日金句
"""
    html = TelegramMessageConverter.to_telegram_html(md)

    assert "<b>🎯 群聊日常分析报告</b>" in html
    assert "<b>📊 基础统计</b>\n" in html
    assert "• <b>消息总数</b>：100" in html
    assert "• <b>参与人数</b>：10" in html
    assert "<blockquote>活跃发言积极参与</blockquote>" in html
    assert "<b>1. &quot;今天天气真好&quot;</b> — Bob" in html or "<b>1. \"今天天气真好\"</b> — Bob" in html
    assert "<blockquote>每日金句</blockquote>" in html


def test_to_telegram_html_preserves_inline_code_without_interpreting_markdown():
    md = "这是代码 `**not_bold**` 和变量 `foo <bar>` 以及 **外部加粗**"
    html = TelegramMessageConverter.to_telegram_html(md)

    assert "<code>**not_bold**</code>" in html
    assert "<code>foo &lt;bar&gt;</code>" in html
    assert "<b>外部加粗</b>" in html


def test_strip_markdown_preserves_code_contents_and_removes_bold():
    md = "这是 `**literal**` 和 **加粗文字**"
    stripped = TelegramMessageConverter.strip_markdown(md)

    assert stripped == "这是 **literal** 和 加粗文字"


def test_format_forward_nodes_to_text_single_source_and_multi_source():
    # 单一来源节点（同名）不应产生重复的 [分析报告] 前缀
    single_source_nodes = [
        {"data": {"name": "分析报告", "content": "# 报告标题\n第一段"}},
        {"data": {"name": "分析报告", "content": "第二段内容"}},
    ]
    formatted_single = TelegramMessageConverter.format_forward_nodes_to_text(
        single_source_nodes
    )
    assert "[分析报告]" not in formatted_single
    assert "# 报告标题\n第一段\n\n第二段内容" == formatted_single

    # 多来源节点应保留各自来源标注
    multi_source_nodes = [
        {"data": {"name": "Alice", "content": "Alice 的发言"}},
        {"data": {"name": "Bob", "content": "Bob 的发言"}},
    ]
    formatted_multi = TelegramMessageConverter.format_forward_nodes_to_text(
        multi_source_nodes
    )
    assert "**[Alice]**\nAlice 的发言" in formatted_multi
    assert "**[Bob]**\nBob 的发言" in formatted_multi
