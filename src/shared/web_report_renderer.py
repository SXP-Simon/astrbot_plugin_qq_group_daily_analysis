"""
网页日报渲染工具。

该模块只依赖纯 Python + Jinja2，供插件端和 Worker 端共用。
"""

from __future__ import annotations

import base64
import html
import re
from datetime import datetime
from typing import Any

from jinja2 import Environment

_MENTION_PATTERN = re.compile(r"\[(\d+)\]")
_TEMPLATE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def normalize_template_name(template_name: str | None) -> str | None:
    """校验模板名，阻止路径穿越。"""
    if not template_name:
        return None
    normalized = str(template_name).strip()
    if not normalized:
        return None
    if not _TEMPLATE_NAME_PATTERN.fullmatch(normalized):
        return None
    return normalized


def render_report_html(
    env: Environment,
    report_payload: dict[str, Any],
    document_template: str = "image_template.html",
    chart_template: str = "activity_chart.html",
) -> str:
    """根据结构化 payload 渲染完整 HTML。"""
    render_context = build_render_context(
        env, report_payload, chart_template=chart_template
    )
    return env.get_template(document_template).render(**render_context)


def build_render_context(
    env: Environment,
    report_payload: dict[str, Any],
    chart_template: str = "activity_chart.html",
) -> dict[str, Any]:
    """将结构化 payload 转为当前模板所需的渲染变量。"""
    created_at = _parse_created_at(report_payload.get("created_at"))
    statistics = report_payload.get("statistics", {})
    user_directory = _normalize_user_directory(report_payload.get("user_directory", {}))

    topics_html = env.get_template("topic_item.html").render(
        topics=_build_topics_payload(report_payload.get("topics", []), user_directory)
    )
    titles_html = env.get_template("user_title_item.html").render(
        titles=_build_user_titles_payload(
            report_payload.get("user_titles", []), user_directory
        )
    )
    quotes_html = env.get_template("quote_item.html").render(
        quotes=_build_quotes_payload(
            report_payload.get("golden_quotes", []), user_directory
        )
    )

    chart_data = _build_hourly_chart_data(statistics.get("hourly_activity", {}))
    hourly_chart_html = env.get_template(chart_template).render(chart_data=chart_data)

    chat_quality_html = ""
    chat_quality_review = report_payload.get("chat_quality_review")
    if chat_quality_review:
        chat_quality_html = env.get_template("chat_quality_item.html").render(
            **chat_quality_review
        )

    token_usage = statistics.get("token_usage", {}) or {}

    return {
        "current_date": created_at.strftime("%Y年%m月%d日"),
        "current_datetime": created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "message_count": _coerce_int(statistics.get("message_count")),
        "participant_count": _coerce_int(statistics.get("participant_count")),
        "total_characters": _coerce_int(statistics.get("total_characters")),
        "emoji_count": _coerce_int(statistics.get("emoji_count")),
        "most_active_period": statistics.get("most_active_period", "") or "",
        "topics_html": topics_html,
        "titles_html": titles_html,
        "quotes_html": quotes_html,
        "hourly_chart_html": hourly_chart_html,
        "chat_quality_html": chat_quality_html,
        "total_tokens": _coerce_int(token_usage.get("total_tokens")),
        "prompt_tokens": _coerce_int(token_usage.get("prompt_tokens")),
        "completion_tokens": _coerce_int(token_usage.get("completion_tokens")),
    }


def _build_topics_payload(
    topics: list[dict[str, Any]],
    user_directory: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rendered_topics = []
    for index, topic in enumerate(topics, start=1):
        contributors = topic.get("contributors", []) or []
        rendered_topics.append(
            {
                "index": index,
                "topic": {"topic": topic.get("topic", "") or ""},
                "contributors": "、".join(str(item) for item in contributors if item),
                "detail": _render_mentions(
                    topic.get("detail", "") or "", user_directory
                ),
            }
        )
    return rendered_topics


def _build_user_titles_payload(
    user_titles: list[dict[str, Any]],
    user_directory: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rendered_titles = []
    for title in user_titles:
        user_id = str(title.get("user_id", "") or "")
        user_info = user_directory.get(user_id, {})
        rendered_titles.append(
            {
                "name": title.get("name", "") or user_info.get("name", user_id),
                "title": title.get("title", "") or "",
                "mbti": title.get("mbti", "") or "",
                "reason": title.get("reason", "") or "",
                "avatar_data": user_info.get("avatar_data", _default_avatar_data()),
            }
        )
    return rendered_titles


def _build_quotes_payload(
    golden_quotes: list[dict[str, Any]],
    user_directory: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rendered_quotes = []
    for quote in golden_quotes:
        user_id = str(quote.get("user_id", "") or "")
        user_info = user_directory.get(user_id, {})
        rendered_quotes.append(
            {
                "content": quote.get("content", "") or "",
                "sender": quote.get("sender", "") or user_info.get("name", ""),
                "reason": _render_mentions(
                    quote.get("reason", "") or "",
                    user_directory,
                ),
                "avatar_url": user_info.get("avatar_data", _default_avatar_data())
                if user_id
                else None,
            }
        )
    return rendered_quotes


def _render_mentions(
    text: str,
    user_directory: dict[str, dict[str, str]],
) -> str:
    """将 [123456] 替换为受控 HTML 胶囊，其余内容全部转义。"""
    if not text:
        return ""

    result: list[str] = []
    last_end = 0

    for match in _MENTION_PATTERN.finditer(text):
        result.append(_escape_text_segment(text[last_end : match.start()]))

        user_id = match.group(1)
        user_info = user_directory.get(user_id, {})
        name = user_info.get("name") or user_id
        avatar_data = user_info.get("avatar_data") or _default_avatar_data()
        result.append(_build_user_capsule_html(name, avatar_data))
        last_end = match.end()

    result.append(_escape_text_segment(text[last_end:]))
    return "".join(result)


def _escape_text_segment(text: str) -> str:
    return html.escape(text, quote=False).replace("\n", "<br>")


def _build_user_capsule_html(name: str, avatar_data: str) -> str:
    capsule_style = (
        "display:inline-flex;align-items:center;background:rgba(0,0,0,0.05);"
        "padding:2px 6px 2px 2px;border-radius:12px;margin:0 2px;"
        "vertical-align:middle;border:1px solid rgba(0,0,0,0.1);text-decoration:none;"
    )
    img_style = (
        "width:18px;height:18px;border-radius:50%;margin-right:4px;display:block;"
    )
    name_style = "font-size:0.85em;color:inherit;font-weight:500;line-height:1;"

    return (
        f'<span class="user-capsule" style="{capsule_style}">'
        f'<img src="{html.escape(avatar_data, quote=True)}" style="{img_style}">'
        f'<span style="{name_style}">{html.escape(name)}</span>'
        "</span>"
    )


def _normalize_user_directory(
    user_directory: dict[str, Any],
) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for user_id, raw_info in (user_directory or {}).items():
        key = str(user_id)
        info = raw_info if isinstance(raw_info, dict) else {}
        normalized[key] = {
            "name": str(info.get("name", "") or key),
            "avatar_data": str(info.get("avatar_data", "") or _default_avatar_data()),
        }
    return normalized


def _build_hourly_chart_data(
    hourly_activity: dict[str, Any] | dict[int, Any],
) -> list[dict[str, Any]]:
    normalized_activity = {
        _coerce_int(hour): _coerce_int(count)
        for hour, count in (hourly_activity or {}).items()
    }
    max_activity = max(normalized_activity.values(), default=1)

    chart_data = []
    for hour in range(24):
        count = normalized_activity.get(hour, 0)
        percentage = round((count / max_activity) * 100, 1) if max_activity else 0.0
        chart_data.append({"hour": hour, "count": count, "percentage": percentage})
    return chart_data


def _parse_created_at(created_at: str | None) -> datetime:
    if created_at:
        try:
            return datetime.fromisoformat(created_at)
        except ValueError:
            pass
    return datetime.now()


def _coerce_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _default_avatar_data() -> str:
    svg = (
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="50" cy="50" r="50" fill="#ddd"/></svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{encoded}"
