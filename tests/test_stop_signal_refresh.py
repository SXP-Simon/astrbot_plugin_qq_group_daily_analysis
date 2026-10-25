import asyncio

import pytest

from src.infrastructure.platform.stop_signal import FrontendStopWatcher, StopRequest


class HostStopEvent:
    def __init__(self):
        self.extras = {}
        self.read = asyncio.Event()

    def get_extra(self, key, default=None):
        self.read.set()
        return self.extras.get(key, default)


@pytest.mark.asyncio
async def test_delivery_check_reads_host_flag_between_polls():
    event = HostStopEvent()
    watcher = FrontendStopWatcher(event, poll_interval=60)
    await watcher.start()
    try:
        await asyncio.wait_for(event.read.wait(), timeout=1)
        event.extras["agent_stop_requested"] = True
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
    request = StopRequest(event)
    started = False

    async def work():
        nonlocal started
        started = True

    task = asyncio.create_task(work())
    request.cancel_on_stop(task)
    await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()
    assert not started
