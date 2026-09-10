"""
分析任务实体 - 聚合根
"""

import time
import uuid
from dataclasses import dataclass, field

from ...shared.constants import AnalysisStage, TaskStatus


@dataclass
class AnalysisTask:
    """分析任务实体 - 聚合根"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    group_id: str = ""
    platform_name: str = ""
    trace_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    current_stage: AnalysisStage | str = AnalysisStage.FETCH_MESSAGES
    is_manual: bool = False
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result_id: str | None = None
    error_message: str | None = None

    def start(self, can_analyze: bool) -> bool:
        """启动任务，验证平台能力。

        Args:
            can_analyze: 平台是否支持消息分析能力。

        Returns:
            bool: 任务启动是否成功。
        """
        if not can_analyze:
            self.status = TaskStatus.FAILED
            self.error_message = f"平台 {self.platform_name} 不支持分析"
            return False
        self.status = TaskStatus.RUNNING
        self.current_stage = AnalysisStage.FETCH_MESSAGES
        self.started_at = time.time()
        return True

    def advance_to(self, stage: AnalysisStage | str) -> None:
        """推进到下一个流水线阶段。

        Args:
            stage: 目标阶段。
        """
        self.current_stage = stage

    def complete(self, result_id: str):
        """标记任务为已完成"""
        self.status = TaskStatus.COMPLETED
        self.result_id = result_id
        self.completed_at = time.time()

    def fail(self, error: str):
        """标记任务为失败"""
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.completed_at = time.time()

    @property
    def duration(self) -> float | None:
        """获取任务持续时间（秒）"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
