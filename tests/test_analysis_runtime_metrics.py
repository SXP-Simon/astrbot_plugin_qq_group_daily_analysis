"""实际耗时与只读熔断运行快照回归。"""

from unittest.mock import Mock

import pytest

from src.infrastructure.analysis.utils import llm_utils
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.routes.trace_routes import TraceRoutes
from src.utils import resilience


def test_performance_uses_actual_durations_without_time_window(tmp_path):
    store = TraceSQLiteStore(tmp_path / "runtime.db")
    assert store.get_metrics_summary()["analysis_performance"] == {
        "sample_count": 0, "avg_duration_ms": None, "latest_duration_ms": None,
    }
    rows = [
        ("old", "succeeded", 30000, 100),
        ("warning", "warning", 90000, 200),
        ("legacy", "completed", 60000, 150),
        ("failed", "failed", 999999, 300),
        ("aborted", "aborted", 999999, 400),
        ("running", "running", 999999, 500),
        ("missing", "succeeded", None, 600),
        ("zero", "succeeded", 0, 700),
    ]
    for trace_id, status, duration, completed in rows:
        store.save_trace({"trace_id": trace_id, "group_id": "123", "status": "running", "started_at": 1})
        with store._get_connection() as connection:
            connection.execute("UPDATE analysis_traces SET status=?, duration_ms=?, completed_at=? WHERE trace_id=?", (status, duration, completed, trace_id))
    assert store.get_metrics_summary()["analysis_performance"] == {
        "sample_count": 3, "avg_duration_ms": 60000, "latest_duration_ms": 90000,
    }
    # 重新打开存储仍读取历史实测值，不依赖本次进程的运行时长。
    assert TraceSQLiteStore(store.db_path).get_metrics_summary()["analysis_performance"]["sample_count"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("elapsed", [22, 61])
async def test_metrics_refresh_is_readonly_and_expired_circuit_stays_open(tmp_path, monkeypatch, elapsed):
    monkeypatch.setattr(llm_utils, "_circuit_breakers", {})
    monkeypatch.setattr(resilience.time, "monotonic", lambda: 100)
    breaker = llm_utils.get_provider_circuit_breaker("primary")
    for _ in range(5):
        breaker.record_failure()
    breaker.last_failure_time = 100 - elapsed
    breaker.acquire_request = Mock(side_effect=AssertionError("读取不能触发恢复"))
    before = dict(vars(breaker))
    context = Mock()
    route = TraceRoutes(context, TraceSQLiteStore(tmp_path / "route.db"), Mock())
    for _ in range(2):
        response = await route.api_get_metrics_summary()
        runtime = response["data"]["data"]["llm_runtime"]
        assert runtime["circuits"]["primary"]["state"] == "OPEN"
        assert runtime["circuits"]["primary"]["retry_after_seconds"] == max(0, 60 - elapsed)
    assert vars(breaker) == before
    assert set(llm_utils._circuit_breakers) == {"primary"}
    assert context.mock_calls == []


def test_snapshot_follows_recovery_and_is_detached(monkeypatch):
    monkeypatch.setattr(llm_utils, "_circuit_breakers", {})
    monkeypatch.setattr(resilience.time, "monotonic", lambda: 100)
    assert llm_utils.get_llm_runtime_snapshot()["circuits"] == {}
    breaker = llm_utils.get_provider_circuit_breaker("primary")
    for _ in range(5):
        breaker.record_failure()
    breaker.last_failure_time = 0
    before = llm_utils.get_llm_runtime_snapshot()
    permit = breaker.acquire_request()
    assert llm_utils.get_llm_runtime_snapshot()["circuits"]["primary"]["state"] == "HALF_OPEN"
    breaker.record_success(permit)
    assert llm_utils.get_llm_runtime_snapshot()["circuits"]["primary"]["failure_count"] == 0
    assert before["circuits"]["primary"]["state"] == "OPEN"
