"""QQ Official Bot-specific Markdown report generation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ...utils.logger import logger


class QQOfficialMarkdownReportGenerator:
    """Generate QQ Official Markdown without changing other platform reports."""

    def __init__(
        self,
        config_manager: Any,
        html_templates: Any = None,
        render_semaphore: Any = None,
    ) -> None:
        self.config_manager = config_manager
        self.html_templates = html_templates
        self.render_semaphore = render_semaphore

    async def generate(
        self, analysis_result: dict, html_render_func=None
    ) -> tuple[str, str]:
        """Generate QQ Markdown and a URL-free Markdown fallback report."""
        fallback_report = self._generate_markdown_report(analysis_result)
        enabled = self.config_manager.get_qq_official_t2i_summary_dashboard_enabled()
        if not enabled or not callable(html_render_func) or self.html_templates is None:
            return fallback_report, fallback_report

        dashboard_url = await self._generate_summary_dashboard_url(
            analysis_result, html_render_func
        )
        if not dashboard_url:
            return fallback_report, fallback_report
        return (
            self._generate_markdown_report(
                analysis_result, summary_dashboard_url=dashboard_url
            ),
            fallback_report,
        )

    async def _generate_summary_dashboard_url(
        self, analysis_result: dict, html_render_func
    ) -> str | None:
        stats = analysis_result["statistics"]
        hourly_counts = self.get_hourly_counts(stats)
        max_count = max(hourly_counts, default=0)
        chart_data = [
            {
                "hour": f"{hour:02d}",
                "count": count,
                "height": (
                    max(2, round(count / max_count * 100))
                    if count > 0 and max_count > 0
                    else 0
                ),
            }
            for hour, count in enumerate(hourly_counts)
        ]
        metrics = [
            {"value": self.format_metric(stats.message_count), "label": "消息"},
            {"value": self.format_metric(stats.participant_count), "label": "参与"},
            {"value": self.format_metric(stats.total_characters), "label": "字符"},
            {"value": self.format_metric(stats.emoji_count), "label": "表情"},
            {
                "value": self.format_peak_period(stats.most_active_period),
                "label": "高峰",
            },
        ]
        html_content = self.html_templates.render_platform_template(
            "qq_official",
            "summary_dashboard.html",
            report_title="群聊日常分析",
            report_date=datetime.now().strftime("%Y.%m.%d"),
            metrics=metrics,
            chart_data=chart_data,
        )
        if not html_content:
            return None

        options = {
            "type": "png",
            "omit_background": True,
            "full_page": False,
            "clip": {"x": 0, "y": 0, "width": 800, "height": 360},
            "animations": "disabled",
            "caret": "hide",
            "scale": "device",
            "device_scale_factor_level": "high",
            "timeout": 30000,
        }

        async def render() -> str | None:
            result = await html_render_func(html_content, {}, True, options)
            url = str(result or "").strip()
            if url.startswith(("http://", "https://")):
                return url
            logger.warning("[QQOfficial] T2I 概览图未返回可公开访问的 URL")
            return None

        try:
            if self.render_semaphore is None:
                return await render()
            async with self.render_semaphore:
                return await render()
        except Exception as exc:
            logger.warning("[QQOfficial] T2I 群聊概览图生成失败: %s", exc)
            return None

    def _generate_markdown_report(
        self, analysis_result: dict, summary_dashboard_url: str | None = None
    ) -> str:
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]

        if summary_dashboard_url:
            lines = [
                f"![群聊分析概览 #800px #360px]({summary_dashboard_url})",
                "",
            ]
        else:
            lines = [
                "# 🎯 群聊日常分析报告",
                f"📅 {datetime.now().strftime('%Y年%m月%d日')}",
                "",
                "## 📊 基础统计",
                f"- **消息总数**：{stats.message_count}",
                f"- **参与人数**：{stats.participant_count}",
                f"- **总字符数**：{stats.total_characters}",
                f"- **表情数量**：{stats.emoji_count}",
                f"- **最活跃时段**：{stats.most_active_period}",
                "",
            ]
            activity_chart = self.build_activity_chart(stats)
            if activity_chart:
                lines.extend(activity_chart)
                lines.append("")

        lines.append("## 💬 热门话题")
        max_topics = self.config_manager.get_max_topics()
        for index, topic in enumerate(topics[:max_topics], 1):
            topic_name = self.render_identity_text(topic.topic, analysis_result)
            lines.append(f"### {index}. {topic_name}")
            contributor_ids = list(getattr(topic, "contributor_ids", []) or [])
            mentions = self.mentions(contributor_ids)
            if mentions:
                lines.append(f"**参与者**：{mentions}")
            detail = self.render_identity_text(topic.detail, analysis_result)
            if detail:
                lines.append(detail)
            lines.append("")

        lines.append("## 🏆 群友称号")
        max_user_titles = self.config_manager.get_max_user_titles()
        for title in user_titles[:max_user_titles]:
            mention = self.mention(getattr(title, "user_id", ""))
            title_text = self.render_identity_text(title.title, analysis_result)
            mbti = f" · {title.mbti}" if getattr(title, "mbti", "") else ""
            prefix = f"{mention} — " if mention else ""
            lines.append(f"- {prefix}**{title_text}**{mbti}")
            reason = self.render_identity_text(title.reason, analysis_result)
            if reason:
                lines.append(f"  > {reason}")
        lines.append("")

        lines.append("## 💬 群圣经")
        max_golden_quotes = self.config_manager.get_max_golden_quotes()
        for index, golden_quote in enumerate(
            stats.golden_quotes[:max_golden_quotes], 1
        ):
            quote_content = self.render_identity_text(
                golden_quote.content, analysis_result
            )
            mention = self.mention(getattr(golden_quote, "user_id", ""))
            attribution = f" — {mention}" if mention else ""
            lines.append(f"- **{index}. {quote_content}**{attribution}")
            reason = self.render_identity_text(golden_quote.reason, analysis_result)
            if reason:
                lines.append(f"  > {reason}")
            lines.append("")

        return "\n".join(lines).strip()

    @staticmethod
    def format_metric(value: object) -> str:
        try:
            number = max(0, int(value) if value is not None else 0)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return "0"
        if number >= 1_000_000:
            formatted = f"{number / 1_000_000:.1f}".rstrip("0").rstrip(".")
            return f"{formatted}M"
        if number >= 10_000:
            formatted = f"{number / 1_000:.1f}".rstrip("0").rstrip(".")
            return f"{formatted}K"
        return f"{number:,}"

    @staticmethod
    def format_peak_period(value: object) -> str:
        text = str(value or "").strip()
        match = re.search(r"(\d{1,2}):\d{2}\s*[-~—至]\s*(\d{1,2}):\d{2}", text)
        if match:
            return f"{int(match.group(1)):02d}–{int(match.group(2)):02d}"
        return text or "—"

    @classmethod
    def build_activity_chart(cls, stats: object, bar_width: int = 12) -> list[str]:
        hourly_counts = cls.get_hourly_counts(stats)
        max_count = max(hourly_counts, default=0)
        if max_count <= 0:
            return []

        effective_width = max(1, int(bar_width))
        lines = ["## ⏰ 活跃时间分布"]
        for hour, count in enumerate(hourly_counts):
            if count > 0:
                blocks = max(
                    1,
                    (count * effective_width + max_count - 1) // max_count,
                )
                bar = "█" * blocks
            else:
                bar = "—"
            lines.append(f"- {hour:02d}:00　{bar}　{count}")
        return lines

    @staticmethod
    def get_hourly_counts(stats: object) -> list[int]:
        activity_viz = getattr(stats, "activity_visualization", None)
        raw_activity = getattr(activity_viz, "hourly_activity", None) or {}
        if not isinstance(raw_activity, dict):
            return [0] * 24

        hourly_counts: list[int] = []
        for hour in range(24):
            raw_count = raw_activity.get(hour, raw_activity.get(str(hour), 0))
            try:
                count = max(0, int(raw_count or 0))
            except (TypeError, ValueError):
                count = 0
            hourly_counts.append(count)
        return hourly_counts

    @staticmethod
    def mention(user_id: object) -> str:
        normalized = str(user_id or "").strip().strip("[]")
        return f"<@{normalized}>" if normalized else ""

    @classmethod
    def mentions(cls, user_ids: list[object]) -> str:
        unique_ids = list(
            dict.fromkeys(
                str(user_id or "").strip().strip("[]")
                for user_id in user_ids
                if str(user_id or "").strip().strip("[]")
            )
        )
        return " ".join(cls.mention(user_id) for user_id in unique_ids)

    @classmethod
    def render_identity_text(cls, text: object, analysis_result: dict) -> str:
        """Replace known IDs and display names with QQ mention syntax."""
        source = str(text or "")
        user_analysis = analysis_result.get("user_analysis") or {}
        id_to_names: dict[str, set[str]] = {}

        for user_id, user_data in user_analysis.items():
            normalized_id = str(user_id or "").strip()
            if not normalized_id:
                continue
            names: set[str] = set()
            if isinstance(user_data, dict):
                for key in ("nickname", "name", "card"):
                    name = str(user_data.get(key, "") or "").strip()
                    if name and name != normalized_id:
                        names.add(name)
            id_to_names[normalized_id] = names

        for title in analysis_result.get("user_titles", []) or []:
            user_id = str(getattr(title, "user_id", "") or "").strip()
            name = str(getattr(title, "name", "") or "").strip()
            if user_id:
                id_to_names.setdefault(user_id, set())
                if name and name != user_id:
                    id_to_names[user_id].add(name)

        stats = analysis_result.get("statistics")
        for golden_quote in getattr(stats, "golden_quotes", []) or []:
            user_id = str(getattr(golden_quote, "user_id", "") or "").strip()
            name = str(getattr(golden_quote, "sender", "") or "").strip()
            if user_id:
                id_to_names.setdefault(user_id, set())
                if name and name != user_id:
                    id_to_names[user_id].add(name)

        placeholders: dict[str, str] = {}

        def protect_mention(match: re.Match[str]) -> str:
            key = f"\x00QQMENTION{len(placeholders)}\x00"
            placeholders[key] = match.group(0)
            return key

        source = re.sub(r"<@[A-Za-z0-9_-]+>", protect_mention, source)
        for user_id in sorted(id_to_names, key=len, reverse=True):
            mention = cls.mention(user_id)
            source = re.sub(rf"\[{re.escape(user_id)}\]", mention, source)
            source = re.sub(r"<@[A-Za-z0-9_-]+>", protect_mention, source)
            source = re.sub(
                rf"(?<![A-Za-z0-9_-]){re.escape(user_id)}(?![A-Za-z0-9_-])",
                mention,
                source,
            )
            source = re.sub(r"<@[A-Za-z0-9_-]+>", protect_mention, source)

        source = re.sub(r"<@[A-Za-z0-9_-]+>", protect_mention, source)
        name_to_ids: dict[str, set[str]] = {}
        for user_id, names in id_to_names.items():
            for name in names:
                if name:
                    name_to_ids.setdefault(name, set()).add(user_id)
        for name in sorted(name_to_ids, key=len, reverse=True):
            matched_ids = name_to_ids[name]
            replacement = (
                cls.mention(next(iter(matched_ids))) if len(matched_ids) == 1 else ""
            )
            source = source.replace(name, replacement)
            source = re.sub(r"<@[A-Za-z0-9_-]+>", protect_mention, source)

        for placeholder, mention in placeholders.items():
            source = source.replace(placeholder, mention)
        return source.strip()
