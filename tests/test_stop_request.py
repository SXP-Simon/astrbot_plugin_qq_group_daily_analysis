"""不依赖 AstrBot 的停止协作对象及其应用入口。"""

import asyncio
from unittest.mock import Mock

import pytest

from src.application.services.stop_request import StopRequest


@pytest.mark.asyncio
async def test_reading_requested_does_not_probe_or_cancel_tasks():
    probe = Mock(return_value=True)
    request = StopRequest(probe)
    owned = asyncio.create_task(asyncio.Event().wait())
    try:
        # 登记阶段显式刷新，但此时外部来源尚未请求停止。
        probe.return_value = False
        request.cancel_on_stop(owned)
        probe.reset_mock()
        probe.return_value = True
        assert request.requested is False
        assert request.requested is False
        probe.assert_not_called()
        assert owned.cancelling() == 0

        assert request.refresh() is True
        probe.assert_called_once_with()
        assert request.requested is True
        await asyncio.gather(owned, return_exceptions=True)
        assert owned.cancelled()
        assert owned.cancelling() == 1
        probe.return_value = False
        assert request.refresh() is True
        probe.assert_called_once_with()
        await asyncio.wait_for(request.wait(), timeout=1)
    finally:
        if not owned.done():
            owned.cancel()
        await asyncio.gather(owned, return_exceptions=True)
