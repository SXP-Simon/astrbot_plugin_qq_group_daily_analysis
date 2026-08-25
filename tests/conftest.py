import logging
import sys
import types
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


if "astrbot.api" not in sys.modules:
    astrbot_module = types.ModuleType("astrbot")
    astrbot_api_module = types.ModuleType("astrbot.api")
    astrbot_event_module = types.ModuleType("astrbot.api.event")
    astrbot_provider_module = types.ModuleType("astrbot.api.provider")
    astrbot_star_module = types.ModuleType("astrbot.api.star")

    class AstrMessageEvent:
        pass

    class Context:
        pass

    class StarTools:
        pass

    class LLMResponse:
        def __init__(
            self,
            role="assistant",
            completion_text="",
            usage=None,
            raw_completion=None,
        ):
            self.role = role
            self.completion_text = completion_text
            self.usage = usage
            self.raw_completion = raw_completion

    astrbot_api_module.logger = logging.getLogger("astrbot-test")
    astrbot_event_module.AstrMessageEvent = AstrMessageEvent
    astrbot_provider_module.LLMResponse = LLMResponse
    astrbot_star_module.Context = Context
    astrbot_star_module.StarTools = StarTools
    astrbot_api_module.AstrBotConfig = dict
    astrbot_module.api = astrbot_api_module
    sys.modules.setdefault("astrbot", astrbot_module)
    sys.modules.setdefault("astrbot.api", astrbot_api_module)
    sys.modules.setdefault("astrbot.api.event", astrbot_event_module)
    sys.modules.setdefault("astrbot.api.provider", astrbot_provider_module)
    sys.modules.setdefault("astrbot.api.star", astrbot_star_module)
