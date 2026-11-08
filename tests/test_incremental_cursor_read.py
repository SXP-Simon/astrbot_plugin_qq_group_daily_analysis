"""游标缺失可首次分析，读取故障和损坏数据必须阻止历史重算。"""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.services.incremental_analysis_service import IncrementalAnalysisService
from src.application.services.task_guard import TaskGuard
from src.infrastructure.persistence.incremental_store import IncrementalStore
from src.shared.trace_context import TraceContext


class CursorKV:
    def __init__(self):
        self.data = {}
        self.failed_key = None

    async def get_kv_data(self, key, default=None):
        if key == self.failed_key:
            raise OSError("模拟游标存储不可读")
        return deepcopy(self.data.get(key, default))

    async def put_kv_data(self, key, value):
        self.data[key] = deepcopy(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["", "onebot-main"])
async def test_missing_cursor_starts_normally_and_reset_remains_readable(platform):
    root = IncrementalStore(CursorKV())
    store = await root.for_session("123", platform)
    assert await store.get_last_analyzed_cursor("123") == (0, set())
    await store.update_last_analyzed_cursor("123", 100, {"one", "two"})
    assert await store.get_last_analyzed_cursor("123") == (100, {"one", "two"})
    await store.reset_group("123")
    assert await store.get_last_analyzed_cursor("123") == (0, set())


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, 100, "100", 100.0])
async def test_legacy_numeric_cursor_remains_supported(value):
    kv = CursorKV()
    store = IncrementalStore(kv)
    kv.data[store._last_ts_key("123")] = value
    assert await store.get_last_analyzed_cursor("123") == (int(value), set())


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["", "onebot-main"])
@pytest.mark.parametrize("value", [
    None, "", "broken", [], True, -1, 100.5, float("inf"), float("nan"),
    {}, {"message_ids": []}, {"timestamp": 100},
    {"timestamp": "broken", "message_ids": []},
    {"timestamp": True, "message_ids": []},
    {"timestamp": -1, "message_ids": []},
    {"timestamp": 100, "message_ids": "one"},
    {"timestamp": 100, "message_ids": [None]},
    {"timestamp": 100, "message_ids": [{}]},
    {"timestamp": 100, "message_ids": [""]},
])
async def test_corrupt_cursor_is_not_treated_as_missing(platform, value):
    kv = CursorKV()
    root = IncrementalStore(kv)
    store = await root.for_session("123", platform)
    key = store._last_ts_key("123")
    kv.data[key] = value
    with pytest.raises(RuntimeError, match="本次分析已停止"):
        await store.get_last_analyzed_cursor("123")
    assert kv.data[key] is value


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["storage", "corrupt"])
async def test_cursor_failure_stops_analysis_before_fetch_or_llm(monkeypatch, failure):
    kv = CursorKV()
    root = IncrementalStore(kv)
    store = await root.for_session("123", "onebot-main")
    await store.update_last_analyzed_cursor("123", 100, {"already-analyzed"})
    key = store._last_ts_key("123")
    if failure == "storage":
        kv.failed_key = key
    else:
        kv.data[key] = {"timestamp": "broken", "message_ids": []}
    before = deepcopy(kv.data)
    adapter = Mock(is_group_muted=AsyncMock(return_value=False), fetch_messages=AsyncMock())
    llm = Mock(analyze_incremental_concurrent=AsyncMock())
    guard = TaskGuard()
    service = IncrementalAnalysisService(
        config_manager=Mock(),
        bot_manager=Mock(get_adapter=Mock(return_value=adapter), get_adapter_platform_id=Mock(return_value="onebot-main")),
        history_manager=Mock(), llm_analyzer=llm, statistics_service=Mock(),
        analysis_domain_service=Mock(), task_guard=guard, incremental_store=root,
    )
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: TraceContext(group_id="123")))
    with pytest.raises(RuntimeError, match="本次分析已停止"):
        await service.execute_incremental_analysis("123", "onebot-main")
    adapter.fetch_messages.assert_not_awaited()
    llm.analyze_incremental_concurrent.assert_not_awaited()
    assert kv.data == before
    assert not guard.is_group_running("123", "incremental")

    # 故障解除后仍读取原进度，不依赖重置或清空增量数据。
    kv.failed_key = None
    kv.data[key] = {"timestamp": 100, "message_ids": ["already-analyzed"]}
    assert await store.get_last_analyzed_cursor("123") == (100, {"already-analyzed"})
