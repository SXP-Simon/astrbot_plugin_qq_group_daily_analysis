"""
报告生成器 - 生成分析报告的领域服务

该服务从分析结果生成格式化报告。
它是平台无关的，生成文本/Markdown 报告。
"""

from datetime import datetime

from ..value_objects.golden_quote import GoldenQuote
from ..value_objects.statistics import GroupStatistics, TokenUsage
from ..value_objects.topic import Topic
from ..value_objects.user_title import UserTitle


class ReportGenerator:
    """
    生成分析报告的领域服务。

    该服务接收分析结果并生成格式化的
    文本报告，可发送到任何平台。
    """

    def __init__(self, group_name: str = "", date_str: str = ""):
        """
        初始化报告生成器。

        参数:
            group_name: 报告标题中的群组名称
            date_str: 报告的日期字符串
        """
        self.group_name = group_name
        self.date_str = date_str or datetime.now().strftime("%Y-%m-%d")

    def generate_full_report(
        self,
        statistics: GroupStatistics,
        topics: list[Topic],
        user_titles: list[UserTitle],
        golden_quotes: list[GoldenQuote],
        include_header: bool = True,
        include_footer: bool = True,
    ) -> str:
        """
        生成完整的分析报告。

        参数:
            statistics: 群聊统计
            topics: 讨论话题列表
            user_titles: 用户称号/徽章列表
            golden_quotes: 金句列表
            include_header: 是否包含报告头部
            include_footer: 是否包含报告尾部

        返回:
            格式化的报告字符串
        """
        sections = []

        if include_header:
            sections.append(self._generate_header())

        sections.append(self._generate_statistics_section(statistics))

        if topics:
            sections.append(self._generate_topics_section(topics))

        if user_titles:
            sections.append(self._generate_user_titles_section(user_titles))

        if golden_quotes:
            sections.append(self._generate_golden_quotes_section(golden_quotes))

        if include_footer:
            sections.append(self._generate_footer(statistics.token_usage))

        return "\n\n".join(sections)

    def _generate_header(self) -> str:
        """生成报告头部。"""
        title = "📊 群聊分析报告"
        if self.group_name:
            title += f" - {self.group_name}"

        return f"{title}\n📅 日期: {self.date_str}\n{'=' * 40}"

    def _generate_statistics_section(self, stats: GroupStatistics) -> str:
        """生成统计部分。"""
        lines = [
            "📈 **统计概览**",
            f"• 消息总数: {stats.message_count}",
            f"• 字符总数: {stats.total_characters}",
            f"• 参与人数: {stats.participant_count}",
            f"• 平均消息长度: {stats.average_message_length:.1f} 字符",
            f"• 最活跃时段: {stats.most_active_period}",
        ]

        if stats.emoji_count > 0:
            lines.append(f"• 表情使用: {stats.emoji_count}")

        return "\n".join(lines)

    def _generate_topics_section(self, topics: list[Topic]) -> str:
        """生成话题部分。"""
        lines = ["💬 **讨论话题**"]

        for i, topic in enumerate(topics, 1):
            contributors_str = ", ".join(topic.contributors[:3])
            if len(topic.contributors) > 3:
                contributors_str += f" 等{len(topic.contributors) - 3}人"

            lines.append(f"\n{i}. **{topic.name}**")
            lines.append(f"   参与者: {contributors_str}")
            if topic.detail:
                # 截断过长的详情
                detail = (
                    topic.detail[:200] + "..."
                    if len(topic.detail) > 200
                    else topic.detail
                )
                lines.append(f"   {detail}")

        return "\n".join(lines)

    def _generate_user_titles_section(self, titles: list[UserTitle]) -> str:
        """生成用户称号部分。"""
        lines = ["🏆 **用户称号与徽章**"]

        for title in titles:
            lines.append(f"\n👤 **{title.name}**")
            lines.append(f"   🎖️ 称号: {title.title}")
            if title.mbti:
                lines.append(f"   🧠 MBTI: {title.mbti}")
            if title.reason:
                reason = (
                    title.reason[:150] + "..."
                    if len(title.reason) > 150
                    else title.reason
                )
                lines.append(f"   💡 原因: {reason}")

        return "\n".join(lines)

    def _generate_golden_quotes_section(self, quotes: list[GoldenQuote]) -> str:
        """生成金句部分。"""
        lines = ["✨ **金句集锦**"]

        for i, quote in enumerate(quotes, 1):
            lines.append(f'\n{i}. "{quote.content}"')
            lines.append(f"   — {quote.sender}")
            if quote.reason:
                reason = (
                    quote.reason[:100] + "..."
                    if len(quote.reason) > 100
                    else quote.reason
                )
                lines.append(f"   ({reason})")

        return "\n".join(lines)

    def _generate_footer(self, token_usage: TokenUsage | None = None) -> str:
        """生成报告尾部。"""
        lines = ["─" * 40]
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if token_usage and token_usage.total_tokens > 0:
            lines.append(f"令牌使用: {token_usage.total_tokens} tokens")

        return "\n".join(lines)

    def _generate_topics_section(self, topics: list[Topic]) -> str:
        """Generate topics section."""
        lines = ["💬 **Discussion Topics**"]

        for i, topic in enumerate(topics, 1):
            contributors_str = ", ".join(topic.contributors[:3])
            if len(topic.contributors) > 3:
                contributors_str += f" +{len(topic.contributors) - 3} more"

            lines.append(f"\n{i}. **{topic.name}**")
            lines.append(f"   Contributors: {contributors_str}")
            if topic.detail:
                # Truncate long details
                detail = (
                    topic.detail[:200] + "..."
                    if len(topic.detail) > 200
                    else topic.detail
                )
                lines.append(f"   {detail}")

        return "\n".join(lines)

    def _generate_user_titles_section(self, titles: list[UserTitle]) -> str:
        """Generate user titles section."""
        lines = ["🏆 **User Titles & Badges**"]

        for title in titles:
            lines.append(f"\n👤 **{title.name}**")
            lines.append(f"   🎖️ Title: {title.title}")
            if title.mbti:
                lines.append(f"   🧠 MBTI: {title.mbti}")
            if title.reason:
                reason = (
                    title.reason[:150] + "..."
                    if len(title.reason) > 150
                    else title.reason
                )
                lines.append(f"   💡 Reason: {reason}")

        return "\n".join(lines)

    def _generate_golden_quotes_section(self, quotes: list[GoldenQuote]) -> str:
        """Generate golden quotes section."""
        lines = ["✨ **Golden Quotes**"]

        for i, quote in enumerate(quotes, 1):
            lines.append(f'\n{i}. "{quote.content}"')
            lines.append(f"   — {quote.sender}")
            if quote.reason:
                reason = (
                    quote.reason[:100] + "..."
                    if len(quote.reason) > 100
                    else quote.reason
                )
                lines.append(f"   ({reason})")

        return "\n".join(lines)

    def _generate_footer(self, token_usage: TokenUsage | None = None) -> str:
        """Generate report footer."""
        lines = ["─" * 40]
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if token_usage and token_usage.total_tokens > 0:
            lines.append(f"Token Usage: {token_usage.total_tokens} tokens")

        return "\n".join(lines)

    def generate_summary_report(
        self,
        statistics: GroupStatistics,
        top_topic: Topic | None = None,
        top_quote: GoldenQuote | None = None,
    ) -> str:
        """
        Generate a brief summary report.

        Args:
            statistics: Group chat statistics
            top_topic: Most significant topic (optional)
            top_quote: Best golden quote (optional)

        Returns:
            Brief summary string
        """
        lines = [
            f"📊 Daily Summary ({self.date_str})",
            f"Messages: {statistics.message_count} | Participants: {statistics.participant_count}",
        ]

        if top_topic:
            lines.append(f"🔥 Hot Topic: {top_topic.name}")

        if top_quote:
            lines.append(f'✨ Quote: "{top_quote.content}" — {top_quote.sender}')

        return "\n".join(lines)
