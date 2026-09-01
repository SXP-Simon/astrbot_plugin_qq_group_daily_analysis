"""平台适配器模块

提供平台适配器基类和工厂。适配器类支持按需懒加载。
"""

import importlib
from typing import TYPE_CHECKING

from .base import PlatformAdapter
from .factory import PlatformAdapterFactory

if TYPE_CHECKING:
    from .adapters.discord_adapter import DiscordAdapter
    from .adapters.onebot_adapter import OneBotAdapter
    from .adapters.qq_official_adapter import QQOfficialAdapter
    from .adapters.telegram_adapter import TelegramAdapter

__all__ = [
    "PlatformAdapterFactory",
    "PlatformAdapter",
    "OneBotAdapter",
    "QQOfficialAdapter",
    "TelegramAdapter",
    "DiscordAdapter",
]

_LAZY_EXPORTS = {
    "OneBotAdapter": (".adapters.onebot_adapter", "OneBotAdapter"),
    "QQOfficialAdapter": (".adapters.qq_official_adapter", "QQOfficialAdapter"),
    "TelegramAdapter": (".adapters.telegram_adapter", "TelegramAdapter"),
    "DiscordAdapter": (".adapters.discord_adapter", "DiscordAdapter"),
}


def __getattr__(name: str):
    """动态懒加载平台适配器类以节省内存。"""
    if name in _LAZY_EXPORTS:
        module_path, class_name = _LAZY_EXPORTS[name]
        module = importlib.import_module(module_path, package=__package__)
        return getattr(module, class_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
