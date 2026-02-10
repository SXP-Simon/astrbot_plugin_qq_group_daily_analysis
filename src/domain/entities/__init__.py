"""
领域实体

该模块导出所有领域实体类，包括:
- AnalysisTask: 分析任务聚合根
- GroupAnalysisResult: 群聊分析结果实体
- IncrementalState: 增量分析状态实体
- BatchRecord: 增量分析批次记录
"""

from .analysis_result import (
    ActivityVisualization,
    EmojiStatistics,
    GoldenQuote,
    GroupAnalysisResult,
    GroupStatistics,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)
from .analysis_task import AnalysisTask, TaskStatus
from .incremental_state import BatchRecord, IncrementalState

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
    "IncrementalState",
    "BatchRecord",
]
