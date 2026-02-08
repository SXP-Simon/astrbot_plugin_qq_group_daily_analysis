"""
分析任务实体 - 聚合根
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    CHECKING_PLATFORM = "checking_platform"
    FETCHING_MESSAGES = "fetching_messages"
    ANALYZING = "analyzing"
    GENERATING_REPORT = "generating_report"
    SENDING = "sending"
    COMPLETED = "completed"
    FAILED = "failed"
    UNSUPPORTED_PLATFORM = "unsupported_platform"


@dataclass
class AnalysisTask:
    """分析任务实体 - 聚合根"""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    group_id: str = ""
    platform_name: str = ""
    trace_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    is_manual: bool = False
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result_id: str | None = None
    error_message: str | None = None

    def start(self, can_analyze: bool) -> bool:
        """启动任务，验证平台能力"""
        if not can_analyze:
            self.status = TaskStatus.UNSUPPORTED_PLATFORM
            self.error_message = f"平台 {self.platform_name} 不支持分析"
            return False
        self.status = TaskStatus.FETCHING_MESSAGES
        self.started_at = time.time()
        return True

    def advance_to(self, status: TaskStatus):
        """推进到下一个状态"""
        self.status = status

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
