import unittest
import sys
import os
from unittest.mock import MagicMock

# Add paths
plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)
astrbot_root = os.path.abspath(os.path.join(plugin_root, "../../../"))
if astrbot_root not in sys.path:
    sys.path.insert(0, astrbot_root)

from src.core.bot_manager import BotManager  # noqa: E402

class TestBotManagerMetadata(unittest.TestCase):
    def setUp(self):
        self.config_manager = MagicMock()
        self.config_manager.get_bot_qq_ids.return_value = []
        self.bot_manager = BotManager(self.config_manager)
        
        self.context = MagicMock()
        self.platform_manager = MagicMock()
        self.context.platform_manager = self.platform_manager
        self.bot_manager.set_context(self.context)

    def test_metadata_retrieval_via_meta_method(self):
        """Test retrieving metadata via meta() method if attribute is missing"""
        
        # Mock Platform with NO metadata attribute, but has meta() method
        mock_platform = MagicMock()
        del mock_platform.metadata # Ensure no attribute
        
        mock_meta = MagicMock()
        mock_meta.id = "discord_instance_1"
        mock_meta.type = "discord"
        mock_meta.name = "MyDiscordBot"
        
        mock_platform.meta.return_value = mock_meta
        
        # Setup get_insts
        self.platform_manager.get_insts.return_value = [mock_platform]
        
        # Run auto_discover
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        discovered = loop.run_until_complete(self.bot_manager.auto_discover_bot_instances())
        
        # Verify it was discovered
        self.assertIn("discord_instance_1", discovered)
        # It should be in _platforms
        self.assertIn("discord_instance_1", self.bot_manager._platforms)
        
        loop.close()

if __name__ == "__main__":
    unittest.main()
