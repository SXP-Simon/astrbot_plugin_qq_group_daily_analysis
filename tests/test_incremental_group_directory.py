"""目录按平台分开，旧增量数据仅迁移到最近记录的平台。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.incremental_state import IncrementalBatch
from src.infrastructure.persistence.incremental_store import IncrementalStore
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.routes import data_management_routes


class MemoryStar:
    def __init__(self):
        self.data = {}

    async def get_kv_data(self, key, default=None):
        return deepcopy(self.data.get(key, default))

    async def put_kv_data(self, key, value):
        self.data[key] = deepcopy(value)


@pytest.mark.asyncio
async def test_directory_separates_platforms_and_claims_legacy_once(tmp_path, monkeypatch):
    traces = TraceSQLiteStore(tmp_path / "state.db")
    for index, platform, name in [(1, "telegram", "摄影群"), (2, "aiocqhttp", "技术群"), (3, "telegram", "摄影群新名称")]:
        traces.save_trace({"trace_id": str(index), "group_id": "123", "platform": platform, "group_name": name, "started_at": index, "status": "running"})
    store = IncrementalStore(MemoryStar())
    await store.save_batch(IncrementalBatch(group_id="123", batch_id="old", messages_count=7))
    await store.update_last_analyzed_cursor("legacy-only", 100, set())
    monkeypatch.setattr(data_management_routes, "json_response", lambda data: data)
    routes = data_management_routes.DataManagementRoutes(traces, SimpleNamespace(incremental_store=store))
    data = (await routes.api_get_incremental_groups())["data"]
    assert data["groups"] == ["123", "legacy-only"]
    assert data["group_details"] == [
        {"group_id": "legacy-only", "group_name": "", "platform_id": ""},
        {"group_id": "123", "group_name": "技术群", "platform_id": "aiocqhttp"},
        {"group_id": "123", "group_name": "摄影群新名称", "platform_id": "telegram"},
    ]
    assert await (await store.for_session("123", "telegram")).get_batch_count("123") == 1
    assert await (await store.for_session("123", "aiocqhttp")).get_batch_count("123") == 0
    assert (await routes.api_get_incremental_groups())["data"] == data


@pytest.mark.asyncio
async def test_routes_read_delete_and_reset_only_selected_platform(tmp_path, monkeypatch):
    root = IncrementalStore(MemoryStar())
    for platform, count in [("onebot-main", 7), ("telegram-main", 11)]:
        store = await root.for_session("123", platform)
        await store.save_batch(IncrementalBatch(group_id="123", batch_id="same", messages_count=count))
        await store.update_last_analyzed_cursor("123", count, {platform})
    monkeypatch.setattr(data_management_routes, "json_response", lambda data: data)
    monkeypatch.setattr(data_management_routes, "error_response", lambda message, status_code: {"status_code": status_code, "message": message})
    request = MagicMock(query={"group_id": "123", "platform_id": "telegram-main", "batch_id": "same"})
    request.json = AsyncMock(return_value={})
    monkeypatch.setattr(data_management_routes, "request", request)
    routes = data_management_routes.DataManagementRoutes(TraceSQLiteStore(tmp_path / "state.db"), SimpleNamespace(incremental_store=root))
    # 路由锁仅负责任务互斥，仓储会话决定实际读写范围。
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def unlocked(_group):
        yield
    monkeypatch.setattr(routes, "_mutation_guard", unlocked)
    listed = (await routes.api_get_incremental_batches())["data"]
    assert listed["platform_id"] == "telegram-main"
    assert listed["batches"][0]["messages_count"] == 11
    assert listed["cursor"]["last_analyzed_timestamp"] == 11
    assert (await routes.api_get_incremental_batch_detail())["data"]["messages_count"] == 11
    assert (await routes.api_delete_incremental_batch())["data"]["deleted"] is True
    assert (await routes.api_reset_incremental_group())["data"]["deleted_batches"] == 0
    first = await root.for_session("123", "onebot-main")
    assert await first.get_batch_count("123") == 1
    assert await first.get_last_analyzed_cursor("123") == (7, {"onebot-main"})
    request.query.pop("platform_id")
    assert (await routes.api_get_incremental_batches())["status_code"] == 400
