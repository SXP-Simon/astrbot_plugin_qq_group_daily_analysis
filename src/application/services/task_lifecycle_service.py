"""分析任务生命周期用例服务。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ...domain.services.task_state_machine import TaskStateMachine

if TYPE_CHECKING:
    from ...domain.repositories.task_lifecycle_repository import (
        ITaskLifecycleRepository,
    )
    from ...domain.value_objects.task_event import TaskEvent
    from ...domain.value_objects.task_status import TaskStatus


class ConcurrentTaskTransitionError(RuntimeError):
    """任务状态已被并发操作改变，当前跃迁未能提交。"""


class TaskLifecycleService:
    """通过领域状态机和持久层 CAS 执行任务状态跃迁。"""

    def __init__(self, lifecycle_repository: ITaskLifecycleRepository) -> None:
        """创建任务生命周期服务。

        Args:
            lifecycle_repository: 提供状态读取与条件跃迁的仓储契约。
        """
        self.lifecycle_repository = lifecycle_repository

    def transition(
        self,
        trace_id: str,
        event: TaskEvent,
        *,
        expected_status: TaskStatus | None = None,
        completed_at: float | None = None,
        duration_ms: float | None = None,
        error_stage: str | None = None,
        error_message: str | None = None,
        stack_trace: str | None = None,
    ) -> TaskStatus:
        """按事件校验并提交一次任务状态跃迁。

        Args:
            trace_id: 任务追踪标识。
            event: 调用方发送的生命周期事件。
            expected_status: 调用方观察到的状态，用于阻止陈旧上下文覆盖。
            completed_at: 完成时间；省略时使用当前时间。
            duration_ms: 已知的任务耗时；省略时由仓储依据开始时间计算。
            error_stage: 失败发生的阶段名称。
            error_message: 失败或取消原因。
            stack_trace: 失败堆栈文本。

        Returns:
            TaskStatus: 事件映射到的终态。

        Raises:
            IllegalStateTransitionError: 当前状态不允许该事件。
            ConcurrentTaskTransitionError: 数据库状态已被其他操作改变。
            KeyError: 追踪记录不存在。
        """
        current = expected_status or self.lifecycle_repository.get_task_status(trace_id)
        if current is None:
            raise KeyError(f"任务追踪记录不存在: {trace_id}")

        target = TaskStateMachine.transition(current, event)
        transition_time = completed_at if completed_at is not None else time.time()
        changed = self.lifecycle_repository.transition_trace_status(
            trace_id=trace_id,
            expected_status=current,
            event=event,
            completed_at=transition_time,
            duration_ms=duration_ms,
            error_stage=error_stage,
            error_message=error_message,
            stack_trace=stack_trace,
        )
        if not changed:
            latest_status = self.lifecycle_repository.get_task_status(trace_id)
            if latest_status == target:
                return target
            latest_value = latest_status.value if latest_status else "missing"
            raise ConcurrentTaskTransitionError(
                f"任务 {trace_id} 状态已从 [{current.value}] 并发变为 "
                f"[{latest_value}]，拒绝提交事件 [{event.value}]"
            )
        return target
