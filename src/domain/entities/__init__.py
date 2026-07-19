"""
领域实体

该模块导出所有领域实体类，包括:
- AnalysisTask: 分析任务聚合根
- IncrementalBatch: 增量分析独立批次实体
- IncrementalState: 增量分析聚合视图（报告时使用）
"""

from .analysis_task import AnalysisTask, TaskStatus
from .incremental_state import IncrementalBatch, IncrementalState

__all__ = [
    "AnalysisTask",
    "TaskStatus",
    "IncrementalBatch",
    "IncrementalState",
]
