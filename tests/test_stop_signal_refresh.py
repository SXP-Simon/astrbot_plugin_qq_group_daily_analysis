import asyncio
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from src.application.services.stop_request import StopRequest
from src.infrastructure.platform.stop_signal import FrontendStopWatcher


class HostStopEvent:
    def __init__(self):
        self.extras = {}
        self.read = asyncio.Event()

    def get_extra(self, key, default=None):
        self.read.set()
        return self.extras.get(key, default)

    def set_extra(self, key, value):
        self.extras[key] = value


@pytest.mark.asyncio
@pytest.mark.parametrize("poll_started", [False, True])
async def test_native_stop_cancels_registered_listener_without_agent_callback_override(monkeypatch, poll_started):
    host_registry = Mock()
    host_registry.get_background_stop_signal.side_effect = lambda event: asyncio.Event()
    registered = {}

    def register(event, task):
        registered[task] = event
        task.add_done_callback(lambda done: registered.pop(done, None))

    host_registry.register_background_task.side_effect = register
    module = ModuleType("astrbot.core.utils.active_event_registry")
    module.active_event_registry = host_registry
    monkeypatch.setitem(sys.modules, module.__name__, module)
    owners = [HostStopEvent() for _ in range(3)]
    origins = ["official:GroupMessage:member_group", "official:GroupMessage:other_group", "other_bot:GroupMessage:member_group"]
    watchers = []
    for owner, origin in zip(owners, origins):
        owner.unified_msg_origin = origin
        watcher = FrontendStopWatcher(owner)
        await watcher.start()
        watchers.append(watcher)
    try:
        if poll_started:
            await owners[0].read.wait()
        # 宿主按原始会话找到登记的任务、设置标记，再取消监听器。
        listener = next(task for task, owner in registered.items() if owner is owners[0])
        owners[0].set_extra("agent_stop_requested", True)
        listener.cancel()
        owners[0].set_extra("agent_stop_requested", False)
        await asyncio.wait_for(watchers[0].stop_request.wait(), 1)
        assert [watcher.stop_request.requested for watcher in watchers] == [True, False, False]
        host_registry.register_agent_stop_callback.assert_not_called()
        host_registry.unregister_agent_stop_callback.assert_not_called()
    finally:
        for watcher in watchers:
            await watcher.stop()
    assert not registered
    assert [watcher.stop_request.requested for watcher in watchers] == [True, False, False]


@pytest.mark.asyncio
async def test_shared_host_signal_survives_agent_flag_reset(monkeypatch):
    host_signal = asyncio.Event()
    registry = Mock()
    registry.get_background_stop_signal.return_value = host_signal
    module = ModuleType("astrbot.core.utils.active_event_registry")
    module.active_event_registry = registry
    monkeypatch.setitem(sys.modules, module.__name__, module)
    event = HostStopEvent()
    event.unified_msg_origin = "official:GroupMessage:group"
    watcher = FrontendStopWatcher(event, poll_interval=60)
    await watcher.start()
    try:
        await event.read.wait()
        host_signal.set()
        event.set_extra("agent_stop_requested", False)
        assert watcher.stop_request.refresh()
    finally:
        await watcher.stop()


@pytest.mark.asyncio
async def test_legacy_host_keeps_foreground_stop_flag_polling(monkeypatch):
    module = ModuleType("astrbot.core.utils.active_event_registry")
    module.active_event_registry = object()
    monkeypatch.setitem(sys.modules, module.__name__, module)
    event = HostStopEvent()
    event.unified_msg_origin = "official:GroupMessage:group"
    watcher = FrontendStopWatcher(event, poll_interval=0.01)
    await watcher.start()
    try:
        event.set_extra("agent_stop_requested", True)
        await asyncio.wait_for(watcher.stop_request.wait(), 1)
    finally:
        await watcher.stop()


@pytest.mark.asyncio
async def test_delivery_check_reads_host_flag_between_polls():
    event = HostStopEvent()
    watcher = FrontendStopWatcher(event, poll_interval=60)
    await watcher.start()
    try:
        await asyncio.wait_for(event.read.wait(), timeout=1)
        event.extras["agent_stop_requested"] = True
        assert watcher.stop_request.requested is False
        assert watcher.stop_request.refresh() is True
        assert watcher.stop_request.requested is True
        await asyncio.wait_for(watcher.stop_request.wait(), timeout=1)
    finally:
        await watcher.stop()


@pytest.mark.asyncio
async def test_stop_only_cancels_owned_tasks_once():
    request = StopRequest()
    started = asyncio.Event()

    async def owned_work():
        started.set()
        await asyncio.Event().wait()

    owned = asyncio.create_task(owned_work())
    independent = asyncio.create_task(asyncio.Event().wait())
    request.cancel_on_stop(owned)
    try:
        await started.wait()
        request.request()
        request.request()
        await asyncio.gather(owned, return_exceptions=True)
        assert owned.cancelled()
        assert owned.cancelling() == 1
        assert not independent.done()
    finally:
        independent.cancel()
        await asyncio.gather(independent, return_exceptions=True)


@pytest.mark.asyncio
async def test_task_registered_after_stop_never_starts():
    event = HostStopEvent()
    event.extras["agent_stop_requested"] = True
    watcher = FrontendStopWatcher(event)
    request = watcher.stop_request
    started = False

    async def work():
        nonlocal started
        started = True

    task = asyncio.create_task(work())
    request.cancel_on_stop(task)
    await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert not started
