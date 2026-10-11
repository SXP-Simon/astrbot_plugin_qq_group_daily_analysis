"""任务生命周期持久化契约。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..value_objects.task_event import TaskEvent
    from ..value_objects.task_status import TaskStatus


class ITaskLifecycleRepository(Protocol):
    """任务生命周期用例读取状态并执行条件跃迁所需的最小仓储契约。"""

    def get_task_status(self, trace_id: str) -> TaskStatus | None:
        """读取任务的当前生命周期状态。

        Args:
            trace_id: 任务追踪标识。

        Returns:
            TaskStatus | None: 当前状态；记录不存在时返回 None。
        """
        ...

    def transition_trace_status(
        self,
        trace_id: str,
        expected_status: TaskStatus,
        event: TaskEvent,
        *,
        completed_at: float,
        duration_ms: float | None,
        error_stage: str | None,
        error_message: str | None,
        stack_trace: str | None,
    ) -> bool:
        """仅当持久化状态匹配预期旧状态时提交事件跃迁。

        Args:
            trace_id: 任务追踪标识。
            expected_status: 调用方观察到的旧状态。
            event: 请求的生命周期事件；目标状态由领域状态机决定。
            completed_at: 任务完成时间。
            duration_ms: 已知的任务耗时；为空时由仓储按开始时间计算。
            error_stage: 失败或中止阶段。
            error_message: 失败或中止原因。
            stack_trace: 失败堆栈文本。

        Returns:
            bool: 状态仍匹配且更新成功时返回 True。
        """
        ...
