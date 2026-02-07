import sys
import types
from unittest.mock import MagicMock


# Helper to mock packages
def mock_package(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m


# Mock key dependencies
mock_package("mcp")
mock_package("mcp.server")
mock_package("mcp.server.fastmcp")
mock_package("google")
mock_package("google.genai")
mock_package("google.generativeai")
mock_package("openai")
mock_package("anthropic")
mock_package("httpx")

# Adjust path to include the plugin directory
sys.path.append(
    r"c:\Helianthus\astrpro\AstrBot-master\data\plugins\astrbot_plugin_qq_group_daily_analysis"
)
sys.path.append(r"c:\Helianthus\astrpro\AstrBot-master")

print("Starting import...")
try:
    from main import QQGroupDailyAnalysis

    print("Import successful")
except Exception:
    import traceback

    traceback.print_exc()
