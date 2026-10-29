"""SQLite 异步边界与连接释放回归测试。"""

import asyncio
import sqlite3
import threading

import pytest

from src.domain.value_objects.task_event import TaskEvent
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
async def test_trace_write_lock_does_not_block_event_loop(tmp_path):
    store = TraceSQLiteStore(tmp_path / "traces.db")
    locked, release = threading.Event(), threading.Event()

    def hold_lock():
        conn = sqlite3.connect(store.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            locked.set()
            assert release.wait(3)
        finally:
            conn.rollback()
            conn.close()

    locker = asyncio.create_task(asyncio.to_thread(hold_lock))
    await asyncio.to_thread(locked.wait, 2)
    TraceContext.set_global_store(store)
    trace = None
    try:
        writer = asyncio.create_task(
            TraceContext.set_async("locked-write", group_id="123")
        )
        ticks = 0
        while ticks < 10:
            await asyncio.sleep(0.005)
            ticks += 1
        assert not writer.done()
        release.set()
        trace = await asyncio.wait_for(writer, 2)
        assert store.get_trace(trace.trace_id) is not None
        assert ticks == 10
        await asyncio.to_thread(trace.finish, TaskEvent.SUCCEED)
        assert store.get_trace(trace.trace_id)["status"] == "succeeded"
    finally:
        release.set()
        await locker
        TraceContext.set_global_store(None)
        if trace and trace._token:
            # set_async 运行在子任务，令牌只能由该任务复位。
            trace._token = None


@pytest.mark.asyncio
async def test_async_trace_context_keeps_binding_and_persists(tmp_path):
    store = TraceSQLiteStore(tmp_path / "traces.db")
    TraceContext.set_global_store(store)
    previous = TraceContext.current()
    try:
        async with TraceContext(trace_id="async-context") as trace:
            assert TraceContext.current() is trace
            async with trace.span_async("test"):
                await asyncio.sleep(0)
        assert TraceContext.current() is previous
        assert store.get_trace("async-context")["status"] == "succeeded"
    finally:
        TraceContext.set_global_store(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["set", "context"])
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_async_trace_initialization_failure_restores_parent(
    monkeypatch, entry, error_type
):
    import src.shared.trace_context as trace_module

    monkeypatch.setattr(trace_module, "_global_trace_store", None)

    async def failing_persist(self):
        raise error_type("initial save interrupted")

    monkeypatch.setattr(TraceContext, "persist_snapshot_async", failing_persist)
    with TraceContext(trace_id="parent-before-failure") as parent:
        try:
            with pytest.raises(error_type):
                if entry == "set":
                    await TraceContext.set_async("failed-initialization")
                else:
                    async with TraceContext(trace_id="failed-initialization"):
                        pytest.fail("failed initialization must not enter the body")
            assert TraceContext.current() is parent
            assert TraceContext.get_active_trace("failed-initialization") is None
        finally:
            trace_module._active_traces.pop("failed-initialization", None)
