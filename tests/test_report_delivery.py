import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.infrastructure.scheduler.auto_scheduler import AutoScheduler


def test_dispatch_returns_false_when_no_report_format_is_sent():
    async def scenario():
        config_manager = SimpleNamespace(get_output_format=Mock(return_value=["text"]))
        dispatcher = ReportDispatcher(config_manager, None, None)
        dispatcher._dispatch_text = AsyncMock(return_value=False)

        assert await dispatcher.dispatch("123456", {}, "onebot-main") is False

        dispatcher._dispatch_text.return_value = True
        assert await dispatcher.dispatch("123456", {}, "onebot-main") is True

    asyncio.run(scenario())


def test_traditional_analysis_is_failed_when_report_delivery_fails():
    async def scenario():
        scheduler = object.__new__(AutoScheduler)
        scheduler._terminating = False
        scheduler._get_group_name_safe = AsyncMock(return_value="测试群")
        scheduler.bot_manager = SimpleNamespace(
            is_ready_for_auto_analysis=Mock(return_value=True)
        )
        scheduler.analysis_service = SimpleNamespace(
            execute_daily_analysis=AsyncMock(
                return_value={
                    "success": True,
                    "analysis_result": {},
                    "adapter": SimpleNamespace(platform_id="onebot-main"),
                }
            )
        )
        scheduler.report_dispatcher = SimpleNamespace(
            dispatch=AsyncMock(return_value=False)
        )

        result = await scheduler._perform_auto_analysis_for_group(
            "123456", "onebot-main"
        )

        assert result["analysis_success"] is True
        assert result["report_sent"] is False
        assert result["success"] is False
        assert result["reason"] == "report_delivery_failed"

        scheduler.analysis_service.execute_daily_analysis.return_value = {
            "success": True,
            "analysis_result": {},
            "adapter": SimpleNamespace(platform_id="onebot-main"),
        }
        scheduler.report_dispatcher.dispatch.return_value = True
        result = await scheduler._perform_auto_analysis_for_group(
            "123456", "onebot-main"
        )

        assert result["analysis_success"] is True
        assert result["report_sent"] is True
        assert result["success"] is True

    asyncio.run(scenario())


def test_incremental_final_report_requires_successful_delivery():
    async def scenario():
        scheduler = object.__new__(AutoScheduler)
        scheduler._terminating = False
        scheduler._get_group_name_safe = AsyncMock(return_value="测试群")
        scheduler.bot_manager = SimpleNamespace(
            is_ready_for_auto_analysis=Mock(return_value=True)
        )
        scheduler.analysis_service = SimpleNamespace(
            execute_incremental_final_report=AsyncMock(
                return_value={
                    "success": True,
                    "analysis_result": {},
                    "adapter": SimpleNamespace(platform_id="onebot-main"),
                }
            ),
            incremental_store=None,
        )
        scheduler.report_dispatcher = SimpleNamespace(
            dispatch=AsyncMock(return_value=False)
        )
        scheduler.config_manager = SimpleNamespace(get_analysis_days=Mock(return_value=1))

        result = await scheduler._perform_incremental_final_report_for_group(
            "123456", "onebot-main"
        )

        assert result["analysis_success"] is True
        assert result["report_sent"] is False
        assert result["success"] is False
        assert result["reason"] == "report_delivery_failed"

        scheduler.analysis_service.execute_incremental_final_report.return_value = {
            "success": True,
            "analysis_result": {},
            "adapter": SimpleNamespace(platform_id="onebot-main"),
        }
        scheduler.report_dispatcher.dispatch.return_value = True
        result = await scheduler._perform_incremental_final_report_for_group(
            "123456", "onebot-main"
        )

        assert result["analysis_success"] is True
        assert result["report_sent"] is True
        assert result["success"] is True

    asyncio.run(scenario())


def test_fallback_does_not_mask_failed_report_delivery():
    async def scenario():
        scheduler = object.__new__(AutoScheduler)
        scheduler._perform_auto_analysis_for_group_with_timeout = AsyncMock(
            return_value={
                "success": False,
                "analysis_success": True,
                "report_sent": False,
                "reason": "report_delivery_failed",
            }
        )

        result = await scheduler._fallback_to_traditional("123456", "onebot-main")

        assert result["success"] is False
        assert result["fallback"] is True
        assert result["report_sent"] is False

    asyncio.run(scenario())
