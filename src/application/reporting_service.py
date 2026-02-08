"""
Reporting Service - Application service for generating and sending reports

This service coordinates report generation and delivery to groups.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from astrbot.api import logger

from ..domain.services import ReportGenerator
from ..domain.value_objects.topic import Topic
from ..domain.value_objects.user_title import UserTitle
from ..domain.value_objects.golden_quote import GoldenQuote
from ..domain.value_objects.statistics import GroupStatistics
from ..infrastructure.config import ConfigManager
from ..infrastructure.persistence import HistoryRepository


class ReportingService:
    """
    Application service for generating and managing reports.

    This service coordinates between domain services and infrastructure
    to produce and deliver analysis reports.
    """

    def __init__(
        self,
        config: ConfigManager,
        history_repository: HistoryRepository,
    ):
        """
        Initialize the reporting service.

        Args:
            config: Configuration manager
            history_repository: Repository for storing reports
        """
        self.config = config
        self.history = history_repository

    def generate_report(
        self,
        group_id: str,
        group_name: str,
        statistics: GroupStatistics,
        topics: List[Topic],
        user_titles: List[UserTitle],
        golden_quotes: List[GoldenQuote],
        date_str: Optional[str] = None,
    ) -> str:
        """
        Generate a complete analysis report.

        Args:
            group_id: Group identifier
            group_name: Group display name
            statistics: Group statistics
            topics: List of discussion topics
            user_titles: List of user titles
            golden_quotes: List of golden quotes
            date_str: Report date (defaults to today)

        Returns:
            Formatted report string
        """
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")

        generator = ReportGenerator(
            group_name=group_name,
            date_str=date_str,
        )

        # Generate report based on configuration
        report = generator.generate_full_report(
            statistics=statistics,
            topics=topics if self.config.get_include_topics() else [],
            user_titles=user_titles if self.config.get_include_user_titles() else [],
            golden_quotes=golden_quotes if self.config.get_include_golden_quotes() else [],
            include_header=True,
            include_footer=True,
        )

        return report

    def generate_summary(
        self,
        group_id: str,
        statistics: GroupStatistics,
        top_topic: Optional[Topic] = None,
        top_quote: Optional[GoldenQuote] = None,
        date_str: Optional[str] = None,
    ) -> str:
        """
        Generate a brief summary report.

        Args:
            group_id: Group identifier
            statistics: Group statistics
            top_topic: Most significant topic
            top_quote: Best golden quote
            date_str: Report date

        Returns:
            Brief summary string
        """
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")

        generator = ReportGenerator(date_str=date_str)
        return generator.generate_summary_report(
            statistics=statistics,
            top_topic=top_topic,
            top_quote=top_quote,
        )

    def save_report(
        self,
        group_id: str,
        report_data: Dict[str, Any],
        date_str: Optional[str] = None,
    ) -> bool:
        """
        Save a report to history.

        Args:
            group_id: Group identifier
            report_data: Report data dictionary
            date_str: Report date

        Returns:
            True if saved successfully
        """
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")

        return self.history.save_analysis_result(
            group_id=group_id,
            result=report_data,
            date_str=date_str,
        )

    def get_report(
        self,
        group_id: str,
        date_str: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a saved report.

        Args:
            group_id: Group identifier
            date_str: Report date

        Returns:
            Report data or None
        """
        return self.history.get_analysis_result(group_id, date_str)

    def get_recent_reports(
        self,
        group_id: str,
        limit: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Get recent reports for a group.

        Args:
            group_id: Group identifier
            limit: Maximum number of reports

        Returns:
            List of report data dictionaries
        """
        return self.history.get_recent_results(group_id, limit)

    def has_report_for_today(self, group_id: str) -> bool:
        """
        Check if a report exists for today.

        Args:
            group_id: Group identifier

        Returns:
            True if report exists
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return self.history.has_analysis_for_date(group_id, today)

    def format_for_platform(
        self,
        report: str,
        platform: str,
        format_type: Optional[str] = None,
    ) -> str:
        """
        Format a report for a specific platform.

        Args:
            report: Raw report text
            platform: Target platform
            format_type: Override format type

        Returns:
            Platform-formatted report
        """
        format_type = format_type or self.config.get_report_format()

        # For now, return as-is. Can be extended for platform-specific formatting
        if format_type == "markdown":
            return report
        elif format_type == "text":
            # Strip markdown formatting
            return self._strip_markdown(report)
        else:
            return report

    def _strip_markdown(self, text: str) -> str:
        """Strip markdown formatting from text."""
        # Simple markdown stripping
        import re

        # Remove bold
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        # Remove italic
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        # Remove headers
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

        return text

    def create_report_data(
        self,
        group_id: str,
        group_name: str,
        statistics: GroupStatistics,
        topics: List[Topic],
        user_titles: List[UserTitle],
        golden_quotes: List[GoldenQuote],
    ) -> Dict[str, Any]:
        """
        Create a report data dictionary for storage.

        Args:
            group_id: Group identifier
            group_name: Group display name
            statistics: Group statistics
            topics: List of topics
            user_titles: List of user titles
            golden_quotes: List of golden quotes

        Returns:
            Report data dictionary
        """
        return {
            "group_id": group_id,
            "group_name": group_name,
            "timestamp": datetime.now().isoformat(),
            "statistics": statistics.to_dict(),
            "topics": [t.to_dict() for t in topics],
            "user_titles": [u.to_dict() for u in user_titles],
            "golden_quotes": [q.to_dict() for q in golden_quotes],
        }
