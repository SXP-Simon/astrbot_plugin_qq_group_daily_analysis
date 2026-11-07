"""会话防重、旧共享资源保护及取消后释放的竞争回归。"""

import asyncio

import pytest

from src.application.services.task_guard import DuplicateGroupTaskError, TaskGuard


@pytest.mark.asyncio
async def test_sessions_are_independent_but_same_session_is_exclusive():
    guard = TaskGuard()
    async with guard.group_lock("123", "incremental", "first"):
        assert guard.is_group_running("123", "incremental", "first")
        assert not guard.is_group_running("123", "incremental", "second")
        async with guard.group_lock("123", "incremental", "second"):
            with pytest.raises(DuplicateGroupTaskError):
                async with guard.group_lock("123", "incremental", "first"):
                    pytest.fail("同一会话不能重复执行")
        async with guard.group_lock("123", "final", "first"):
            assert guard.is_group_running("123", "final", "first")
        with pytest.raises(DuplicateGroupTaskError):
            async with guard.group_lock("123", "incremental"):
                pytest.fail("旧共享资源不能越过正在执行的会话")
    async with guard.group_lock("123", "incremental"):
        with pytest.raises(DuplicateGroupTaskError):
            async with guard.group_lock("123", "incremental", "second"):
                pytest.fail("会话不能越过旧共享资源保护")
    assert not guard.active_tasks


@pytest.mark.asyncio
async def test_cancel_while_waiting_releases_only_own_session_and_keeps_global_limit():
    guard = TaskGuard(1)
    entered = asyncio.Event()

    async def waiting():
        async with guard.group_lock("123", "incremental", "second"):
            entered.set()
            async with guard.llm_slot("123", "incremental"):
                pytest.fail("全局并发槽位不能被会话隔离绕过")

    async with guard.group_lock("123", "incremental", "first"):
        async with guard.llm_slot("123", "incremental"):
            task = asyncio.create_task(waiting())
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert guard.is_group_running("123", "incremental", "first")
            assert not guard.is_group_running("123", "incremental", "second")
    async with guard.group_lock("123", "incremental", "second"):
        async with guard.llm_slot("123", "incremental"):
            assert guard.llm_semaphore.locked()
    assert not guard.active_tasks

@pytest.mark.asyncio
@pytest.mark.parametrize("prior", [{}, {"llm_stage": "prior-stage", "llm_group_id": "prior-group"}])
async def test_cancelled_queue_restores_trace_metadata_without_releasing_foreign_slot(monkeypatch, prior):
    """排队取消也恢复追踪上下文，不能释放别的请求持有的槽位。"""
    from src.shared.trace_context import TraceContext

    metadata = {"unrelated": "keep", **prior}
    trace = TraceContext(trace_id="queue-test", metadata=metadata.copy())
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    guard = TaskGuard(1)
    await guard.llm_semaphore.acquire()
    entered = asyncio.Event()

    async def waiting():
        try:
            async with guard.llm_slot("123", "new-stage"):
                pytest.fail("排队取消的请求不应进入槽位")
        finally:
            entered.set()

    task = asyncio.create_task(waiting())
    try:
        await asyncio.sleep(0)
        assert trace.metadata["llm_stage"] == "new-stage"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert entered.is_set()
        assert trace.metadata == metadata
        assert guard.llm_semaphore.locked()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        guard.llm_semaphore.release()
