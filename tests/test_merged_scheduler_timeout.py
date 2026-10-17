"""调度分析与合并投递的独立期限、取消传播及清理边界。"""

import asyncio
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.services.merged_forward_delivery import (
    MergedForwardDeliveryService,
    PreparedForwardMessage,
)
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.infrastructure.scheduler import auto_scheduler
from src.infrastructure.scheduler.auto_scheduler import AutoScheduler
from src.shared.trace_context import TraceContext


@pytest.fixture
def environment(monkeypatch):
    """保留真实调度器、分发器和合并服务，仅替换生成与网络边界。"""
    trace = SimpleNamespace(status="running", finish=Mock())
    monkeypatch.setattr(TraceContext, "set", Mock(return_value=trace))
    monkeypatch.setattr(TraceContext, "current", lambda: None)
    monkeypatch.setattr(auto_scheduler, "_SCHEDULED_ANALYSIS_TIMEOUT_SECONDS", 0.04)
    config = SimpleNamespace(
        get_enable_merged_forward=Mock(return_value=True),
        get_merged_forward_timeout=Mock(return_value=600),
        get_output_format=Mock(return_value=["text"]),
        get_incremental_fallback_enabled=Mock(return_value=False),
        get_analysis_days=Mock(return_value=1),
    )
    adapter = SimpleNamespace(
        platform_id="bot",
        get_platform_name=lambda: "aiocqhttp",
        bot_self_ids=["42"],
        capabilities=SimpleNamespace(supports_forward_message=True),
        send_forward_msg=AsyncMock(return_value=True),
    )
    bots = SimpleNamespace(
        get_adapter=Mock(return_value=adapter),
        is_ready_for_auto_analysis=Mock(return_value=True),
    )
    sender = SimpleNamespace(bot_manager=bots)
    generator = SimpleNamespace(generate_text_report=Mock(return_value="分析正文"))
    dispatcher = ReportDispatcher(config, generator, sender)
    dispatcher.merged_delivery = MergedForwardDeliveryService(config, bots)
    cloud_sent = AsyncMock()
    dispatcher.wordcloud_delivery = SimpleNamespace(
        prepare_for_report=AsyncMock(
            return_value=[
                PreparedForwardMessage("wordcloud", "词云", after_send=cloud_sent)
            ]
        )
    )
    scheduler = object.__new__(AutoScheduler)
    scheduler._terminating = False
    scheduler._get_group_name_safe = AsyncMock(return_value="测试群")
    scheduler.bot_manager = bots
    scheduler.config_manager = config
    scheduler.analysis_service = SimpleNamespace(
        execute_daily_analysis=AsyncMock(
            return_value={"success": True, "analysis_result": {}}
        ),
        execute_incremental_final_report=AsyncMock(
            return_value={"success": True, "analysis_result": {}}
        ),
        incremental_store=None,
    )
    scheduler.report_dispatcher = dispatcher
    scheduler.plugin_instance = None
    scheduler.incremental_trigger = None
    scheduler._fallback_to_traditional = AsyncMock()
    return SimpleNamespace(
        scheduler=scheduler,
        dispatcher=dispatcher,
        config=config,
        adapter=adapter,
        generator=generator,
        cloud_sent=cloud_sent,
        trace=trace,
    )


async def run_scheduled(environment, incremental):
    """选择真实的传统或增量调度包装器。"""
    scheduler = environment.scheduler
    if incremental:
        return await scheduler._perform_incremental_final_report_for_group_with_timeout(
            "123", "bot"
        )
    return await scheduler._perform_auto_analysis_for_group_with_timeout("123", "bot")


@pytest.mark.asyncio
@pytest.mark.parametrize("incremental", [False, True], ids=["daily", "incremental"])
@pytest.mark.parametrize("collection_timeout", [600, 3600])
async def test_completed_merge_outlives_analysis_deadline(
    environment, incremental, collection_timeout
):
    """默认和最大配置均有独立预算，慢漫画跨过分析期限仍一次投递三项。"""
    environment.config.get_merged_forward_timeout.return_value = collection_timeout

    async def slow_comic(*_args):
        await asyncio.sleep(0.08)
        return [PreparedForwardMessage("comic", "漫画")]

    environment.dispatcher.comic_handler = SimpleNamespace(
        prepare_for_report=slow_comic
    )
    result = await asyncio.wait_for(run_scheduled(environment, incremental), timeout=1)

    assert result["success"] is True
    assert result["analysis_success"] is True
    assert result["report_sent"] is True
    environment.adapter.send_forward_msg.assert_awaited_once()
    nodes = environment.adapter.send_forward_msg.call_args.args[1]
    assert len(nodes) == 3
    environment.cloud_sent.assert_awaited_once()
    environment.config.get_merged_forward_timeout.assert_called_once_with()
    environment.scheduler._fallback_to_traditional.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("incremental", [False, True], ids=["daily", "incremental"])
async def test_collection_timeout_sends_ready_report_and_cloud(
    environment, incremental
):
    """跨过旧分析期限后才到达收集期限，仍投递完成项并取消慢漫画。"""
    environment.config.get_merged_forward_timeout.return_value = 0.08
    cancelled = asyncio.Event()

    async def blocked_comic(*_args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    environment.dispatcher.comic_handler = SimpleNamespace(
        prepare_for_report=blocked_comic
    )
    result = await asyncio.wait_for(run_scheduled(environment, incremental), timeout=1)

    assert result["success"] is True
    assert cancelled.is_set()
    environment.adapter.send_forward_msg.assert_awaited_once()
    nodes = environment.adapter.send_forward_msg.call_args.args[1]
    assert len(nodes) == 2
    assert "分析正文" in nodes[0]["data"]["content"][0]["data"]["text"]
    environment.cloud_sent.assert_awaited_once()
    environment.scheduler._fallback_to_traditional.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("incremental", [False, True], ids=["daily", "incremental"])
async def test_analysis_still_times_out_before_merged_dispatch(
    environment, incremental
):
    """长时间未完成的前置分析仍被取消，不提前开始转发。"""
    cancelled = asyncio.Event()

    async def blocked_analysis(**_kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    analysis = environment.scheduler.analysis_service
    analysis.execute_daily_analysis.side_effect = blocked_analysis
    analysis.execute_incremental_final_report.side_effect = blocked_analysis
    result = await run_scheduled(environment, incremental)

    assert result["reason"] == "timeout"
    assert result["analysis_success"] is False
    assert cancelled.is_set()
    environment.adapter.send_forward_msg.assert_not_awaited()
    environment.config.get_merged_forward_timeout.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("incremental", [False, True], ids=["daily", "incremental"])
@pytest.mark.parametrize("unsupported", [False, True], ids=["disabled", "unsupported"])
async def test_normal_delivery_keeps_original_total_timeout(
    environment, incremental, unsupported
):
    """关闭合并或平台不支持时，不能因为进入分发而撤销原总时限。"""
    if unsupported:
        environment.adapter.capabilities.supports_forward_message = False
    else:
        environment.config.get_enable_merged_forward.return_value = False
    cancelled = asyncio.Event()

    async def blocked_text(*_args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    environment.dispatcher._dispatch_text = blocked_text
    result = await run_scheduled(environment, incremental)

    assert result["reason"] == "timeout"
    assert cancelled.is_set()
    environment.adapter.send_forward_msg.assert_not_awaited()
    environment.config.get_merged_forward_timeout.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("incremental", [False, True], ids=["daily", "incremental"])
async def test_external_cancel_still_reaches_merged_producers(environment, incremental):
    """移交期限后仍接受外部取消，不能屏蔽停止信号或触发传统重发。"""
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def blocked_comic(*_args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    environment.dispatcher.comic_handler = SimpleNamespace(
        prepare_for_report=blocked_comic
    )
    task = asyncio.create_task(run_scheduled(environment, incremental))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert cancelled.is_set()
    environment.adapter.send_forward_msg.assert_not_awaited()
    environment.scheduler._fallback_to_traditional.assert_not_awaited()


@pytest.mark.asyncio
async def test_incremental_cleanup_timeout_preserves_success(environment, monkeypatch):
    """已经成功投递后的清理卡住时按独立期限结束，成功结果保持不变。"""
    monkeypatch.setattr(auto_scheduler, "_INCREMENTAL_CLEANUP_TIMEOUT_SECONDS", 0.01)
    cancelled = asyncio.Event()

    async def blocked_cleanup(*_args):
        assert environment.adapter.send_forward_msg.await_count == 1
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    environment.scheduler.analysis_service.incremental_store = SimpleNamespace(
        cleanup_old_batches=AsyncMock(side_effect=blocked_cleanup)
    )
    result = await asyncio.wait_for(run_scheduled(environment, True), timeout=1)

    assert result["success"] is True
    assert result["report_sent"] is True
    assert cancelled.is_set()
    environment.scheduler._fallback_to_traditional.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("incremental", [False, True], ids=["daily", "incremental"])
async def test_business_trace_context_stays_in_child_task(
    environment, incremental, monkeypatch
):
    """更换超时实现后仍隔离业务追踪，不污染调度调用方的上下文。"""
    context = ContextVar("scheduled_trace", default="parent")

    def set_trace(**_kwargs):
        context.set("child")
        return environment.trace

    monkeypatch.setattr(TraceContext, "set", set_trace)
    result = await run_scheduled(environment, incremental)

    assert result["success"] is True
    assert context.get() == "parent"
