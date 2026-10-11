"""分析任务生命周期状态值对象。"""

from enum import Enum


class TaskStatus(str, Enum):
    """分析任务可持久化的生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    WARNING = "warning"
    # 旧数据中保留的终态；新任务通过 SUCCEEDED 表示正常完成。
    COMPLETED = "completed"
    FAILED = "failed"
    # 旧 WebUI 路径曾写入 cancelled；新取消事件统一映射为 ABORTED。
    CANCELLED = "cancelled"
    ABORTED = "aborted"
    SKIPPED = "skipped"
