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
    领域服务：报告生成器

    负责将抽象的统计数据、话题和金句转换为人类可读的格式化报告。
    该类是平台无关的，主要生成 Markdown 风格的文本。
    """

    def __init__(self, group_name: str = "", date_str: str = ""):
        """
        初始化报告生成器。

        Args:
            group_name (str): 报告所属的群组名称
            date_str (str, optional): 报告日期 (YYYY-MM-DD)，默认为今日
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
        生成完整的群聊分析报告。

        Args:
            statistics (GroupStatistics): 基础统计数据
            topics (list[Topic]): 讨论话题列表
            user_titles (list[UserTitle]): 用户称号列表
            golden_quotes (list[GoldenQuote]): 精彩金句列表
            include_header (bool): 是否包含页眉
            include_footer (bool): 是否包含页脚

        Returns:
            str: 格式化后的完整报告字符串
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
        """
        内部方法：构造报告的标题页眉。

        Returns:
            str: 包含群名、日期的页眉文本
        """
        title = "📊 群聊分析报告"
        if self.group_name:
            title += f" - {self.group_name}"

        return f"{title}\n📅 日期: {self.date_str}\n{'=' * 40}"

    def _generate_statistics_section(self, stats: GroupStatistics) -> str:
        """
        内部方法：格式化基础数值统计区块。

        Args:
            stats (GroupStatistics): 群组统计数据

        Returns:
            str: 格式化的 Markdown 列表区块
        """
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
        """
        内部方法：格式化讨论话题摘要区块。

        Args:
            topics (list[Topic]): 话题列表

        Returns:
            str: 序列化的 Markdown 话题区块
        """
        lines = ["💬 **讨论话题**"]

        for i, topic in enumerate(topics, 1):
            contributors_str = ", ".join(topic.contributors[:3])
            if len(topic.contributors) > 3:
                contributors_str += f" 等{len(topic.contributors) - 3}人"

            lines.append(f"\n{i}. **{topic.name}**")
            lines.append(f"   参与者: {contributors_str}")
            if topic.detail:
                # 截断过长的详情，避免报告过大
                detail = (
                    topic.detail[:200] + "..."
                    if len(topic.detail) > 200
                    else topic.detail
                )
                lines.append(f"   {detail}")

        return "\n".join(lines)

    def _generate_user_titles_section(self, titles: list[UserTitle]) -> str:
        """
        内部方法：格式化用户荣誉/称号区块。

        Args:
            titles (list[UserTitle]): 称号列表

        Returns:
            str: 格式化的 Markdown 用户榜区块
        """
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
        """
        内部方法：格式化精彩金句展示区块。

        Args:
            quotes (list[GoldenQuote]): 金句列表

        Returns:
            str: 格式化的 Markdown 金句区块
        """
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
        """
        内部方法：生成包含生成时间和性能元数据的页脚。

        Args:
            token_usage (TokenUsage, optional): 关联的 LLM 消耗

        Returns:
            str: 报告页脚
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = ["─" * 40]
        lines.append(f"生成时间: {now}")

        if token_usage and token_usage.total_tokens > 0:
            lines.append(f"令牌使用: {token_usage.total_tokens} tokens")

        return "\n".join(lines)

    def generate_summary_report(
        self,
        statistics: GroupStatistics,
        top_topic: Topic | None = None,
        top_quote: GoldenQuote | None = None,
    ) -> str:
        """
        生成简短的摘要报告。

        Args:
            statistics (GroupStatistics): 基础统计数据
            top_topic (Topic, optional): 头对话题
            top_quote (GoldenQuote, optional): 最优金句

        Returns:
            str: 简短摘要字符串
        """
        lines = [
            f"📊 每日摘要 ({self.date_str})",
            f"消息: {statistics.message_count} | 参与: {statistics.participant_count}人",
        ]

        if top_topic:
            lines.append(f"🔥 热门话题: {top_topic.name}")

        if top_quote:
            lines.append(f'✨ 金句: "{top_quote.content}" — {top_quote.sender}')

        return "\n".join(lines)
