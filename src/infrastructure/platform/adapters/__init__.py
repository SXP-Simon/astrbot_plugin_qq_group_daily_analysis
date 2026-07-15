"""Optional platform adapter exports.

Each platform is imported independently so an unavailable optional SDK does not
prevent the QQ Official adapter from being registered.
"""

__all__: list[str] = []

try:
    from .discord_adapter import DiscordAdapter  # noqa: F401

    __all__.append("DiscordAdapter")
except ImportError:
    pass

try:
    from .lark_adapter import LarkAdapter  # noqa: F401

    __all__.append("LarkAdapter")
except ImportError:
    pass

try:
    from .onebot_adapter import OneBotAdapter  # noqa: F401

    __all__.append("OneBotAdapter")
except ImportError:
    pass

try:
    from .qq_official_adapter import QQOfficialAdapter  # noqa: F401

    __all__.append("QQOfficialAdapter")
except ImportError:
    pass
