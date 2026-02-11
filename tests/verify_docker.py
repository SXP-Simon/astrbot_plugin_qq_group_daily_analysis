import sys
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

# Add paths for Docker environment
sys.path.append("/AstrBot")
sys.path.append("/AstrBot/data/plugins")  # Ensure we can import the plugin as a package

# Import real modules using package path
try:
    from astrbot_plugin_qq_group_daily_analysis.src.scheduler.auto_scheduler import (
        AutoScheduler,
    )
    from astrbot_plugin_qq_group_daily_analysis.main import QQGroupDailyAnalysis
except ImportError as e:
    print(f"ImportError in Docker: {e}")
    # Fallback to local paths if testing locally
    sys.path.append(r"c:\Helianthus\astrpro\AstrBot-master\data\plugins")
    from astrbot_plugin_qq_group_daily_analysis.src.scheduler.auto_scheduler import (
        AutoScheduler,
    )
    from astrbot_plugin_qq_group_daily_analysis.main import QQGroupDailyAnalysis


class TestPhase3Docker(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_jobs(self):
        """Test that schedule_jobs correctly adds jobs to APScheduler."""
        # Mocks for Logic only
        config_manager = MagicMock()
        config_manager.get_enable_auto_analysis.return_value = True
        config_manager.get_auto_analysis_time.return_value = ["09:00", "18:30"]

        context = MagicMock()
        scheduler = MagicMock()
        context.cron_manager.scheduler = scheduler

        # Instantiate AutoScheduler
        auto_scheduler = AutoScheduler(
            config_manager,
            MagicMock(),  # message_handler
            MagicMock(),  # analyzer
            MagicMock(),  # report_generator
            MagicMock(),  # bot_manager
            MagicMock(),  # retry_manager
        )

        # Call schedule_jobs
        auto_scheduler.schedule_jobs(context)

        # Verify add_job was called twice
        self.assertEqual(scheduler.add_job.call_count, 2)

        # Verify call arguments
        args, kwargs = scheduler.add_job.call_args_list[0]
        self.assertEqual(
            kwargs["id"], "astrbot_plugin_qq_group_daily_analysis_trigger_0"
        )
        # Verify trigger via string representation to avoid attribute errors with real CronTrigger objects
        trigger_str = str(kwargs["trigger"])
        self.assertTrue(
            "hour='9'" in trigger_str or "hour=9" in trigger_str,
            f"Trigger mismatch: {trigger_str}",
        )
        self.assertTrue(
            "minute='0'" in trigger_str or "minute=0" in trigger_str,
            f"Trigger mismatch: {trigger_str}",
        )

        args, kwargs = scheduler.add_job.call_args_list[1]
        self.assertEqual(
            kwargs["id"], "astrbot_plugin_qq_group_daily_analysis_trigger_1"
        )
        trigger_str = str(kwargs["trigger"])
        self.assertTrue(
            "hour='18'" in trigger_str or "hour=18" in trigger_str,
            f"Trigger mismatch: {trigger_str}",
        )
        self.assertTrue(
            "minute='30'" in trigger_str or "minute=30" in trigger_str,
            f"Trigger mismatch: {trigger_str}",
        )

    async def test_main_on_platform_loaded(self):
        """Test that main.py's on_platform_loaded triggers job scheduling."""
        context = MagicMock()
        config = MagicMock()

        # Patch dependencies in main.py using full package path
        with (
            patch(
                "astrbot_plugin_qq_group_daily_analysis.main.ConfigManager"
            ) as MockConfigManager,
            patch(
                "astrbot_plugin_qq_group_daily_analysis.main.BotManager"
            ) as MockBotManager,
            patch(
                "astrbot_plugin_qq_group_daily_analysis.main.MessageAnalyzer"
            ),
            patch(
                "astrbot_plugin_qq_group_daily_analysis.main.ReportGenerator"
            ),
            patch(
                "astrbot_plugin_qq_group_daily_analysis.main.RetryManager"
            ),
            patch(
                "astrbot_plugin_qq_group_daily_analysis.main.AutoScheduler"
            ) as MockAutoScheduler,
        ):
            mock_auto_scheduler_instance = MockAutoScheduler.return_value
            mock_config_instance = MockConfigManager.return_value
            mock_config_instance.get_enable_auto_analysis.return_value = True

            mock_bot_manager_instance = MockBotManager.return_value
            mock_bot_manager_instance.initialize_from_config = AsyncMock(
                return_value={"test_platform": MagicMock()}
            )

            # Instantiate plugin
            plugin = QQGroupDailyAnalysis(context, config)

            # Call on_platform_loaded
            event = MagicMock()
            await plugin.on_platform_loaded(event)

            # Verify initialized_from_config called
            mock_bot_manager_instance.initialize_from_config.assert_called_once()
            # Verify schedule_jobs called
            mock_auto_scheduler_instance.schedule_jobs.assert_called_once_with(context)


if __name__ == "__main__":
    unittest.main()
