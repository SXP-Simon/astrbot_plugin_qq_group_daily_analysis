"""
报告服务 - 生成和发送报告的应用服务

该服务协调报告的生成并将其发送到群组。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.logger import logger

from ..domain.services import ReportGenerator
from ..domain.value_objects.topic import Topic
from ..domain.value_objects.user_title import UserTitle
from ..domain.value_objects.golden_quote import GoldenQuote
from ..domain.value_objects.statistics import GroupStatistics
from ..infrastructure.config import ConfigManager
from ..infrastructure.persistence import HistoryRepository


class ReportingService:
    """
    生成和管理报告的应用服务。

    该服务协调领域服务和基础设施
    以生成和发送分析报告。
    """

    def __init__(
        self,
        config: ConfigManager,
        history_repository: HistoryRepository,
    ):
        """
        初始化报告服务。

        Args:
            config: 配置管理器
            history_repository: 用于存储报告的仓库
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
        生成完整的分析报告。

        Args:
            group_id: 群组标识符
            group_name: 群组显示名称
            statistics: 群组统计
            topics: 讨论话题列表
            user_titles: 用户称号列表
            golden_quotes: 金句列表
            date_str: 报告日期（默认为今天）

        Returns:
            格式化的报告字符串
        """
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")

        generator = ReportGenerator(
            group_name=group_name,
            date_str=date_str,
        )

        # 根据配置生成报告
        report = generator.generate_full_report(
            statistics=statistics,
            topics=topics if self.config.get_include_topics() else [],
            user_titles=user_titles if self.config.get_include_user_titles() else [],
            golden_quotes=golden_quotes
            if self.config.get_include_golden_quotes()
            else [],
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
        生成简要摘要报告。

        Args:
            group_id: 群组标识符
            statistics: 群组统计
            top_topic: 最重要的话题
            top_quote: 最佳金句
            date_str: 报告日期

        Returns:
            简要摘要字符串
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
        保存报告到历史记录。

        Args:
            group_id: 群组标识符
            report_data: 报告数据字典
            date_str: 报告日期

        Returns:
            如果保存成功则返回 True
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
        获取已保存的报告。

        Args:
            group_id: 群组标识符
            date_str: 报告日期

        Returns:
            报告数据或 None
        """
        return self.history.get_analysis_result(group_id, date_str)

    def get_recent_reports(
        self,
        group_id: str,
        limit: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        获取群组的最近报告。

        Args:
            group_id: 群组标识符
            limit: 最大报告数

        Returns:
            报告数据字典列表
        """
        return self.history.get_recent_results(group_id, limit)

    def has_report_for_today(self, group_id: str) -> bool:
        """
        检查今天是否已存在报告。

        Args:
            group_id: 群组标识符

        Returns:
            如果报告存在则返回 True
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
        为特定平台格式化报告。

        Args:
            report: 原始报告文本
            platform: 目标平台
            format_type: 覆盖格式类型

        Returns:
            平台格式化的报告
        """
        format_type = format_type or self.config.get_report_format()

        # 目前保持原样返回。可以扩展为平台特定的格式化
        if format_type == "markdown":
            return report
        elif format_type == "text":
            # 去除 markdown 格式
            return self._strip_markdown(report)
        else:
            return report

    def _strip_markdown(self, text: str) -> str:
        """从文本中去除 markdown 格式。"""
        # 简单的 markdown 去除
        import re

        # 去除加粗
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        # 去除斜体
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        # 去除标题
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
        创建用于存储的报告数据字典。

        Args:
            group_id: 群组标识符
            group_name: 群组显示名称
            statistics: 群组统计
            topics: 话题列表
            user_titles: 用户称号列表
            golden_quotes: 金句列表

        Returns:
            报告数据字典
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
