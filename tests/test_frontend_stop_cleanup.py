import asyncio
import gc
import weakref

import pytest
from frontend_stop_support import StubTaskManager, make_handler

from src.application.services.stop_request import StopRequest


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_twice", [False, True])
async def test_host_cancellation_retrieves_child_cleanup_errors(
    cancel_twice, monkeypatch
):
    from src.application.handlers import analysis_command_handler as module

    started = asyncio.Event()
    cancelled = asyncio.Event()
    release = asyncio.Event()
    task_ref = None
    logs = []

    async def work():
        nonlocal task_ref
        task_ref = weakref.ref(asyncio.current_task())
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            if cancel_twice:
                await release.wait()
            raise RuntimeError("取消清理失败") from None

    monkeypatch.setattr(
        module.logger, "warning", lambda text, *_args, **_kwargs: logs.append(text)
    )
    handler = make_handler(object(), StubTaskManager())
    loop = asyncio.get_running_loop()
    errors = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _, context: errors.append(context))
    parent = asyncio.create_task(handler._await_with_stop(work(), StopRequest()))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        parent.cancel()
        await asyncio.wait_for(cancelled.wait(), timeout=1)
        if cancel_twice:
            parent.cancel()
        with pytest.raises(asyncio.CancelledError):
            await parent
        release.set()
        # 不 gather 子任务，避免测试自己取回异常而掩盖生产代码的问题。
        for _ in range(10):
            await asyncio.sleep(0)
        assert task_ref is not None
        if task_ref() is not None:
            assert task_ref().done()
        del parent
        gc.collect()
        await asyncio.sleep(0)
        assert not errors
        assert any("取消清理失败" in str(entry) for entry in logs)
    finally:
        release.set()
        loop.set_exception_handler(previous)
