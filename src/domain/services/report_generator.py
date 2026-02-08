"""
Report Generator - Domain service for generating analysis reports

This service generates formatted reports from analysis results.
It is platform-agnostic and produces text/markdown reports.
"""

from datetime import datetime
from typing import List, Optional

from ..value_objects.topic import Topic
from ..value_objects.user_title import UserTitle
from ..value_objects.golden_quote import GoldenQuote
from ..value_objects.statistics import GroupStatistics, TokenUsage


class ReportGenerator:
    """
    Domain service for generating analysis reports.

    This service takes analysis results and produces formatted
    text reports that can be sent to any platform.
    """

    def __init__(self, group_name: str = "", date_str: str = ""):
        """
        Initialize the report generator.

        Args:
            group_name: Name of the group for report header
            date_str: Date string for the report
        """
        self.group_name = group_name
        self.date_str = date_str or datetime.now().strftime("%Y-%m-%d")

    def generate_full_report(
        self,
        statistics: GroupStatistics,
        topics: List[Topic],
        user_titles: List[UserTitle],
        golden_quotes: List[GoldenQuote],
        include_header: bool = True,
        include_footer: bool = True,
    ) -> str:
        """
        Generate a complete analysis report.

        Args:
            statistics: Group chat statistics
            topics: List of discussion topics
            user_titles: List of user titles/badges
            golden_quotes: List of golden quotes
            include_header: Whether to include report header
            include_footer: Whether to include report footer

        Returns:
            Formatted report string
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
        """Generate report header."""
        title = f"📊 Group Analysis Report"
        if self.group_name:
            title += f" - {self.group_name}"

        return f"{title}\n📅 Date: {self.date_str}\n{'=' * 40}"

    def _generate_statistics_section(self, stats: GroupStatistics) -> str:
        """Generate statistics section."""
        lines = [
            "📈 **Statistics Overview**",
            f"• Total Messages: {stats.message_count}",
            f"• Total Characters: {stats.total_characters}",
            f"• Participants: {stats.participant_count}",
            f"• Average Message Length: {stats.average_message_length:.1f} chars",
            f"• Most Active Period: {stats.most_active_period}",
        ]

        if stats.emoji_count > 0:
            lines.append(f"• Emoji Used: {stats.emoji_count}")

        return "\n".join(lines)

    def _generate_topics_section(self, topics: List[Topic]) -> str:
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
                detail = topic.detail[:200] + "..." if len(topic.detail) > 200 else topic.detail
                lines.append(f"   {detail}")

        return "\n".join(lines)

    def _generate_user_titles_section(self, titles: List[UserTitle]) -> str:
        """Generate user titles section."""
        lines = ["🏆 **User Titles & Badges**"]

        for title in titles:
            lines.append(f"\n👤 **{title.name}**")
            lines.append(f"   🎖️ Title: {title.title}")
            if title.mbti:
                lines.append(f"   🧠 MBTI: {title.mbti}")
            if title.reason:
                reason = title.reason[:150] + "..." if len(title.reason) > 150 else title.reason
                lines.append(f"   💡 Reason: {reason}")

        return "\n".join(lines)

    def _generate_golden_quotes_section(self, quotes: List[GoldenQuote]) -> str:
        """Generate golden quotes section."""
        lines = ["✨ **Golden Quotes**"]

        for i, quote in enumerate(quotes, 1):
            lines.append(f"\n{i}. \"{quote.content}\"")
            lines.append(f"   — {quote.sender}")
            if quote.reason:
                reason = quote.reason[:100] + "..." if len(quote.reason) > 100 else quote.reason
                lines.append(f"   ({reason})")

        return "\n".join(lines)

    def _generate_footer(self, token_usage: Optional[TokenUsage] = None) -> str:
        """Generate report footer."""
        lines = ["─" * 40]
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if token_usage and token_usage.total_tokens > 0:
            lines.append(f"Token Usage: {token_usage.total_tokens} tokens")

        return "\n".join(lines)

    def generate_summary_report(
        self,
        statistics: GroupStatistics,
        top_topic: Optional[Topic] = None,
        top_quote: Optional[GoldenQuote] = None,
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
            lines.append(f"✨ Quote: \"{top_quote.content}\" — {top_quote.sender}")

        return "\n".join(lines)
