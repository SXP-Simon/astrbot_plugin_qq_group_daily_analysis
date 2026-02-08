"""
领域实体

该模块导出所有领域实体类，包括:
- AnalysisTask: 分析任务聚合根
- GroupAnalysisResult: 群聊分析结果实体
"""

from .analysis_task import AnalysisTask, TaskStatus
from .analysis_result import (
    GroupAnalysisResult,
    SummaryTopic,
    UserTitle,
    GoldenQuote,
    TokenUsage,
    EmojiStatistics,
    ActivityVisualization,
    GroupStatistics,
)

# 别名，保持向后兼容
AnalysisResult = GroupAnalysisResult

__all__ = [
    "AnalysisTask",
    "TaskStatus",
    "GroupAnalysisResult",
    "AnalysisResult",  # 别名
    "SummaryTopic",
    "UserTitle",
    "GoldenQuote",
    "TokenUsage",
    "EmojiStatistics",
    "ActivityVisualization",
    "GroupStatistics",
]
