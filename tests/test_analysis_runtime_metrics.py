"""实际耗时与只读熔断运行快照回归。"""

from unittest.mock import Mock

import pytest

from src.infrastructure.analysis.utils import llm_utils
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.routes.trace_routes import TraceRoutes
from src.utils import resilience


@pytest.mark.parametrize("valid_count", [0, 3, 7])
def test_performance_lists_recent_successes_by_completion_time(tmp_path, valid_count):
    db_path = tmp_path / "runtime.db"
    store = TraceSQLiteStore(db_path)
    rows = [
        (f"success-{i}", ("succeeded", "warning", "completed")[i % 3],
         1000 + i * 100, 200 - i, 300 + i)
        for i in range(valid_count)
    ]
    rows.extend([
        ("failed", "failed", 99000, 200, 400),
        ("aborted", "aborted", 99000, 200, 401),
        ("running", "running", 99000, 200, 402),
        ("missing-duration", "succeeded", None, 200, 403),
        ("zero-duration", "succeeded", 0, 200, 404),
        ("missing-completion", "succeeded", 99000, 200, None),
    ])
    for trace_id, status, duration, started, completed in reversed(rows):
        store.save_trace({"trace_id": trace_id, "group_id": "123", "status": "running", "started_at": started})
        with store._get_connection() as connection:
            connection.execute(
                "UPDATE analysis_traces SET status=?, duration_ms=?, completed_at=? WHERE trace_id=?",
                (status, duration, completed, trace_id),
            )
    expected = [row[2] for row in reversed(rows[:valid_count])][:5]
    assert TraceSQLiteStore(db_path).get_metrics_summary()["analysis_performance"] == {
        "recent_durations_ms": expected,
    }


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
