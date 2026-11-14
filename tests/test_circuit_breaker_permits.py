"""单次恢复资格及并发请求迟到结果的状态机回归。"""

import pytest

from src.utils import resilience


def test_single_probe_and_stale_completions_cannot_change_recovery(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(resilience.time, "monotonic", lambda: now[0])
    breaker = resilience.CircuitBreaker(failure_threshold=1, recovery_timeout=60)
    failed = breaker.acquire_request()
    late = breaker.acquire_request()
    breaker.record_failure(failed)
    with pytest.raises(resilience.CircuitBreakerRejected, match="冷却中"):
        breaker.acquire_request()
    now[0] = 160
    for _ in range(6):
        breaker.check_request()
    assert breaker.state == "OPEN"
    probe = breaker.acquire_request()
    for _ in range(6):
        with pytest.raises(resilience.CircuitBreakerRejected, match="恢复探测"):
            breaker.acquire_request()
    breaker.record_success(late)
    breaker.record_failure(late)
    breaker.release_request(late)
    assert breaker.state == "HALF_OPEN"
    assert breaker.failure_count == 1
    breaker.record_failure(probe)
    breaker.release_request(probe)
    assert breaker.snapshot()["retry_after_seconds"] == 60
    now[0] += 60
    next_probe = breaker.acquire_request()
    breaker.record_success(probe)
    assert breaker.state == "HALF_OPEN"
    breaker.record_success(next_probe)
    breaker.release_request(next_probe)
    assert breaker.state == "CLOSED"
    assert breaker.failure_count == 0


def test_released_probe_can_be_replaced_without_old_release_stealing_new_slot(monkeypatch):
    monkeypatch.setattr(resilience.time, "monotonic", lambda: 100)
    breaker = resilience.CircuitBreaker(failure_threshold=1, recovery_timeout=0)
    breaker.record_failure()
    first = breaker.acquire_request()
    breaker.release_request(first)
    second = breaker.acquire_request()
    breaker.release_request(first)
    breaker.record_success(first)
    assert breaker.state == "HALF_OPEN"
    with pytest.raises(resilience.CircuitBreakerRejected):
        breaker.acquire_request()
    breaker.record_success(second)
    assert breaker.state == "CLOSED"
