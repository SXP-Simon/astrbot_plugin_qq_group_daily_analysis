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
    from src.infrastructure.platform.factory import PlatformAdapterFactory  # noqa: E402
    from src.infrastructure.platform.adapters.discord_adapter import DiscordAdapter  # noqa: E402
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

    def test_discord_fetch_messages(self):
        """测试 Discord 消息获取逻辑 (Mocked)"""
        # Mock bot instance
        mock_bot = MagicMock()
        mock_channel = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        
        # Mock message history
        # Create a mock message that mimics discord.Message
        mock_msg = MagicMock()
        mock_msg.id = 12345
        mock_msg.content = "test message"
        mock_msg.author.id = 999
        mock_msg.author.name = "User"
        mock_msg.created_at.timestamp.return_value = 1600000000
        mock_msg.attachments = []
        mock_msg.embeds = []
        mock_msg.stickers = []
        mock_msg.reference = None
        
        # history returns an async iterator
        async def async_iter():
            yield mock_msg
            
        mock_channel.history.return_value = async_iter()
        
        # Initialize adapter
        adapter = DiscordAdapter(bot_instance=mock_bot, config={"bot_user_id": "123"})
        
        # Run async test
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        messages = loop.run_until_complete(
            adapter.fetch_messages("1001", days=1)
        )
        
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].text_content, "test message")
        self.assertEqual(messages[0].platform, "discord")
        
        loop.close()

if __name__ == "__main__":
    unittest.main()
