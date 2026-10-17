"""增量合并投递后的失败、回执不明与取消均不得自动重发。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.infrastructure.scheduler import auto_scheduler
from src.infrastructure.scheduler.auto_scheduler import AutoScheduler
from src.shared.trace_context import TraceContext


@pytest.fixture
def scheduler(monkeypatch):
    """保留真实最终报告和超时包装器，仅替换分析及投递边界。"""
    trace = SimpleNamespace(status="running", finish=Mock())
    monkeypatch.setattr(TraceContext, "set", Mock(return_value=trace))
    instance = object.__new__(AutoScheduler)
    instance._terminating = False
    instance._get_group_name_safe = AsyncMock(return_value="测试群")
    instance.bot_manager = SimpleNamespace(
        is_ready_for_auto_analysis=Mock(return_value=True)
    )
    instance.analysis_service = SimpleNamespace(
        execute_incremental_final_report=AsyncMock(
            return_value={"success": True, "analysis_result": {"topics": []}}
        ),
        incremental_store=None,
    )
    instance.config_manager = SimpleNamespace(
        get_incremental_fallback_enabled=Mock(return_value=True),
        get_analysis_days=Mock(return_value=1),
    )
    instance.report_dispatcher = SimpleNamespace(
        merged_delivery=SimpleNamespace(enabled_for=Mock(return_value=True)),
        dispatch=AsyncMock(return_value=False),
    )
    instance.plugin_instance = None
    instance.incremental_trigger = None
    instance._fallback_to_traditional = AsyncMock(
        return_value={"success": True, "fallback": True}
    )
    return instance


@pytest.mark.asyncio
async def test_partial_merge_success_does_not_retry_whole_report(scheduler):
    """词云或漫画成功、报告失败时，也不能再次生成整份内容。"""
    result = await scheduler._perform_incremental_final_report_for_group_with_timeout(
        "123", "onebot"
    )
    assert result["success"] is False
    assert result["analysis_success"] is True
    assert result["reason"] == "report_delivery_failed"
    scheduler.report_dispatcher.dispatch.assert_awaited_once_with(
        "123", {"topics": []}, "onebot"
    )
    scheduler._fallback_to_traditional.assert_not_awaited()


@pytest.mark.asyncio
async def test_ambiguous_send_timeout_does_not_trigger_full_analysis(scheduler):
    """平台发送可能已接收，未收到有效回执时不能自动再发。"""
    scheduler.report_dispatcher.dispatch.side_effect = TimeoutError("平台回执超时")
    result = await scheduler._perform_incremental_final_report_for_group_with_timeout(
        "123", "onebot"
    )
    assert result["success"] is False
    assert result["reason"] == "平台回执超时"
    scheduler.report_dispatcher.dispatch.assert_awaited_once()
    scheduler._fallback_to_traditional.assert_not_awaited()


@pytest.mark.asyncio
async def test_analysis_deadline_does_not_cancel_merged_dispatch(
    scheduler, monkeypatch
):
    """进入合并投递后使用独立时限，失败时也不重复分析。"""

    async def slow_dispatch(*_args):
        await asyncio.sleep(0.03)
        return False

    scheduler.report_dispatcher.dispatch.side_effect = slow_dispatch
    monkeypatch.setattr(auto_scheduler, "_SCHEDULED_ANALYSIS_TIMEOUT_SECONDS", 0.01)
    result = await scheduler._perform_incremental_final_report_for_group_with_timeout(
        "123", "onebot"
    )
    assert result["reason"] == "report_delivery_failed"
    assert result["analysis_success"] is True
    scheduler.report_dispatcher.dispatch.assert_awaited_once()
    scheduler._fallback_to_traditional.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError("超时"), RuntimeError("异常")])
async def test_wrapper_exception_after_dispatch_mark_never_retries(scheduler, error):
    """已记录合并投递的调用即使直接抛出异常，也不能走原有回退分支。"""

    async def failing_report(*_args, on_merged_dispatch):
        on_merged_dispatch()
        raise error

    scheduler._perform_incremental_final_report_for_group = failing_report
    result = await scheduler._perform_incremental_final_report_for_group_with_timeout(
        "123", "onebot"
    )
    assert result["success"] is False
    assert result["analysis_success"] is True
    scheduler._fallback_to_traditional.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("raises", [False, True])
async def test_analysis_failure_keeps_existing_full_analysis_fallback(
    scheduler, raises
):
    """尚未进入投递时的无增量数据或分析异常继续允许传统回退。"""
    if raises:
        scheduler.analysis_service.execute_incremental_final_report.side_effect = (
            RuntimeError("分析失败")
        )
    else:
        scheduler.analysis_service.execute_incremental_final_report.return_value = {
            "success": False,
            "reason": "no_incremental_data",
        }
    result = await scheduler._perform_incremental_final_report_for_group_with_timeout(
        "123", "onebot"
    )
    assert result == {"success": True, "fallback": True}
    scheduler._fallback_to_traditional.assert_awaited_once_with("123", "onebot")
    scheduler.report_dispatcher.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_analysis_deadline_before_dispatch_still_allows_fallback(
    scheduler, monkeypatch
):
    """总时限发生在分析阶段时，保留原有自动回退行为。"""

    async def blocked_analysis(**_kwargs):
        await asyncio.Event().wait()

    scheduler.analysis_service.execute_incremental_final_report.side_effect = (
        blocked_analysis
    )
    monkeypatch.setattr(auto_scheduler, "_SCHEDULED_ANALYSIS_TIMEOUT_SECONDS", 0.01)
    result = await scheduler._perform_incremental_final_report_for_group_with_timeout(
        "123", "onebot"
    )
    assert result == {"success": True, "fallback": True}
    scheduler._fallback_to_traditional.assert_awaited_once_with("123", "onebot")
    scheduler.report_dispatcher.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_normal_delivery_failure_keeps_original_fallback(scheduler):
    """未使用合并投递时，原有报告失败回退语义保持不变。"""
    scheduler.report_dispatcher.merged_delivery = None
    result = await scheduler._perform_incremental_final_report_for_group_with_timeout(
        "123", "onebot"
    )
    assert result == {"success": True, "fallback": True}
    scheduler._fallback_to_traditional.assert_awaited_once_with("123", "onebot")


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_stage", ["analysis", "dispatch"])
async def test_parent_cancellation_never_starts_another_analysis(
    scheduler, cancel_stage
):
    """外部停止信号直接传播，无论是否已经进入合并投递都不回退。"""
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked(*_args, **_kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    if cancel_stage == "analysis":
        scheduler.analysis_service.execute_incremental_final_report.side_effect = (
            blocked
        )
    else:
        scheduler.report_dispatcher.dispatch.side_effect = blocked
    task = asyncio.create_task(
        scheduler._perform_incremental_final_report_for_group_with_timeout(
            "123", "onebot"
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
    scheduler._fallback_to_traditional.assert_not_awaited()
