import logging
import sys
import types
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
if str(PLUGIN_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT.parent))



if "astrbot.api" not in sys.modules:
    astrbot_module = types.ModuleType("astrbot")
    astrbot_api_module = types.ModuleType("astrbot.api")
    astrbot_event_module = types.ModuleType("astrbot.api.event")
    astrbot_provider_module = types.ModuleType("astrbot.api.provider")
    astrbot_star_module = types.ModuleType("astrbot.api.star")
    astrbot_message_components_module = types.ModuleType(
        "astrbot.api.message_components"
    )

    class AstrMessageEvent:
        pass

    class Context:
        pass

    class StarTools:
        @classmethod
        def get_data_dir(cls, name=""):
            return Path("/tmp")

    class Star:
        def __init__(self, context=None):
            self.context = context

        async def html_render(self, *args, **kwargs):
            return None

    class PermissionType:
        ADMIN = "ADMIN"
        USER = "USER"

    class EventMessageType:
        GROUP_MESSAGE = "GROUP_MESSAGE"

    class PlatformAdapterType:
        TELEGRAM = 1
        QQOFFICIAL = 2
        QQOFFICIAL_WEBHOOK = 4

    class filter:
        @staticmethod
        def command(*args, **kwargs):
            return lambda fn: fn

        @staticmethod
        def permission_type(*args, **kwargs):
            return lambda fn: fn

        @staticmethod
        def on_platform_loaded(*args, **kwargs):
            return lambda fn: fn

        @staticmethod
        def event_message_type(*args, **kwargs):
            return lambda fn: fn

        @staticmethod
        def platform_adapter_type(*args, **kwargs):
            return lambda fn: fn

        PermissionType = PermissionType
        EventMessageType = EventMessageType
        PlatformAdapterType = PlatformAdapterType

    class BaseMessageComponent:
        pass

    class Plain(BaseMessageComponent):
        def __init__(self, text=""):
            self.text = text

    class Image(BaseMessageComponent):
        @classmethod
        def fromFileSystem(cls, path):
            return cls()

        @classmethod
        def fromURL(cls, url):
            return cls()

    class Node(BaseMessageComponent):
        def __init__(self, uin=None, name=None, content=None):
            self.uin = uin
            self.name = name
            self.content = content

    class Nodes(BaseMessageComponent):
        def __init__(self, nodes=None):
            self.nodes = nodes or []

    class File(BaseMessageComponent):
        def __init__(self, file=None, name=None):
            self.file = file
            self.name = name

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

    astrbot_event_module.__path__ = []
    astrbot_event_filter_module = types.ModuleType("astrbot.api.event.filter")
    astrbot_event_filter_module.PermissionType = PermissionType
    astrbot_event_filter_module.EventMessageType = EventMessageType
    astrbot_event_filter_module.PlatformAdapterType = PlatformAdapterType
    astrbot_event_filter_module.command = filter.command
    astrbot_event_filter_module.permission_type = filter.permission_type
    astrbot_event_filter_module.on_platform_loaded = filter.on_platform_loaded
    astrbot_event_filter_module.event_message_type = filter.event_message_type
    astrbot_event_filter_module.platform_adapter_type = filter.platform_adapter_type

    astrbot_api_module.logger = logging.getLogger("astrbot-test")
    astrbot_event_module.AstrMessageEvent = AstrMessageEvent
    astrbot_event_module.filter = filter
    astrbot_provider_module.LLMResponse = LLMResponse
    astrbot_star_module.Context = Context
    astrbot_star_module.Star = Star
    astrbot_star_module.StarTools = StarTools
    astrbot_message_components_module.BaseMessageComponent = BaseMessageComponent
    astrbot_message_components_module.Plain = Plain
    astrbot_message_components_module.Image = Image
    astrbot_message_components_module.Node = Node
    astrbot_message_components_module.Nodes = Nodes
    astrbot_api_module.AstrBotConfig = dict
    astrbot_module.api = astrbot_api_module

    astrbot_core_module = types.ModuleType("astrbot.core")
    astrbot_core_message_module = types.ModuleType("astrbot.core.message")
    astrbot_core_message_components_module = types.ModuleType(
        "astrbot.core.message.components"
    )
    astrbot_core_message_components_module.File = File

    sys.modules.setdefault("astrbot", astrbot_module)
    sys.modules.setdefault("astrbot.api", astrbot_api_module)
    sys.modules.setdefault("astrbot.api.event", astrbot_event_module)
    sys.modules.setdefault("astrbot.api.event.filter", astrbot_event_filter_module)
    sys.modules.setdefault("astrbot.api.provider", astrbot_provider_module)
    sys.modules.setdefault("astrbot.api.star", astrbot_star_module)
    sys.modules.setdefault(
        "astrbot.api.message_components", astrbot_message_components_module
    )
    sys.modules.setdefault("astrbot.core", astrbot_core_module)
    sys.modules.setdefault("astrbot.core.message", astrbot_core_message_module)
    sys.modules.setdefault(
        "astrbot.core.message.components", astrbot_core_message_components_module
    )



