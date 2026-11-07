"""WebUI 手动任务从接口到后台资源回收的取消契约。"""

import asyncio
import importlib
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_webui_trace_initialization_failure_does_not_leave_active_task(tmp_path, monkeypatch):
    manager = ActiveTaskManager()
    service = MagicMock(execute_daily_analysis=AsyncMock())
    routes = TaskRoutes(TraceSQLiteStore(tmp_path / "traces.db"), manager, service)
    await manager.register_task("init-failure", "123", platform="first", trigger_type="web_ui")
    monkeypatch.setattr(TraceContext, "set_async", AsyncMock(side_effect=OSError("模拟快照存储不可写")))
    await routes._run_triggered_task("init-failure", "123", "示例群", "first")
    assert not manager.get_active_tasks()
    service.execute_daily_analysis.assert_not_awaited()

from src.application.services.task_guard import TaskGuard
from src.application.services.task_lifecycle_service import TaskLifecycleService
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.reporting import typst_process
from src.infrastructure.webui.active_task_manager import ActiveTaskManager
from src.infrastructure.webui.routes.task_routes import TaskRoutes
from src.shared import trace_context
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["queue", "llm", "typst"])
async def test_webui_trigger_can_be_cancelled_during_analysis_or_typst(
    tmp_path, monkeypatch, stage
):
    """通过真实路由、生命周期、并发锁与子进程验证取消传递。"""
    store = TraceSQLiteStore(tmp_path / "cancel.db")
    lifecycle = TaskLifecycleService(store)
    manager = ActiveTaskManager(lifecycle)
    monkeypatch.setattr(trace_context, "_global_trace_store", store)
    monkeypatch.setattr(trace_context, "_global_task_lifecycle_service", lifecycle)
    monkeypatch.setattr(trace_context, "_global_active_task_manager", manager)
    entered = asyncio.Event()
    guard = TaskGuard(1)
    child = None
    create_process = asyncio.create_subprocess_exec

    async def start_worker(*args, **kwargs):
        nonlocal child
        child = await create_process(
            sys.executable, "-c", "import time; time.sleep(120)",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        entered.set()
        return child

    monkeypatch.setattr(typst_process.asyncio, "create_subprocess_exec", start_worker)
    if stage == "queue":
        await guard.llm_semaphore.acquire()

    async def execute(**kwargs):
        async with guard.group_lock("GROUP_OPENID", "daily"):
            if stage == "queue":
                entered.set()
            async with guard.llm_slot("GROUP_OPENID", "web_ui"):
                trace = TraceContext.current()
                async with trace.span_async("TYPST_COMPILE" if stage == "typst" else "LLM_ANALYSIS"):
                    if stage == "typst":
                        await typst_process._execute_typst_worker(tmp_path, tmp_path, 120)
                    else:
                        entered.set()
                        await asyncio.Event().wait()

    service = MagicMock()
    service.is_group_running.return_value = False
    service.bot_manager.resolve_platform_id.side_effect = lambda value: value
    service.execute_daily_analysis = AsyncMock(side_effect=execute)
    service.bot_manager.get_adapter.return_value = MagicMock()
    dispatcher = SimpleNamespace(dispatch=AsyncMock())
    routes = TaskRoutes(store, manager, service, dispatcher)
    route_module = importlib.import_module(TaskRoutes.__module__)
    request = SimpleNamespace(
        json=AsyncMock(return_value={"group_id": "GROUP_OPENID", "platform": "official"}),
        query={},
    )
    monkeypatch.setattr(route_module, "request", request)
    task = None
    try:
        response = await routes.api_trigger_task()
        trace_id = response["data"]["data"]["trace_id"]
        task = manager._tasks[trace_id].asyncio_task
        await asyncio.wait_for(entered.wait(), 5)
        request.json.return_value = {"task_id": trace_id}
        result = await routes.api_cancel_task()
        assert result["data"]["status"] == "ok"
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert not guard.is_group_running("GROUP_OPENID", "daily")
        assert not manager.get_active_tasks()
        assert guard.llm_semaphore._value == (0 if stage == "queue" else 1)
        saved = store.get_trace(trace_id)
        assert saved["status"] == "aborted"
        assert "WebUI" in saved["error_message"]
        assert all(span["status"] != "running" for span in saved["spans"])
        dispatcher.dispatch.assert_not_awaited()
        if stage == "typst":
            assert child is not None and child.returncode is not None
    finally:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if child and child.returncode is None:
            child.kill()
            await child.wait()
        if stage == "queue":
            guard.llm_semaphore.release()


@pytest.mark.asyncio
async def test_webui_can_cancel_before_background_task_initializes_trace(tmp_path):
    """任务已入活跃列表但尚未调度时，缺少 Trace 不得使取消失效。"""
    manager = ActiveTaskManager(TaskLifecycleService(TraceSQLiteStore(tmp_path / "early.db")))
    async def run():
        await asyncio.Event().wait()

    task = asyncio.create_task(run())
    try:
        await manager.register_task("not-started", "GROUP_OPENID", asyncio_task=task)
        assert await manager.cancel_task("not-started")
        await asyncio.gather(task, return_exceptions=True)
        assert task.cancelled()
        assert not manager.get_active_tasks()
        assert not await manager.cancel_task("not-started")
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancel_initializing_trace_does_not_leave_running_archive(tmp_path, monkeypatch):
    """状态查询让出执行权时恰好开始初始化，也需先归档中止再结束协程。"""
    store = TraceSQLiteStore(tmp_path / "initializing.db")
    manager = ActiveTaskManager(TaskLifecycleService(store))
    monkeypatch.setattr(trace_context, "_global_trace_store", store)
    monkeypatch.setattr(trace_context, "_global_task_lifecycle_service", None)
    original_persist = TraceContext.persist_snapshot_async
    initializing = asyncio.Event()

    async def delayed_first_persist(self):
        if not initializing.is_set():
            initializing.set()
            await asyncio.Event().wait()
        await original_persist(self)

    monkeypatch.setattr(TraceContext, "persist_snapshot_async", delayed_first_persist)
    task = asyncio.create_task(TraceContext.set_async("initializing", "GROUP_OPENID"))
    try:
        await manager.register_task("initializing", "GROUP_OPENID", asyncio_task=task)
        assert await manager.cancel_task("initializing")
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 3)
        assert task.cancelled()
        assert store.get_trace("initializing")["status"] == "aborted"
        assert TraceContext.get_active_trace("initializing") is None
        assert not manager.get_active_tasks()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
