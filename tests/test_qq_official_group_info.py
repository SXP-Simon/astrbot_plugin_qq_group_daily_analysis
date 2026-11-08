"""QQ 官方群资料查询、缓存隔离与任务展示回归。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.services.analysis_application_service import (
    AnalysisApplicationService,
)
from src.application.services.task_guard import TaskGuard
from src.application.services.incremental_analysis_service import (
    IncrementalAnalysisService,
)
from src.infrastructure.platform.adapters import qq_official_adapter as module
from src.infrastructure.platform.adapters.qq_official_adapter import QQOfficialAdapter
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.scheduler.target_resolver import ScheduledTargetResolver
from src.infrastructure.webui.active_task_manager import ActiveTaskManager
from src.shared import trace_context as trace_module
from src.shared.trace_context import TraceContext


def adapter_for(api, platform="official-a"):
    return QQOfficialAdapter(
        SimpleNamespace(api=api, platform=None), {"platform_id": platform}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped", [False, True])
async def test_group_info_uses_sdk_method_and_reuses_validated_metadata(wrapped):
    payload = {
        "group_openid": "GROUP",
        "group_name": "  读书\n分享会  ",
        "group_member_num": 256,
        "group_finger_memo": "每周共读",
    }
    method = AsyncMock(return_value={"data": payload} if wrapped else payload)
    adapter = adapter_for(SimpleNamespace(get_group_info=method))
    first = await adapter.get_group_info("GROUP")
    assert first.group_name == "读书 分享会"
    assert first.member_count == 256 and first.description == "每周共读"
    assert first.platform == "qq_official"
    assert await adapter.get_group_info("GROUP") == first
    method.assert_awaited_once_with(group_openid="GROUP")


@pytest.mark.asyncio
async def test_legacy_sdk_reuses_authenticated_http_and_encodes_route():
    http = SimpleNamespace(request=AsyncMock(return_value={"group_name": "旧 SDK 群"}))
    adapter = adapter_for(SimpleNamespace(_http=http))
    assert (await adapter.get_group_info("GROUP/space ?")).group_name == "旧 SDK 群"
    route = http.request.await_args.args[0]
    assert route.method == "GET"
    assert route.url == "https://api.bot.qq.com/v2/groups/GROUP%2Fspace%20%3F/info"
    route.is_sandbox = True
    assert route.url.startswith("https://sandbox.api.sgroup.qq.com/")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"group_name": 123},
        {"group_name": " "},
        {"group_name": "GROUP"},
        {"group_name": "其他群", "group_openid": "OTHER"},
        {"data": {"group_name": []}},
    ],
)
async def test_invalid_response_falls_back_and_is_negatively_cached(payload):
    method = AsyncMock(return_value=payload)
    adapter = adapter_for(SimpleNamespace(get_group_info=method))
    assert (await adapter.get_group_info("GROUP")).group_name == "GROUP"
    assert (await adapter.get_group_info("GROUP")).group_name == "GROUP"
    assert method.await_count == 1


@pytest.mark.asyncio
async def test_permission_failure_retains_stale_name_then_recovers(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    debug = Mock()
    monkeypatch.setattr(module.logger, "debug", debug)
    method = AsyncMock(
        side_effect=[
            {"group_name": "旧群名"},
            RuntimeError("403 token=secret"),
            {"group_name": "新群名"},
        ]
    )
    adapter = adapter_for(SimpleNamespace(get_group_info=method))
    assert (await adapter.get_group_info("GROUP")).group_name == "旧群名"
    clock[0] = 3601
    assert (await adapter.get_group_info("GROUP")).group_name == "旧群名"
    clock[0] = 3900
    assert (await adapter.get_group_info("GROUP")).group_name == "旧群名"
    assert method.await_count == 2
    assert "secret" not in repr(debug.call_args_list)
    clock[0] = 3902
    assert (await adapter.get_group_info("GROUP")).group_name == "新群名"


@pytest.mark.asyncio
async def test_first_permission_failure_can_retry_after_negative_ttl(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    method = AsyncMock(side_effect=[PermissionError("403"), {"group_name": "已授权群"}])
    adapter = adapter_for(SimpleNamespace(get_group_info=method))
    assert (await adapter.get_group_info("GROUP")).group_name == "GROUP"
    clock[0] = 301
    assert (await adapter.get_group_info("GROUP")).group_name == "已授权群"


@pytest.mark.asyncio
async def test_concurrent_queries_are_coalesced_and_cache_is_bot_scoped():
    entered, release = asyncio.Event(), asyncio.Event()

    async def query(**kwargs):
        entered.set()
        await release.wait()
        return {"group_name": "机器人 A"}

    method = AsyncMock(side_effect=query)
    a = adapter_for(SimpleNamespace(get_group_info=method))
    b = adapter_for(
        SimpleNamespace(
            get_group_info=AsyncMock(return_value={"group_name": "机器人 B"})
        )
    )
    tasks = [asyncio.create_task(a.get_group_info("GROUP")) for _ in range(5)]
    await entered.wait()
    release.set()
    assert all(item.group_name == "机器人 A" for item in await asyncio.gather(*tasks))
    assert method.await_count == 1
    assert (await b.get_group_info("GROUP")).group_name == "机器人 B"
    assert not a._group_info_locks


@pytest.mark.asyncio
async def test_slow_group_does_not_block_other_groups_or_cached_names():
    entered, release = asyncio.Event(), asyncio.Event()

    async def query(*, group_openid):
        if group_openid == "SLOW":
            entered.set()
            await release.wait()
        return {"group_name": f"名称 {group_openid}"}

    method = AsyncMock(side_effect=query)
    adapter = adapter_for(SimpleNamespace(get_group_info=method))
    await adapter.get_group_info("CACHED")
    slow = asyncio.create_task(adapter.get_group_info("SLOW"))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        for group in ("FAST", "CACHED"):
            result = await asyncio.wait_for(adapter.get_group_info(group), timeout=1)
            assert result.group_name == f"名称 {group}"
        assert not slow.done()
    finally:
        release.set()
        await slow
    assert method.await_count == 3
    assert not adapter._group_info_locks


@pytest.mark.asyncio
async def test_timeout_and_cancellation_do_not_block_future_queries():
    entered = asyncio.Event()

    async def blocked(**kwargs):
        entered.set()
        await asyncio.Event().wait()

    method = AsyncMock(side_effect=blocked)
    adapter = adapter_for(SimpleNamespace(get_group_info=method))
    adapter.GROUP_INFO_TIMEOUT = 0.01
    assert (await adapter.get_group_info("TIMEOUT")).group_name == "TIMEOUT"
    entered.clear()
    adapter.GROUP_INFO_TIMEOUT = 3
    task = asyncio.create_task(adapter.get_group_info("CANCELLED"))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(not lock.locked() for lock in adapter._group_info_locks.values())
    method.side_effect = None
    method.return_value = {"group_name": "正常群"}
    assert (await adapter.get_group_info("CANCELLED")).group_name == "正常群"


@pytest.mark.asyncio
async def test_missing_client_empty_group_and_bounded_cache():
    adapter = adapter_for(None)
    assert await adapter.get_group_info(" ") is None
    assert (await adapter.get_group_info("GROUP")).group_name == "GROUP"
    for number in range(260):
        await adapter.get_group_info(str(number))
    assert len(adapter._group_info_cache) == 256


@pytest.mark.asyncio
async def test_scheduler_does_not_freeze_qq_fallback_or_mix_platform_names():
    first = adapter_for(
        SimpleNamespace(get_group_info=AsyncMock(return_value={"group_name": "QQ 群"}))
    )
    second = SimpleNamespace(
        get_platform_name=lambda: "telegram",
        get_group_info=AsyncMock(return_value=SimpleNamespace(group_name="其他平台群")),
    )
    adapters = {"official-a": first, "other": second}
    resolver = ScheduledTargetResolver(None, SimpleNamespace(
        get_adapter=adapters.get,
        get_adapter_platform_id=lambda adapter: next(
            key for key, value in adapters.items() if value is adapter
        ),
    ))
    assert await resolver.get_group_name_safe("GROUP", "official-a") == "QQ 群"
    first._group_info_cache.clear()
    first.bot.api.get_group_info.return_value = {"group_name": "QQ 改名"}
    assert await resolver.get_group_name_safe("GROUP", "official-a") == "QQ 改名"
    assert await resolver.get_group_name_safe("GROUP", "other") == "其他平台群"
    assert await resolver.get_group_name_safe("GROUP", "other") == "其他平台群"
    second.get_group_info.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "original,fail,expected",
    [
        ("GROUP", False, "读书分享会"),
        ("", False, "读书分享会"),
        ("群 GROUP", False, "读书分享会"),
        ("未知群", False, "读书分享会"),
        ("自定义名称", False, "自定义名称"),
        ("GROUP", True, "GROUP"),
        ("群 GROUP", True, "GROUP"),
    ],
)
@pytest.mark.parametrize("incremental", [False, True])
async def test_web_trigger_enriches_trace_and_persists_name(
    tmp_path, monkeypatch, original, fail, expected, incremental
):
    adapter = adapter_for(
        SimpleNamespace(
            get_group_info=AsyncMock(
                side_effect=PermissionError() if fail else None,
                return_value={"group_name": "读书分享会"},
            )
        )
    )
    adapter.is_group_muted = AsyncMock(return_value=False)
    service = object.__new__(
        IncrementalAnalysisService if incremental else AnalysisApplicationService
    )
    service._task_guard = TaskGuard()
    service.task_guard = service._task_guard
    service.bot_manager = SimpleNamespace(
        get_adapter=lambda _: adapter, get_adapter_platform_id=lambda _: "official-a",
        resolve_platform_id=lambda platform: platform,
    )
    service.config_manager = SimpleNamespace(
        get_analysis_days=lambda: 1,
        get_max_messages=lambda: 10,
        get_incremental_min_messages=lambda: 5,
    )
    service.checkpoint_store = None
    service.incremental_store = SimpleNamespace(
        for_session=AsyncMock(return_value=SimpleNamespace(
            get_last_analyzed_cursor=AsyncMock(return_value=(0, []))
        ))
    )
    trace = TraceContext(
        trace_id="web-test",
        group_id="GROUP",
        group_name=original,
        platform="",
    )
    store = TraceSQLiteStore(tmp_path / "trace.db")
    manager = ActiveTaskManager()
    monkeypatch.setattr(trace_module, "_global_trace_store", store)
    monkeypatch.setattr(trace_module, "_global_task_lifecycle_service", None)
    monkeypatch.setattr(trace_module, "_global_active_task_manager", manager)
    await manager.register_task("web-test", "GROUP", original, "official-a")
    events = manager.subscribe()

    async def fetch(**kwargs):
        assert manager.get_active_tasks()[0]["group_name"] == expected
        return []

    adapter.fetch_messages = AsyncMock(side_effect=fetch)
    async with trace:
        if incremental:
            result = await service.execute_incremental_analysis("GROUP", "official-a")
        else:
            result = await service.execute_daily_analysis(
                "GROUP", "official-a", manual=True
            )
        assert result["reason"] == "no_messages"
    await asyncio.gather(*manager._bg_tasks)
    progress = json.loads(events.get_nowait())
    assert progress["event"] == "task_progress"
    assert progress["data"]["group_name"] == expected
    assert store.get_trace("web-test")["group_name"] == expected
    assert store.get_trace("web-test")["status"] != "running"
    assert store.get_trace("web-test")["platform"] == "official-a"
    assert store.get_distinct_groups(by_session=True)[0]["group_name"] == expected
    if original == "自定义名称":
        adapter.bot.api.get_group_info.assert_not_awaited()
