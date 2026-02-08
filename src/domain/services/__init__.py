"""
领域服务 - 分析业务逻辑服务

该模块导出所有封装核心业务逻辑的领域服务，
用于分析群聊数据。这些服务是平台无关的。

服务分类:
- 分析器服务: 话题分析、用户称号分析、金句分析
- 计算服务: 统计计算
- 生成服务: 报告生成
"""

from .golden_quote_analyzer import GoldenQuoteAnalyzerAdapter, IGoldenQuoteAnalyzer
from .report_generator import ReportGenerator
from .statistics_calculator import StatisticsCalculator
from .topic_analyzer import ITopicAnalyzer, TopicAnalyzerAdapter
from .user_title_analyzer import IUserTitleAnalyzer, UserTitleAnalyzerAdapter

__all__ = [
    # 统计与报告服务
    "StatisticsCalculator",
    "ReportGenerator",
    # 话题分析服务
    "ITopicAnalyzer",
    "TopicAnalyzerAdapter",
    # 用户称号分析服务
    "IUserTitleAnalyzer",
    "UserTitleAnalyzerAdapter",
    # 金句分析服务
    "IGoldenQuoteAnalyzer",
    "GoldenQuoteAnalyzerAdapter",
]
