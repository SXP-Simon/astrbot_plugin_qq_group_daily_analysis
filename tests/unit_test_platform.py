import unittest
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add plugin root to path so we can import src
# Assuming this file is in tests/
plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

# Add AstrBot root to path so we can import astrbot.api
astrbot_root = os.path.abspath(os.path.join(plugin_root, "../../../"))
if astrbot_root not in sys.path:
    sys.path.insert(0, astrbot_root)

print(f"Added to sys.path: {plugin_root}, {astrbot_root}")

try:
    from src.infrastructure.platform.factory import PlatformAdapterFactory
    from src.infrastructure.platform.base import PlatformAdapter
    from src.infrastructure.platform.adapters.discord_adapter import DiscordAdapter, DISCORD_CAPABILITIES
    from src.application.analysis_orchestrator import AnalysisOrchestrator
    from src.domain.value_objects.unified_message import UnifiedMessage
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"sys.path: {sys.path}")
    # Try importing as package
    try:
        from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.platform.factory import PlatformAdapterFactory
        # ... and others
    except ImportError:
        pass
    raise e

class TestPlatformArchitecture(unittest.TestCase):
    
    def setUp(self):
        # Reset factory for isolation if needed, though hard with class methods
        pass

    def test_discord_adapter_capabilities(self):
        """测试 Discord 适配器能力配置"""
        adapter = DiscordAdapter(bot_instance=MagicMock(), config={"bot_user_id": "123"})
        caps = adapter.get_capabilities()
        
        self.assertEqual(caps.platform_name, "discord")
        self.assertTrue(caps.supports_message_history)
        self.assertTrue(caps.supports_image_message)
        # Check correct attribute name and value (30 from predefined caps)
        self.assertEqual(caps.max_message_history_days, 30)

    def test_factory_registration(self):
        """测试适配器工厂注册机制"""
        # Discord should be registered by import
        self.assertTrue(PlatformAdapterFactory.is_supported("discord"))
        self.assertTrue(PlatformAdapterFactory.is_supported("aiocqhttp"))
        
        # Test creation
        adapter = PlatformAdapterFactory.create("discord", MagicMock(), {})
        self.assertIsInstance(adapter, DiscordAdapter)

    def test_orchestrator_raw_conversion(self):
        """测试编排器的原始格式转换 (验证硬编码移除)"""
        # Mock adapter
        mock_adapter = MagicMock(spec=PlatformAdapter)
        mock_adapter.get_capabilities.return_value = DISCORD_CAPABILITIES
        
        # Mock fetch_messages return
        mock_msg = UnifiedMessage(
            message_id="1", sender_id="u1", sender_name="User", 
            group_id="g1", text_content="test", contents=[], 
            timestamp=1234567890, platform="discord"
        )
        mock_adapter.fetch_messages = AsyncMock(return_value=[mock_msg])
        
        # Mock convert_to_raw_format
        mock_adapter.convert_to_raw_format.return_value = [{"id": "1", "content": "raw"}]
        
        # Create orchestrator
        orchestrator = AnalysisOrchestrator(adapter=mock_adapter)
        
        # Run sync wrapper for async method (simplified for unit test structure)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Call fetch_messages_as_raw
        raw_msgs = loop.run_until_complete(
            orchestrator.fetch_messages_as_raw("g1")
        )
        
        # Verify result
        self.assertEqual(len(raw_msgs), 1)
        self.assertEqual(raw_msgs[0]["content"], "raw")
        
        # Verify adapter method was called (PROVING adapter pattern is used)
        mock_adapter.convert_to_raw_format.assert_called_once()
        loop.close()

if __name__ == "__main__":
    unittest.main()
