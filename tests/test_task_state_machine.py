"""任务状态机合法转移与终态保护测试。"""

import pytest

from src.domain.services.task_state_machine import (
    IllegalStateTransitionError,
    TaskStateMachine,
)
from src.domain.value_objects.task_event import TaskEvent
from src.shared.constants import TaskStatus


@pytest.mark.parametrize(
    ("event", "target"),
    [
        (TaskEvent.SUCCEED, TaskStatus.SUCCEEDED),
        (TaskEvent.WARN, TaskStatus.WARNING),
        (TaskEvent.FAIL, TaskStatus.FAILED),
        (TaskEvent.CANCEL, TaskStatus.ABORTED),
        (TaskEvent.ABORT, TaskStatus.ABORTED),
        (TaskEvent.SKIP, TaskStatus.SKIPPED),
    ],
)
def test_running_task_accepts_only_terminal_outcome_events(
    event: TaskEvent, target: TaskStatus
):
    assert TaskStateMachine.transition(TaskStatus.RUNNING, event) == target


@pytest.mark.parametrize(
    "status",
    [
        TaskStatus.SUCCEEDED,
        TaskStatus.WARNING,
        TaskStatus.FAILED,
        TaskStatus.ABORTED,
        TaskStatus.SKIPPED,
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    ],
)
def test_terminal_statuses_have_only_idempotent_self_transitions(status: TaskStatus):
    for event in TaskEvent:
        target = TaskStateMachine.VALID_TRANSITIONS.get((status, event))
        if target == status:
            assert TaskStateMachine.transition(status, event) == status
            continue
        with pytest.raises(IllegalStateTransitionError):
            TaskStateMachine.transition(status, event)


def test_pending_legacy_status_has_no_unverified_transitions():
    for event in TaskEvent:
        with pytest.raises(IllegalStateTransitionError):
            TaskStateMachine.transition(TaskStatus.PENDING, event)
