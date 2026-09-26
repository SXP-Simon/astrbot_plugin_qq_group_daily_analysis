"""多平台通用 Markdown 报告生成器 (Markdown Report Generator)

负责根据领域层分析结果载荷，格式化并生成结构化 Markdown 文本报告。
支持不同平台的提及渲染风格（如 QQ 官方的 <@user_id> 真提及与 Telegram/Discord 等的昵称降级展示）。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from ...utils.logger import logger

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable, Sequence

    from ...domain.value_objects import AnalysisResultPayload, GroupStatistics
    from ..config.config_manager import ConfigManager
    from .templates import HTMLTemplates


MENTION_STYLE_QQ = "qq"
"""QQ 官方机器人：身份以 <@user_id> 真提及展示。"""

MENTION_STYLE_NAME = "name"
"""跨平台标准模式（Telegram / Discord 等无 @ 提及能力）：身份降级为昵称文本。"""


class MarkdownReportGenerator:
    """多平台 Markdown 报告生成器。

    支持根据不同平台的消息能力输出结构化 Markdown 报告或降级文本。
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        html_templates: HTMLTemplates | None = None,
        render_semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self.config_manager = config_manager
        self.html_templates = html_templates
        self.render_semaphore = render_semaphore

    async def generate_qq_official_report(
        self,
        analysis_result: AnalysisResultPayload,
        html_render_func: Callable[..., Awaitable[str | None]] | None = None,
    ) -> tuple[str, str]:
        """生成 QQ 官方 Markdown 报告（含可选 T2I 概览图）与无 URL 的备选降级报告。

        Args:
            analysis_result: 分析结果载荷。
            html_render_func: HTML 异步渲染函数。

        Returns:
            tuple[str, str]: (主报告内容, 降级报告内容)
        """
        fallback_report = self._generate_markdown_report(
            analysis_result, mention_style=MENTION_STYLE_QQ
        )
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
                analysis_result,
                summary_dashboard_url=dashboard_url,
                mention_style=MENTION_STYLE_QQ,
            ),
            fallback_report,
        )

    # 兼容历史别名
    generate = generate_qq_official_report

    async def _generate_summary_dashboard_url(
        self,
        analysis_result: AnalysisResultPayload,
        html_render_func: Callable[..., Awaitable[str | None]],
    ) -> str | None:
        """生成 T2I 概览图并返回可访问 URL。"""
        if not self.html_templates:
            return None
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
            logger.warning("[MarkdownReport] T2I 概览图未返回可公开访问的 URL")
            return None

        try:
            if self.render_semaphore is None:
                return await render()
            async with self.render_semaphore:
                return await render()
        except Exception as exc:
            logger.warning("[MarkdownReport] T2I 群聊概览图生成失败: %s", exc)
            return None

    def generate_plain_markdown_report(
        self,
        analysis_result: AnalysisResultPayload,
    ) -> str:
        """生成跨平台通用的 Markdown 文本报告（身份降级为昵称）。

        供 Telegram / Discord 等无法渲染 <@user_id> 真提及的平台复用同一套排版，
        避免为每个平台重复维护文本模版。

        Args:
            analysis_result: 分析结果载荷。

        Returns:
            str: 格式化的 Markdown 文本报告。
        """
        return self._generate_markdown_report(
            analysis_result, mention_style=MENTION_STYLE_NAME
        )

    def _collect_identity_names(
        self, analysis_result: AnalysisResultPayload
    ) -> dict[str, str]:
        """收集 user_id -> 展示昵称映射，供无 @ 能力的平台降级展示身份。"""
        names: dict[str, str] = {}

        def remember(user_id: object, name: object) -> None:
            normalized_id = str(user_id or "").strip().strip("[]")
            normalized_name = str(name or "").strip()
            if normalized_id and normalized_name and normalized_name != normalized_id:
                names.setdefault(normalized_id, normalized_name)

        user_analysis = analysis_result.get("user_analysis") or {}
        for user_id, user_data in user_analysis.items():
            if isinstance(user_data, dict):
                for key in ("nickname", "name", "card"):
                    if user_data.get(key):
                        remember(user_id, user_data.get(key))
                        break

        for title in analysis_result.get("user_titles", []) or []:
            remember(getattr(title, "user_id", None), getattr(title, "name", None))

        stats = analysis_result.get("statistics")
        for golden_quote in getattr(stats, "golden_quotes", None) or []:
            remember(
                getattr(golden_quote, "user_id", None),
                getattr(golden_quote, "sender", None),
            )

        return names

    # 平台用户 ID 的长度下限：QQ(6~11 位) / Telegram(≤10 位) 等平台的 ID 都是 6 位以上数字，
    # 用它把「裸数字身份引用」与正文里的普通统计数字（如消息总数 1234）区分开。
    _MIN_BARE_ID_LENGTH = 6

    # 身份引用匹配：显式形式 [id] / <@id>，以及裸数字 ID（长度下限见 _MIN_BARE_ID_LENGTH）。
    _IDENTITY_REF_RE = re.compile(
        r"\[([^\[\]]+)\]|<@([^<>]+)>|(?<![A-Za-z0-9_[<])(\d+)(?![A-Za-z0-9_>])"
    )

    @classmethod
    def _render_identity_names(cls, text: str | None, names: dict[str, str]) -> str:
        """把文本里的用户引用替换为昵称。

        支持两类明确的引用：`[id]`、`<@id>` 形式，以及长度 >= _MIN_BARE_ID_LENGTH 的
        纯数字裸 ID。单次遍历原文完成替换，避免二次替换与误替换。
        """

        def replace(match: re.Match[str]) -> str:
            explicit = match.group(1) or match.group(2)
            user_id = explicit or match.group(3)
            if user_id not in names:
                return match.group(0)
            if explicit is None and len(user_id) < cls._MIN_BARE_ID_LENGTH:
                return match.group(0)
            return names[user_id]

        return cls._IDENTITY_REF_RE.sub(replace, str(text or "")).strip()

    def _generate_markdown_report(
        self,
        analysis_result: AnalysisResultPayload,
        summary_dashboard_url: str | None = None,
        mention_style: str = MENTION_STYLE_QQ,
    ) -> str:
        """生成 Markdown 报告主体内容。"""
        stats = analysis_result["statistics"]
        topics = analysis_result["topics"]
        user_titles = analysis_result["user_titles"]

        plain_names = mention_style == MENTION_STYLE_NAME
        identity_names = (
            self._collect_identity_names(analysis_result) if plain_names else {}
        )

        def render_mention(user_id: str | int | None) -> str:
            if not plain_names:
                return self.mention(user_id)
            normalized = str(user_id or "").strip().strip("[]")
            return identity_names.get(normalized, normalized) if normalized else ""

        def render_mentions(user_ids: Sequence[str | int | None]) -> str:
            if not plain_names:
                return self.mentions(user_ids)
            rendered = [render_mention(user_id) for user_id in user_ids]
            return "、".join(dict.fromkeys(name for name in rendered if name))

        def render_text(text: str | None) -> str:
            if not plain_names:
                return self.render_identity_text(text or "", analysis_result)
            return self._render_identity_names(text, identity_names)

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
            topic_name = render_text(topic.topic)
            lines.append(f"### {index}. {topic_name}")
            contributor_ids = list(topic.contributor_ids or [])
            mentions = render_mentions(contributor_ids)
            if mentions:
                lines.append(f"**参与者**：{mentions}")
            detail = render_text(topic.detail)
            if detail:
                lines.append(detail)
            lines.append("")

        lines.append("## 🏆 群友称号")
        max_user_titles = self.config_manager.get_max_user_titles()
        for title in user_titles[:max_user_titles]:
            mention = render_mention(title.user_id)
            title_text = render_text(title.title)
            mbti = f" · {title.mbti}" if title.mbti else ""
            prefix = f"{mention} — " if mention else ""
            lines.append(f"- {prefix}**{title_text}**{mbti}")
            reason = render_text(title.reason)
            if reason:
                lines.append(f"  > {reason}")
        lines.append("")

        lines.append("## 💬 群圣经")
        max_golden_quotes = self.config_manager.get_max_golden_quotes()
        for index, golden_quote in enumerate(
            stats.golden_quotes[:max_golden_quotes], 1
        ):
            quote_content = render_text(golden_quote.content)
            mention = render_mention(golden_quote.user_id)
            attribution = f" — {mention}" if mention else ""
            lines.append(f"- **{index}. {quote_content}**{attribution}")
            reason = render_text(golden_quote.reason)
            if reason:
                lines.append(f"  > {reason}")
            lines.append("")

        return "\n".join(lines).strip()

    @staticmethod
    def format_metric(value: int | float | str | bytes | bytearray | None) -> str:
        """格式化数字指标，支持 K/M 紧凑展示。"""
        try:
            if isinstance(value, (int, float, str, bytes, bytearray)):
                number = max(0, int(value))
            else:
                number = 0
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
    def format_peak_period(value: str | None) -> str:
        """格式化高峰时间段。"""
        text = str(value or "").strip()
        match = re.search(r"(\d{1,2}):\d{2}\s*[-~—至]\s*(\d{1,2}):\d{2}", text)
        if match:
            return f"{int(match.group(1)):02d}–{int(match.group(2)):02d}"
        return text or "—"

    @classmethod
    def build_activity_chart(
        cls, stats: GroupStatistics | None, bar_width: int = 12
    ) -> list[str]:
        """构建 24 小时活跃度字符柱状图。"""
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
    def get_hourly_counts(stats: GroupStatistics | None) -> list[int]:
        """从统计对象中解析 24 小时活跃度数组。"""
        if stats is None:
            return [0] * 24
        activity_viz = getattr(stats, "activity_visualization", None)
        if activity_viz is None:
            return [0] * 24
        raw_activity = getattr(activity_viz, "hourly_activity", None)
        if not isinstance(raw_activity, dict):
            return [0] * 24

        hourly_counts: list[int] = []
        for hour in range(24):
            raw_count = raw_activity.get(hour, raw_activity.get(str(hour), 0))
            try:
                count = max(0, int(str(raw_count or 0)))
            except (TypeError, ValueError):
                count = 0
            hourly_counts.append(count)
        return hourly_counts

    @staticmethod
    def mention(user_id: str | int | None) -> str:
        """生成 QQ 官方提及标签 <@user_id>。"""
        normalized = str(user_id or "").strip().strip("[]")
        return f"<@{normalized}>" if normalized else ""

    @classmethod
    def mentions(cls, user_ids: Sequence[str | int | None]) -> str:
        """批量生成 QQ 官方提及标签。"""
        unique_ids = list(
            dict.fromkeys(
                str(user_id or "").strip().strip("[]")
                for user_id in user_ids
                if str(user_id or "").strip().strip("[]")
            )
        )
        return " ".join(cls.mention(user_id) for user_id in unique_ids)

    @classmethod
    def render_identity_text(
        cls, text: str, analysis_result: AnalysisResultPayload
    ) -> str:
        """将文本中的用户 ID 或唯一昵称安全转换为 QQ 官方提及格式。"""
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
            user_id = str(title.user_id or "").strip()
            name = str(title.name or "").strip()
            if user_id:
                id_to_names.setdefault(user_id, set())
                if name and name != user_id:
                    id_to_names[user_id].add(name)

        stats = analysis_result.get("statistics")
        if stats:
            for golden_quote in stats.golden_quotes or []:
                user_id = str(golden_quote.user_id or "").strip()
                name = str(golden_quote.sender or "").strip()
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
            # 仅当昵称唯一映射到单一 user_id 时才做安全替换，多义词保持原样避免误删
            if len(matched_ids) == 1:
                mention_str = cls.mention(next(iter(matched_ids)))
                # 保护非单词字符边界
                pattern = (
                    rf"(?<![\w\u4e00-\u9fa5]){re.escape(name)}(?![\w\u4e00-\u9fa5])"
                )
                source = re.sub(pattern, mention_str, source)
                source = re.sub(r"<@[A-Za-z0-9_-]+>", protect_mention, source)

        for placeholder, mention in placeholders.items():
            source = source.replace(placeholder, mention)
        return source.strip()


# 向后兼容别名
QQOfficialMarkdownReportGenerator = MarkdownReportGenerator
