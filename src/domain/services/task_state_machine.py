"""分析任务生命周期状态机。"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Mapping

from ..value_objects.task_event import TaskEvent
from ..value_objects.task_status import TaskStatus


class IllegalStateTransitionError(ValueError):
    """任务收到当前状态不允许的生命周期事件。"""

    def __init__(self, current: TaskStatus, event: TaskEvent):
        """保存非法转移的源状态和事件。

        Args:
            current: 任务当前状态。
            event: 调用方发送的生命周期事件。
        """
        self.current = current
        self.event = event
        super().__init__(
            f"禁止任务状态从 [{current.value}] 经事件 [{event.value}] 转移"
        )


class TaskStateMachine:
    """以唯一白名单校验任务状态转移。"""

    VALID_TRANSITIONS: ClassVar[Mapping[tuple[TaskStatus, TaskEvent], TaskStatus]] = (
        MappingProxyType(
            {
                (TaskStatus.RUNNING, TaskEvent.SUCCEED): TaskStatus.SUCCEEDED,
                (TaskStatus.RUNNING, TaskEvent.WARN): TaskStatus.WARNING,
                (TaskStatus.RUNNING, TaskEvent.FAIL): TaskStatus.FAILED,
                (TaskStatus.RUNNING, TaskEvent.TIMEOUT): TaskStatus.FAILED,
                (TaskStatus.RUNNING, TaskEvent.CANCEL): TaskStatus.ABORTED,
                (TaskStatus.RUNNING, TaskEvent.ABORT): TaskStatus.ABORTED,
                (TaskStatus.RUNNING, TaskEvent.SKIP): TaskStatus.SKIPPED,
                # 同一终态结果的事件重放是无副作用的幂等自环。
                (TaskStatus.COMPLETED, TaskEvent.SUCCEED): TaskStatus.COMPLETED,
                (TaskStatus.SUCCEEDED, TaskEvent.SUCCEED): TaskStatus.SUCCEEDED,
                (TaskStatus.WARNING, TaskEvent.WARN): TaskStatus.WARNING,
                (TaskStatus.FAILED, TaskEvent.FAIL): TaskStatus.FAILED,
                (TaskStatus.FAILED, TaskEvent.TIMEOUT): TaskStatus.FAILED,
                (TaskStatus.CANCELLED, TaskEvent.CANCEL): TaskStatus.CANCELLED,
                (TaskStatus.ABORTED, TaskEvent.CANCEL): TaskStatus.ABORTED,
                (TaskStatus.ABORTED, TaskEvent.ABORT): TaskStatus.ABORTED,
                (TaskStatus.SKIPPED, TaskEvent.SKIP): TaskStatus.SKIPPED,
            }
        )
    )

    @classmethod
    def transition(cls, current: TaskStatus, event: TaskEvent) -> TaskStatus:
        """校验事件并返回唯一允许的目标状态。

        白名单中仅包含运行态跃迁和明确允许的幂等终态自环。

        Args:
            current: 任务当前状态。
            event: 调用方发送的生命周期事件。

        Returns:
            TaskStatus: 事件对应的目标状态。

        Raises:
            IllegalStateTransitionError: 当前状态不允许该事件。
            TypeError: 状态或事件不是对应的领域枚举。
        """
        if type(current) is not TaskStatus:
            raise TypeError("current 必须是 TaskStatus")
        if type(event) is not TaskEvent:
            raise TypeError("event 必须是 TaskEvent")
        target = cls.VALID_TRANSITIONS.get((current, event))
        if target is None:
            raise IllegalStateTransitionError(current, event)
        return target
