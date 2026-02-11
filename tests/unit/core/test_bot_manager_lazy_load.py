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
from src.infrastructure.platform.factory import PlatformAdapterFactory  # noqa: E402

class TestBotManagerLazyLoad(unittest.TestCase):
    def setUp(self):
        self.config_manager = MagicMock()
        self.config_manager.get_bot_qq_ids.return_value = []
        self.bot_manager = BotManager(self.config_manager)
        
        # Mock Context and PlatformManager
        self.context = MagicMock()
        self.platform_manager = MagicMock()
        self.context.platform_manager = self.platform_manager
        self.bot_manager.set_context(self.context)

    def test_lazy_load_discord(self):
        """Test that BotManager lazily loads Discord adapter when client becomes ready later"""
        
        # 1. Setup a Mock Platform that is NOT ready yet (no client attribute or None)
        mock_platform = MagicMock()
        mock_platform.metadata.id = "discord"
        mock_platform.metadata.name = "discord"
        # Ensure it has NO client/bot attributes initially
        del mock_platform.client 
        del mock_platform.bot
        del mock_platform.get_client
        
        # Mock platform manager returning this platform
        self.platform_manager.get_insts.return_value = [mock_platform]
        
        # 2. Run auto discovery (Simulate on_platform_loaded)
        # Since it's async, we run it synchronously
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        discovered = loop.run_until_complete(self.bot_manager.auto_discover_bot_instances())
        
        # Verify it was "discovered" (added to dict) but likely as a placeholder or not fully init
        # Based on my code: discovered[platform_id] = platform (if client missing)
        self.assertIn("discord", discovered)
        self.assertEqual(discovered["discord"], mock_platform)
        
        # Verify internal state: stored in _platforms but NOT in _bot_instances yet
        self.assertIn("discord", self.bot_manager._platforms)
        self.assertNotIn("discord", self.bot_manager._bot_instances)
        
        # 3. Simulate Client becoming ready
        mock_client = MagicMock() # The DiscordBotClient
        mock_platform.client = mock_client # Now it has the client
        
        # 4. Call get_bot_instance - should trigger lazy load
        # We need to mock PlatformAdapterFactory to support "discord" and return a mock adapter
        # Actually factory already supports it, but we need to ensure it doesn't fail on creation
        # The create method takes (platform_name, bot_instance, config)
        
        # We assume "discord" is registered (it is in factory.py)
        # But we need to make sure DiscordAdapter can be instantiated with our mock client
        # DiscordAdapter needs discord module. If not present, it logs error.
        # We should patch discord module if needed, but in Docker it exists.
        
        # Let's try calling get_bot_instance
        instance = self.bot_manager.get_bot_instance("discord")
        
        # 5. Verify instance is returned and stored
        self.assertIsNotNone(instance)
        self.assertEqual(instance, mock_client) # get_bot_instance returns the bot_client (not adapter)
        
        # Verify it's now in _bot_instances
        self.assertIn("discord", self.bot_manager._bot_instances)
        
        # Verify adapter was created
        self.assertIn("discord", self.bot_manager._adapters)
        
        loop.close()

if __name__ == "__main__":
    unittest.main()
