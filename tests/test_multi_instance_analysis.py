"""经过真实平台解析与增量仓储的多实例并发回归。"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.services.incremental_analysis_service import IncrementalAnalysisService
from src.application.services.task_guard import DuplicateGroupTaskError, TaskGuard
from src.infrastructure.persistence.incremental_store import IncrementalStore
from src.infrastructure.platform.bot_manager import BotManager
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
async def test_incremental_execution_normalizes_alias_before_lock_and_other_instance_can_run(monkeypatch):
    values = {}

    async def get(key, default=None):
        return values.get(key, default)

    async def put(key, value):
        values[key] = value

    root = IncrementalStore(Mock(get_kv_data=get, put_kv_data=put))
    manager = BotManager(Mock())
    arrived = {name: asyncio.Event() for name in ("first", "second")}
    release = asyncio.Event()

    def adapter_for(name):
        async def fetch(**kwargs):
            arrived[name].set()
            await release.wait()
            return []
        return Mock(platform_id=name, is_group_muted=AsyncMock(return_value=False), fetch_messages=AsyncMock(side_effect=fetch))

    manager._adapters = {name: adapter_for(name) for name in arrived}
    config = Mock()
    config.get_analysis_days.return_value = 1
    config.get_incremental_min_messages.return_value = 1
    config.get_max_messages.return_value = 100
    guard = TaskGuard()
    service = IncrementalAnalysisService(config, manager, Mock(), Mock(), Mock(), Mock(), guard, root)
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: TraceContext(group_id="123")))
    first = asyncio.create_task(service.execute_incremental_analysis("123", " FIRST "))
    await asyncio.wait_for(arrived["first"].wait(), 1)
    second = asyncio.create_task(service.execute_incremental_analysis("123", "second"))
    try:
        await asyncio.wait_for(arrived["second"].wait(), 1)
        with pytest.raises(DuplicateGroupTaskError):
            await service.execute_incremental_analysis("123", "first")
    finally:
        release.set()
        await asyncio.gather(first, second)
    assert not guard.active_tasks
    assert {session.platform_id for session in await root.get_tracked_sessions()} == {"first", "second"}
