"""任务提醒知晓接口的输入、持久化回执和失败反馈测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot_plugin_qq_group_daily_analysis.src.domain.value_objects.task_event import TaskEvent
from astrbot_plugin_qq_group_daily_analysis.src.domain.value_objects.task_status import TaskStatus
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.routes import trace_routes


@pytest.fixture
def routes(tmp_path, monkeypatch):
    store = TraceSQLiteStore(tmp_path / "traces.db")
    for trace_id in ["finished", "active"]:
        store.save_trace({"trace_id": trace_id, "group_id": "g", "started_at": 1, "status": "running"})
    store.transition_trace_status(
        "finished", TaskStatus.RUNNING, TaskEvent.FAIL,
        completed_at=2, duration_ms=1000, error_stage="LLM_ANALYSIS",
        error_message="连接失败", stack_trace=None,
    )
    monkeypatch.setattr(trace_routes, "request", SimpleNamespace(json=AsyncMock(return_value={"acknowledged": True})))
    monkeypatch.setattr(trace_routes, "json_response", lambda payload: payload)
    monkeypatch.setattr(trace_routes, "error_response", lambda message, status_code: {"message": message, "status_code": status_code})
    return trace_routes.TraceRoutes(MagicMock(), store, MagicMock())


@pytest.mark.asyncio
async def test_acknowledgement_returns_persisted_time_and_supports_restore(routes):
    response = await routes.api_acknowledge_trace("finished")
    stamp = response["data"]["acknowledged_at"]
    assert stamp > 0
    assert response["data"]["trace_id"] == "finished"
    assert routes.trace_store.get_trace("finished")["acknowledged_at"] == stamp
    trace_routes.request.json.return_value = {"acknowledged": False}
    assert (await routes.api_acknowledge_trace("finished"))["data"]["acknowledged_at"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [None, [], {}, {"acknowledged": 1}, {"acknowledged": "true"}])
async def test_acknowledgement_rejects_ambiguous_input(routes, body):
    trace_routes.request.json.return_value = body
    assert (await routes.api_acknowledge_trace("finished"))["status_code"] == 400
    assert routes.trace_store.get_trace("finished")["acknowledged_at"] is None


@pytest.mark.asyncio
async def test_acknowledgement_reports_missing_running_and_storage_failure(routes, monkeypatch):
    assert (await routes.api_acknowledge_trace("missing"))["status_code"] == 404
    assert (await routes.api_acknowledge_trace("active"))["status_code"] == 409
    monkeypatch.setattr(routes.trace_store, "set_trace_acknowledgement", MagicMock(side_effect=OSError("disk full")))
    response = await routes.api_acknowledge_trace("finished")
    assert response["status_code"] == 500
    assert "未能保存" in response["message"]
    trace_routes.request.json.side_effect = ValueError("invalid JSON")
    assert (await routes.api_acknowledge_trace("finished"))["status_code"] == 400
