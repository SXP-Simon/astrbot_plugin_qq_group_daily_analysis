"""任务生命周期事件值对象。"""

from enum import Enum


class TaskEvent(str, Enum):
    """调用方可发送的任务生命周期事件。"""

    SUCCEED = "succeed"
    WARN = "warn"
    FAIL = "fail"
    CANCEL = "cancel"
    ABORT = "abort"
    SKIP = "skip"
