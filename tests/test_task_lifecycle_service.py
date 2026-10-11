"""任务生命周期服务与持久化并发保护测试。"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock, get_ident

import pytest

from src.application.services.task_lifecycle_service import (
    ConcurrentTaskTransitionError,
    TaskLifecycleService,
)
from src.domain.services.task_state_machine import IllegalStateTransitionError
from src.domain.value_objects.task_event import TaskEvent
from src.domain.value_objects.task_status import TaskStatus
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.shared.trace_context import TraceContext


@pytest.fixture
def lifecycle(tmp_path: Path) -> tuple[TraceSQLiteStore, TaskLifecycleService]:
    """创建隔离的 SQLite 生命周期服务，并设置 TraceContext 依赖。"""
    store = TraceSQLiteStore(tmp_path / "lifecycle.db")
    service = TaskLifecycleService(store)
    TraceContext.set_global_store(store)
    TraceContext.set_global_lifecycle_service(service)
    yield store, service
    TraceContext.set_global_lifecycle_service(None)
    TraceContext.set_global_store(None)


def test_trace_finish_is_event_only_and_terminal_state_is_immutable(lifecycle):
    store, _ = lifecycle
    trace = TraceContext.set("terminal-trace")

    with pytest.raises(AttributeError):
        setattr(trace, "status", TaskStatus.SUCCEEDED.value)

    trace.finish(event=TaskEvent.SUCCEED)

    assert trace.status == TaskStatus.SUCCEEDED.value
    with pytest.raises(IllegalStateTransitionError):
        trace.finish(event=TaskEvent.FAIL)
    assert store.get_trace("terminal-trace")["status"] == TaskStatus.SUCCEEDED.value


def test_repeated_terminal_event_is_idempotent_without_changing_completion_time(
    lifecycle,
):
    store, _ = lifecycle
    trace = TraceContext.set("idempotent-trace")
    trace.finish(event=TaskEvent.SUCCEED)
    completed_at = store.get_trace("idempotent-trace")["completed_at"]

    trace.finish(event=TaskEvent.SUCCEED)

    assert trace.status == TaskStatus.SUCCEEDED.value
    assert store.get_trace("idempotent-trace")["completed_at"] == completed_at


def test_stale_expected_terminal_status_is_checked_before_idempotent_success(
    lifecycle,
):
    store, service = lifecycle
    store.save_trace(
        {"trace_id": "stale-idempotent-trace", "group_id": "group", "status": "running"}
    )

    with pytest.raises(ConcurrentTaskTransitionError):
        service.transition(
            "stale-idempotent-trace",
            TaskEvent.SUCCEED,
            expected_status=TaskStatus.SUCCEEDED,
        )

    persisted = store.get_trace("stale-idempotent-trace")
    assert persisted is not None
    assert persisted["status"] == TaskStatus.RUNNING.value


def test_cancel_finalizes_open_spans_as_aborted(lifecycle):
    store, _ = lifecycle
    trace = TraceContext.set("cancelled-trace")
    span_context = trace.span("LONG_RUNNING_STAGE")
    span_context.__enter__()

    trace.finish(event=TaskEvent.CANCEL, error_message="cancelled")

    persisted = store.get_trace("cancelled-trace")
    assert persisted is not None
    assert persisted["status"] == TaskStatus.ABORTED.value
    assert persisted["spans"][0]["status"] == "aborted"
    span_context.__exit__(None, None, None)
    assert store.get_trace("cancelled-trace")["spans"][0]["status"] == "aborted"


def test_stale_transition_is_rejected_without_replacing_terminal_state(lifecycle):
    store, service = lifecycle
    store.save_trace(
        {"trace_id": "stale-trace", "group_id": "group", "status": "running"}
    )
    service.transition("stale-trace", TaskEvent.SUCCEED)

    with pytest.raises(ConcurrentTaskTransitionError):
        service.transition(
            "stale-trace",
            TaskEvent.FAIL,
            expected_status=TaskStatus.RUNNING,
        )

    assert store.get_trace("stale-trace")["status"] == TaskStatus.SUCCEEDED.value


def test_repository_rejects_transition_event_not_in_domain_matrix(lifecycle):
    store, service = lifecycle
    store.save_trace(
        {"trace_id": "guarded-trace", "group_id": "group", "status": "running"}
    )
    service.transition("guarded-trace", TaskEvent.SUCCEED)

    with pytest.raises(IllegalStateTransitionError):
        store.transition_trace_status(
            "guarded-trace",
            TaskStatus.SUCCEEDED,
            TaskEvent.FAIL,
            completed_at=200.0,
            duration_ms=100.0,
            error_stage=None,
            error_message="stale failure",
            stack_trace=None,
        )

    persisted = store.get_trace("guarded-trace")
    assert persisted is not None
    assert persisted["status"] == TaskStatus.SUCCEEDED.value
    assert persisted["error_message"] is None


def test_snapshot_save_cannot_overwrite_task_lifecycle(lifecycle):
    store, service = lifecycle
    store.save_trace(
        {"trace_id": "snapshot-trace", "group_id": "group", "status": "running"}
    )
    service.transition("snapshot-trace", TaskEvent.FAIL, error_message="failed")

    store.save_trace(
        {
            "trace_id": "snapshot-trace",
            "group_id": "group",
            "status": "running",
            "error_message": "stale snapshot",
            "extra": {"report_files": [{"filename": "report.html"}]},
        }
    )

    persisted = store.get_trace("snapshot-trace")
    assert persisted is not None
    assert persisted["status"] == TaskStatus.FAILED.value
    assert persisted["error_message"] == "failed"
    assert persisted["extra"]["report_files"][0]["filename"] == "report.html"


def test_stale_snapshot_cannot_reopen_terminal_span(lifecycle):
    store, service = lifecycle
    stale_snapshot = {
        "trace_id": "span-race-trace",
        "group_id": "group",
        "status": TaskStatus.RUNNING.value,
        "spans": [
            {
                "span_id": "span-race-trace_FETCH_1",
                "stage_name": "FETCH",
                "status": "running",
                "started_at": 100.0,
                "payload": {},
            }
        ],
    }
    store.save_trace(stale_snapshot)
    service.transition("span-race-trace", TaskEvent.CANCEL)
    immediately_persisted = store.get_trace("span-race-trace")
    assert immediately_persisted is not None
    assert immediately_persisted["spans"][0]["status"] == "aborted"

    store.save_trace(stale_snapshot)

    persisted = store.get_trace("span-race-trace")
    assert persisted is not None
    assert persisted["status"] == TaskStatus.ABORTED.value
    assert persisted["spans"][0]["status"] == "aborted"


def test_only_one_concurrent_transition_from_same_status_wins(lifecycle):
    store, _ = lifecycle
    store.save_trace(
        {"trace_id": "racing-trace", "group_id": "group", "status": "running"}
    )
    barrier = Barrier(2)
    first_reads: set[int] = set()
    first_reads_lock = Lock()

    class RacingRepository:
        """让两个用例在读取同一旧状态后再竞争 CAS。"""

        def get_task_status(self, trace_id: str) -> TaskStatus | None:
            status = store.get_task_status(trace_id)
            thread_id = get_ident()
            with first_reads_lock:
                is_first_read = thread_id not in first_reads
                first_reads.add(thread_id)
            if is_first_read:
                barrier.wait(timeout=5)
            return status

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
            return store.transition_trace_status(
                trace_id,
                expected_status,
                event,
                completed_at=completed_at,
                duration_ms=duration_ms,
                error_stage=error_stage,
                error_message=error_message,
                stack_trace=stack_trace,
            )

    service = TaskLifecycleService(RacingRepository())

    def transition(event: TaskEvent) -> TaskStatus | None:
        try:
            return service.transition("racing-trace", event)
        except ConcurrentTaskTransitionError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(transition, [TaskEvent.SUCCEED, TaskEvent.FAIL])
        )

    assert sum(outcome is not None for outcome in outcomes) == 1
    persisted = store.get_trace("racing-trace")
    assert persisted is not None
    assert persisted["status"] in {
        TaskStatus.SUCCEEDED.value,
        TaskStatus.FAILED.value,
    }
