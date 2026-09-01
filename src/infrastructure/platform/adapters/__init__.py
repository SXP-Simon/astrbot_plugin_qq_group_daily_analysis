"""可选平台适配器模块

采用按需懒加载机制，避免在插件初始化时加载未启用的第三方平台 SDK。
"""

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discord_adapter import DiscordAdapter
    from .onebot_adapter import OneBotAdapter
    from .qq_official_adapter import QQOfficialAdapter
    from .telegram_adapter import TelegramAdapter

__all__ = [
    "DiscordAdapter",
    "OneBotAdapter",
    "QQOfficialAdapter",
    "TelegramAdapter",
]

_ADAPTER_MODULES = {
    "DiscordAdapter": ".discord_adapter",
    "OneBotAdapter": ".onebot_adapter",
    "QQOfficialAdapter": ".qq_official_adapter",
    "TelegramAdapter": ".telegram_adapter",
}


def __getattr__(name: str):
    """按需动态导入适配器类。"""
    if name in _ADAPTER_MODULES:
        module = importlib.import_module(_ADAPTER_MODULES[name], package=__package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
