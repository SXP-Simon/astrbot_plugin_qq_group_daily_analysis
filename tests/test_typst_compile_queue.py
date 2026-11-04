"""验证原生编译串行预算、排队取消与任务阶段归属。"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.reporting import typst_process
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_queued_compile_does_not_spawn_and_preserves_next_slot(tmp_path, monkeypatch, cancel):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    started, release = asyncio.Event(), asyncio.Event()
    active = 0
    maximum = 0
    calls = []

    async def execute(job, fonts, timeout, raster_ppi=144):
        nonlocal active, maximum
        calls.append(job.name)
        active += 1
        maximum = max(maximum, active)
        try:
            if job.name == "first":
                started.set()
                await release.wait()
            return None
        finally:
            active -= 1

    monkeypatch.setattr(typst_process, "_execute_typst_worker", execute)
    first = asyncio.create_task(typst_process.run_typst_worker(tmp_path / "first", tmp_path, 5))
    await started.wait()
    second = asyncio.create_task(typst_process.run_typst_worker(tmp_path / "second", tmp_path, 5 if cancel else .02))
    if cancel:
        await asyncio.sleep(0)
        second.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        await second
    assert calls == ["first"]
    release.set()
    await first
    await typst_process.run_typst_worker(tmp_path / "third", tmp_path, 5)
    assert calls == ["first", "third"]
    assert maximum == 1


@pytest.mark.asyncio
async def test_queue_wait_does_not_consume_compilation_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    started, release = asyncio.Event(), asyncio.Event()
    queued = asyncio.Event()
    remaining = []

    async def execute(job, fonts, timeout, raster_ppi=144):
        if job.name == "first":
            started.set()
            await release.wait()
        else:
            remaining.append(timeout)

    async def next_compile():
        queued.set()
        await typst_process.run_typst_worker(tmp_path / "second", tmp_path, 5)

    monkeypatch.setattr(typst_process, "_execute_typst_worker", execute)
    first = asyncio.create_task(typst_process.run_typst_worker(tmp_path / "first", tmp_path, 5))
    await started.wait()
    second = asyncio.create_task(next_compile())
    await queued.wait()
    await asyncio.sleep(.02)
    assert not remaining
    release.set()
    await asyncio.gather(first, second)
    assert remaining == [5]


@pytest.mark.asyncio
async def test_compiler_failure_does_not_hold_slot(tmp_path, monkeypatch):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    execute = AsyncMock(side_effect=[RuntimeError("编译失败"), None])
    monkeypatch.setattr(typst_process, "_execute_typst_worker", execute)
    with pytest.raises(RuntimeError, match="编译失败"):
        await typst_process.run_typst_worker(tmp_path, tmp_path, 1)
    await typst_process.run_typst_worker(tmp_path, tmp_path, 1)
    assert execute.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["TYPST_COMPILE", "TYPST_RECOVERY"])
async def test_compile_queue_is_child_of_actual_compile_span(tmp_path, monkeypatch, stage):
    trace = TraceContext(trace_id="native-compile-queue")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(typst_process, "_execute_typst_worker", AsyncMock(return_value=None))
    async with trace.span_async("RENDER_REPORT"):
        async with trace.span_async(stage) as parent:
            await typst_process.run_typst_worker(tmp_path, tmp_path, 1)
    queue = next(span for span in trace._spans if span["stage_name"] == "IMAGE_RENDER_QUEUE")
    assert queue["payload"]["parent_span_id"] == parent["span_id"]
    assert queue["payload"]["scope"] == "native_compile"
    assert queue["status"] == "success"


def test_compile_slots_do_not_bind_future_event_loops(monkeypatch):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))

    async def scenario():
        with monkeypatch.context() as patch:
            patch.setattr(typst_process, "_execute_typst_worker", AsyncMock(return_value=None))
            await asyncio.gather(*(typst_process.run_typst_worker(Path("job"), Path("fonts"), 1) for _ in range(2)))

    asyncio.run(scenario())
    asyncio.run(scenario())
