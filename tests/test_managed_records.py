"""业务记录管理使用真实仓储，并校验任务互斥、修订冲突与游标保护。"""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from diskcache import Cache

from src.application.services.task_guard import TaskGuard
from src.domain.entities.incremental_state import IncrementalBatch
from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.infrastructure.persistence.incremental_store import IncrementalStore
from src.infrastructure.persistence.history_manager import HistoryManager
from src.shared.trace_context import TraceContext
from src.infrastructure.webui.routes import managed_record_routes as routes


@pytest.mark.asyncio
async def test_record_read_normalizes_alias_before_binding_storage(record_endpoint):
    endpoint, request, _, _ = record_endpoint
    endpoint.service.bot_manager.resolve_platform_id = lambda value: "first" if value == "alias" else value
    root = endpoint.service.incremental_store
    scoped = await root.for_session("123", "first")
    await scoped.save_batch(IncrementalBatch(group_id="123", batch_id="one"))
    request.query = {"kind": "batch", "group_id": "123", "platform_id": "alias", "batch_id": "one"}
    result = (await endpoint.api_detail())["data"]
    assert result["locator"]["platform_id"] == "first"
    assert {session.platform_id for session in await root.get_tracked_sessions()} == {"first"}


@pytest.mark.asyncio
async def test_session_history_versions_remain_manageable_and_delete_repairs_only_own_pointer(record_endpoint, monkeypatch):
    endpoint, request, plugin, _ = record_endpoint
    manager = HistoryManager(plugin)
    monkeypatch.setattr("src.shared.trace_context._global_trace_store", None)
    for platform, task_id in [("first", "a1"), ("second", "b1"), ("first", "a2")]:
        with TraceContext(trace_id=task_id, platform=platform, group_id="123"):
            assert await manager.save_analysis("123", {"topics": []}, "2026-11-07", "12:00", platform_id=platform)
    request.query = {"kind": "history"}
    result = await endpoint.api_list()
    assert result["data"]["total"] == 3
    items = result["data"]["items"]
    assert {item["locator"]["platform_id"] for item in items} == {"first", "second"}
    latest_key = plugin.values[manager.latest_key("123", "2026-11-07", "first")]
    locator = next(item["locator"] for item in items if item["locator"]["key"] == latest_key)
    request.query = locator
    detail = (await endpoint.api_detail())["data"]
    request.json.return_value = {"locator": locator, "operation": "delete", "revision": detail["revision"]}
    assert (await endpoint.api_mutate())["status"] == "ok"
    assert (await manager.get_analysis("123", "2026-11-07", platform_id="first"))["trace_id"] == "a1"
    assert (await manager.get_analysis("123", "2026-11-07", platform_id="second"))["trace_id"] == "b1"
    assert await manager.get_analysis("123", "2026-11-07", platform_id="first", trace_id="a2") is None


class FakePlugin:
    plugin_id = "test-plugin"

    def __init__(self):
        self.values = {}

    async def get_kv_data(self, key, default=None):
        return copy.deepcopy(self.values.get(key, default))

    async def put_kv_data(self, key, value):
        self.values[key] = copy.deepcopy(value)

    async def delete_kv_data(self, key):
        self.values.pop(key, None)


@pytest.fixture
def record_endpoint(tmp_path, monkeypatch):
    plugin = FakePlugin()
    guard = TaskGuard()
    service = SimpleNamespace(
        history_manager=SimpleNamespace(plugin=plugin),
        bot_manager=SimpleNamespace(resolve_platform_id=lambda value: value),
        incremental_store=IncrementalStore(plugin),
        checkpoint_store=CheckpointStore(tmp_path / "traces.db"),
        group_lock=guard.group_lock,
    )
    active = SimpleNamespace(get_active_tasks=lambda: [])
    endpoint = routes.ManagedRecordRoutes(service, active)
    request = MagicMock(query={})
    request.json = AsyncMock()
    monkeypatch.setattr(routes, "request", request)
    monkeypatch.setattr(routes.StarTools, "get_data_dir", lambda _: tmp_path)
    monkeypatch.setattr(routes, "json_response", lambda value: value)
    monkeypatch.setattr(
        routes,
        "error_response",
        lambda message, status_code: {"message": message, "status_code": status_code},
    )

    async def history():
        return {
            key: value
            for key, value in plugin.values.items()
            if routes.HISTORY_KEY.fullmatch(key) and isinstance(value, dict)
        }

    monkeypatch.setattr(endpoint, "_history", history)
    return endpoint, request, plugin, guard


@pytest.mark.asyncio
async def test_batch_import_edit_conflict_and_cursor_is_untouched(record_endpoint):
    endpoint, request, _, guard = record_endpoint
    store = endpoint.service.incremental_store
    await store.update_last_analyzed_cursor("123", 42, {"m1"})
    locator = {"kind": "batch", "group_id": "123", "batch_id": "batch-one"}
    batch = IncrementalBatch(
        group_id="123", batch_id="batch-one", messages_count=3
    ).to_dict()
    request.json.return_value = {
        "locator": locator,
        "operation": "create",
        "data": batch,
    }
    assert (await endpoint.api_mutate())["status"] == "ok"
    assert (await endpoint.api_mutate())["status_code"] == 409
    request.query = locator
    record = (await endpoint.api_detail())["data"]
    request.json.return_value = {
        **record,
        "operation": "replace",
        "data": {**record["data"], "messages_count": 4},
    }
    async with guard.group_lock("123", "incremental"):
        assert (await endpoint.api_mutate())["status_code"] == 409
    assert (await endpoint.api_mutate())["status"] == "ok"
    assert (await endpoint.api_mutate())["status_code"] == 409
    assert await store.get_last_analyzed_cursor("123") == (42, {"m1"})
    record = (await endpoint.api_detail())["data"]
    request.json.return_value = {
        **record,
        "operation": "replace",
        "data": {**record["data"], "messages_count": -1},
    }
    assert (await endpoint.api_mutate())["status_code"] == 400


@pytest.mark.asyncio
async def test_checkpoint_revision_preserves_identity_and_ttl(record_endpoint):
    endpoint, request, _, _ = record_endpoint
    store = endpoint.service.checkpoint_store
    store.save_checkpoint(
        "123", "2026-11-03", "LLM_ANALYSIS", {"topics": []}, "trace-a"
    )
    request.query = {
        "kind": "checkpoint",
        "group_id": "123",
        "date_str": "2026-11-03",
        "stage_name": "LLM_ANALYSIS",
        "trace_id": "trace-a",
    }
    original = (await endpoint.api_detail())["data"]
    request.json.return_value = {
        **original,
        "operation": "replace",
        "data": {**original["data"], "data": {"topics": [{"topic": "修订"}]}},
    }
    assert (await endpoint.api_mutate())["status"] == "ok"
    updated = (await endpoint.api_detail())["data"]
    assert updated["data"]["created_at"] == original["data"]["created_at"]
    assert updated["data"]["expire_at"] == original["data"]["expire_at"]
    request.json.return_value = {
        **updated,
        "operation": "replace",
        "data": {**updated["data"], "expire_at": 9999999999},
    }
    assert (await endpoint.api_mutate())["status_code"] == 400
    request.query["trace_id"] = "wrong-trace"
    assert (await endpoint.api_detail())["status_code"] == 404


@pytest.mark.asyncio
async def test_history_delete_repairs_daily_pointer_and_import_cannot_overwrite_alias(
    record_endpoint,
):
    endpoint, request, plugin, _ = record_endpoint
    daily = "analysis_123_2026-11-03"
    first, second = daily + "_10-00", daily + "_11-00"
    plugin.values.update(
        {
            first: {"summary": {}, "analysis": {}},
            second: {"summary": {}, "analysis": {}},
            daily: second,
        }
    )
    request.json.return_value = {
        "locator": {"kind": "history", "key": daily},
        "operation": "create",
        "data": {},
    }
    assert (await endpoint.api_mutate())["status_code"] == 409
    request.query = {"kind": "history", "key": second}
    record = (await endpoint.api_detail())["data"]
    request.json.return_value = {**record, "operation": "delete"}
    assert (await endpoint.api_mutate())["status"] == "ok"
    assert plugin.values[daily] == first
    request.query = {"kind": "history", "search": "10-00"}
    assert (await endpoint.api_list())["data"]["total"] == 1


@pytest.mark.asyncio
async def test_avatar_management_uses_cache_api_and_rejects_edits(
    record_endpoint, tmp_path
):
    endpoint, request, _, _ = record_endpoint
    with Cache(str(tmp_path / "avatar")) as cache:
        cache.set("onebot:123", "data:image/png;base64,AA==")
    request.query = {"kind": "avatar", "key": "onebot:123"}
    record = (await endpoint.api_detail())["data"]
    request.json.return_value = {**record, "operation": "replace"}
    assert (await endpoint.api_mutate())["status_code"] == 400
    request.json.return_value["operation"] = "delete"
    assert (await endpoint.api_mutate())["status"] == "ok"
    with Cache(str(tmp_path / "avatar")) as cache:
        assert cache.get("onebot:123") is None
        assert (tmp_path / "avatar/cache.db").exists()


@pytest.mark.asyncio
async def test_import_history_repairs_missing_daily_index(record_endpoint):
    endpoint, request, plugin, _ = record_endpoint
    key = "analysis_123_2026-11-03_10-00"
    request.json.return_value = {"locator": {"kind": "history", "key": key}, "operation": "create", "data": {"summary": {}, "analysis": {}}}
    assert (await endpoint.api_mutate())["status"] == "ok"
    assert plugin.values["analysis_123_2026-11-03"] == key


@pytest.mark.asyncio
async def test_existing_delete_endpoint_obeys_group_mutation_lock(record_endpoint, monkeypatch):
    from src.infrastructure.webui.routes import data_management_routes

    endpoint, request, _, guard = record_endpoint
    legacy = data_management_routes.DataManagementRoutes(MagicMock(), endpoint.service)
    monkeypatch.setattr(data_management_routes, "request", request)
    monkeypatch.setattr(data_management_routes, "error_response", lambda message, status_code: {"message": message, "status_code": status_code})
    request.json.return_value = {"group_id": "123", "batch_id": "batch-one"}
    async with guard.group_lock("123", "daily"):
        assert (await legacy.api_delete_incremental_batch())["status_code"] == 409


@pytest.mark.asyncio
async def test_same_batch_identity_is_scoped_for_import_edit_and_delete(record_endpoint):
    endpoint, request, _, _ = record_endpoint
    root = endpoint.service.incremental_store
    for platform, count in [("onebot-main", 3), ("telegram-main", 8)]:
        locator = {"kind": "batch", "platform_id": platform, "group_id": "123", "batch_id": "same"}
        request.json.return_value = {"locator": locator, "operation": "create", "data": IncrementalBatch(group_id="123", batch_id="same", messages_count=count).to_dict()}
        assert (await endpoint.api_mutate())["status"] == "ok"
    request.query = locator
    record = (await endpoint.api_detail())["data"]
    assert record["locator"]["platform_id"] == "telegram-main"
    assert record["data"]["messages_count"] == 8
    request.json.return_value = {**record, "operation": "replace", "data": {**record["data"], "messages_count": 9}}
    assert (await endpoint.api_mutate())["status"] == "ok"
    record = (await endpoint.api_detail())["data"]
    assert record["data"]["messages_count"] == 9
    request.json.return_value = {**record, "operation": "delete"}
    assert (await endpoint.api_mutate())["status"] == "ok"
    assert (await endpoint.api_detail())["status_code"] == 404
    first = await root.for_session("123", "onebot-main")
    assert (await first.get_batch_detail("123", "same")).messages_count == 3
