"""
Analysis Task Entity - Aggregate Root
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import uuid


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
    """Analysis task entity - Aggregate root"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    group_id: str = ""
    platform_name: str = ""
    trace_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    is_manual: bool = False
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result_id: Optional[str] = None
    error_message: Optional[str] = None

    def start(self, can_analyze: bool) -> bool:
        """Start task, validate platform capability"""
        if not can_analyze:
            self.status = TaskStatus.UNSUPPORTED_PLATFORM
            self.error_message = f"Platform {self.platform_name} does not support analysis"
            return False
        self.status = TaskStatus.FETCHING_MESSAGES
        self.started_at = time.time()
        return True

    def advance_to(self, status: TaskStatus):
        """Advance to next status"""
        self.status = status

    def complete(self, result_id: str):
        """Mark task as completed"""
        self.status = TaskStatus.COMPLETED
        self.result_id = result_id
        self.completed_at = time.time()

    def fail(self, error: str):
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.completed_at = time.time()

    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
