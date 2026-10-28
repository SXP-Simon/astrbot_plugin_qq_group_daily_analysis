"""WebUI 活跃任务取消、超时与生命周期竞争测试。"""

import asyncio
import time
from pathlib import Path

import pytest

from src.application.services.task_lifecycle_service import (
    ConcurrentTaskTransitionError,
    TaskLifecycleService,
)
from src.domain.value_objects.task_event import TaskEvent
from src.domain.value_objects.task_status import TaskStatus
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.active_task_manager import ActiveTaskManager
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
async def test_reaper_cancels_task_even_when_another_event_already_finished_trace(
    tmp_path: Path,
):
    store = TraceSQLiteStore(tmp_path / "terminal_reaper_race.db")
    store.save_trace(
        {"trace_id": "finished_but_active", "group_id": "999", "status": "running"}
    )
    lifecycle_service = TaskLifecycleService(store)
    lifecycle_service.transition("finished_but_active", TaskEvent.SUCCEED)
    manager = ActiveTaskManager(lifecycle_service=lifecycle_service)

    async def hung_job():
        await asyncio.sleep(100)

    task = asyncio.create_task(hung_job())
    await manager.register_task(
        task_id="finished_but_active",
        group_id="999",
        group_name="超时群",
        current_stage="LLM_ANALYSIS",
        asyncio_task=task,
    )
    manager._tasks["finished_but_active"].last_heartbeat = time.time() - 200
    manager.start_reaper(interval_seconds=0.01, timeout_seconds=180)
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 3)
    manager.stop_reaper()
    if manager._reaper_task:
        await asyncio.gather(manager._reaper_task, return_exceptions=True)

    persisted = store.get_trace("finished_but_active")
    assert task.cancelled()
    assert persisted is not None
    assert persisted["status"] == TaskStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_timeout_event_closes_open_span_and_rejects_late_cancel(
    tmp_path: Path,
):
    store = TraceSQLiteStore(tmp_path / "timeout_cancel_race.db")
    lifecycle_service = TaskLifecycleService(store)
    TraceContext.set_global_store(store)
    TraceContext.set_global_lifecycle_service(lifecycle_service)
    manager = ActiveTaskManager(lifecycle_service=lifecycle_service)
    TraceContext.set_active_task_manager(manager)
    task: asyncio.Task[None] | None = None
    transition_conflicts: list[ConcurrentTaskTransitionError] = []

    try:
        with TraceContext(trace_id="timeout_cancel_race") as trace:
            span_entered = asyncio.Event()

            async def job_with_open_span() -> None:
                try:
                    with trace.span("LLM_ANALYSIS"):
                        span_entered.set()
                        await asyncio.sleep(100)
                except asyncio.CancelledError:
                    try:
                        trace.finish(event=TaskEvent.CANCEL)
                    except ConcurrentTaskTransitionError as transition_error:
                        transition_conflicts.append(transition_error)
                    raise

            task = asyncio.create_task(job_with_open_span())
            await span_entered.wait()
            await manager.register_task(
                task_id="timeout_cancel_race",
                group_id="999",
                current_stage="LLM_ANALYSIS",
                asyncio_task=task,
            )
            manager._tasks["timeout_cancel_race"].last_heartbeat = time.time() - 200
            manager.start_reaper(interval_seconds=0.01, timeout_seconds=180)
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 3)
            manager.stop_reaper()
            if manager._reaper_task:
                await asyncio.gather(manager._reaper_task, return_exceptions=True)
            await asyncio.gather(task, return_exceptions=True)

            persisted = store.get_trace("timeout_cancel_race")
            assert task.cancelled()
            assert len(transition_conflicts) == 1
            assert trace.status == TaskStatus.FAILED.value
            assert persisted is not None
            assert persisted["status"] == TaskStatus.FAILED.value
            assert persisted["spans"][0]["status"] == "failed"
    finally:
        manager.stop_reaper()
        if manager._reaper_task:
            await asyncio.gather(manager._reaper_task, return_exceptions=True)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        TraceContext.set_active_task_manager(None)
        TraceContext.set_global_lifecycle_service(None)
        TraceContext.set_global_store(None)


@pytest.mark.asyncio
async def test_stopping_reaper_finishes_inflight_timeout(tmp_path):
    import threading

    store = TraceSQLiteStore(tmp_path / "stopping-reaper.db")
    store.save_trace({"trace_id": "stopping", "group_id": "123", "status": "running"})
    started, release = threading.Event(), threading.Event()

    class DelayedLifecycle(TaskLifecycleService):
        def transition(self, *args, **kwargs):
            started.set()
            assert release.wait(3)
            return super().transition(*args, **kwargs)

    manager = ActiveTaskManager(lifecycle_service=DelayedLifecycle(store))
    job = asyncio.create_task(asyncio.sleep(100))
    await manager.register_task(task_id="stopping", group_id="123", asyncio_task=job)
    manager._tasks["stopping"].last_heartbeat = time.time() - 200
    manager.start_reaper(interval_seconds=0.001, timeout_seconds=180)
    try:
        assert await asyncio.to_thread(started.wait, 2)
        manager.stop_reaper()
        await asyncio.sleep(0)
        assert not job.done()
        release.set()
        await asyncio.wait_for(manager._reaper_task, 3)
        await asyncio.gather(job, return_exceptions=True)
        assert job.cancelled()
        assert not manager.get_active_tasks()
        assert store.get_trace("stopping")["status"] == "failed"
    finally:
        release.set()
        manager.stop_reaper()
        if not job.done():
            job.cancel()
        await asyncio.gather(job, return_exceptions=True)
