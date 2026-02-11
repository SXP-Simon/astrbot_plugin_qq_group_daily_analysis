import sys
import types
from unittest.mock import MagicMock


# Helper to mock packages
def mock_package(name):
    m = types.ModuleType(name)
    m.__path__ = []
    m.__spec__ = None  # Fix for importlib
    m.__loader__ = None
    sys.modules[name] = m
    return m


# Mock key dependencies with proper linking
mcp = mock_package("mcp")
mcp_server = mock_package("mcp.server")
mcp_server_fastmcp = mock_package("mcp.server.fastmcp")
mcp_types = mock_package("mcp.types")
# Link submodules
mcp.server = mcp_server
mcp.types = mcp_types
mcp_server.fastmcp = mcp_server_fastmcp

# Add CallToolResult to mcp.types
mcp_types.CallToolResult = MagicMock()

google = mock_package("google")
google_genai = mock_package("google.genai")
google_generativeai = mock_package("google.generativeai")
google.genai = google_genai
google.generativeai = google_generativeai

openai = mock_package("openai")
openai_types = mock_package("openai.types")
openai.types = openai_types

anthropic = mock_package("anthropic")
anthropic_types = mock_package("anthropic.types")
anthropic.types = anthropic_types

httpx = mock_package("httpx")

import asyncio  # noqa: E402
import unittest  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

# Adjust path to include the plugin directory
sys.path.append(
    r"c:\Helianthus\astrpro\AstrBot-master\data\plugins\astrbot_plugin_qq_group_daily_analysis"
)
sys.path.append(r"c:\Helianthus\astrpro\AstrBot-master")
# Add Docker container path
sys.path.append("/AstrBot")
sys.path.append("/AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis")

from src.scheduler.auto_scheduler import AutoScheduler  # noqa: E402
from main import QQGroupDailyAnalysis  # noqa: E402
from astrbot.api.event import filter  # noqa: E402, F401


class TestPhase3(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_jobs(self):
        """Test that schedule_jobs correctly adds jobs to APScheduler."""
        # Mocks
        config_manager = MagicMock()
        config_manager.get_enable_auto_analysis.return_value = True
        config_manager.get_auto_analysis_time.return_value = ["09:00", "18:30"]

        context = MagicMock()
        scheduler = MagicMock()
        context.cron_manager.scheduler = scheduler

        # Instantiate AutoScheduler (mocking dependencies)
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

        # Verify unschedule_jobs was called (scheduler.get_job called)
        # Verify add_job was called twice
        self.assertEqual(scheduler.add_job.call_count, 2)

        # Verify call arguments for first job
        args, kwargs = scheduler.add_job.call_args_list[0]
        # Check trigger args
        self.assertEqual(
            kwargs["id"], "astrbot_plugin_qq_group_daily_analysis_trigger_0"
        )
        self.assertEqual(kwargs["trigger"].hour, 9)
        self.assertEqual(kwargs["trigger"].minute, 0)

        # Verify call arguments for second job
        args, kwargs = scheduler.add_job.call_args_list[1]
        self.assertEqual(
            kwargs["id"], "astrbot_plugin_qq_group_daily_analysis_trigger_1"
        )
        self.assertEqual(kwargs["trigger"].hour, 18)
        self.assertEqual(kwargs["trigger"].minute, 30)

    async def test_main_on_platform_loaded(self):
        """Test that main.py's on_platform_loaded triggers job scheduling."""
        # Mock Context and Config
        context = MagicMock()
        config = MagicMock()

        # Mock dependencies inside QQGroupDailyAnalysis
        # We need to patch the classes instantiated in __init__
        with (
            patch("main.ConfigManager") as MockConfigManager,
            patch("main.BotManager") as MockBotManager,
            patch("main.MessageAnalyzer"),
            patch("main.ReportGenerator"),
            patch("main.RetryManager") as MockRetryManager,
            patch("main.AutoScheduler") as MockAutoScheduler,
            patch("main.TraceLogFilter"),
        ):
            # Setup mocks
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

            # Verify retry_manager start called
            MockRetryManager.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
