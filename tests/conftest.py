import logging
import sys
import types


if "astrbot.api" not in sys.modules:
    astrbot_module = types.ModuleType("astrbot")
    astrbot_api_module = types.ModuleType("astrbot.api")
    astrbot_event_module = types.ModuleType("astrbot.api.event")
    astrbot_star_module = types.ModuleType("astrbot.api.star")

    class AstrMessageEvent:
        pass

    class Context:
        pass

    astrbot_api_module.logger = logging.getLogger("astrbot-test")
    astrbot_event_module.AstrMessageEvent = AstrMessageEvent
    astrbot_star_module.Context = Context
    astrbot_module.api = astrbot_api_module
    sys.modules.setdefault("astrbot", astrbot_module)
    sys.modules.setdefault("astrbot.api", astrbot_api_module)
    sys.modules.setdefault("astrbot.api.event", astrbot_event_module)
    sys.modules.setdefault("astrbot.api.star", astrbot_star_module)
