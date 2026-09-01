"""平台适配器工厂

根据平台名称按需延迟加载并创建适配器实例。
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping

from ...utils.logger import logger
from .base import PlatformAdapter

# 预定义支持的平台标识及其对应的模块与适配器类（用于按需懒加载）
_LAZY_ADAPTER_REGISTRY: dict[str, tuple[str, str]] = {
    "aiocqhttp": (".adapters.onebot_adapter", "OneBotAdapter"),
    "onebot": (".adapters.onebot_adapter", "OneBotAdapter"),
    "discord": (".adapters.discord_adapter", "DiscordAdapter"),
    "discord_bot": (".adapters.discord_adapter", "DiscordAdapter"),
    "telegram": (".adapters.telegram_adapter", "TelegramAdapter"),
    "qq_official": (".adapters.qq_official_adapter", "QQOfficialAdapter"),
    "qq_official_webhook": (".adapters.qq_official_adapter", "QQOfficialAdapter"),
}


class PlatformAdapterFactory:
    """平台适配器工厂

    根据平台名称动态按需加载并创建适配器实例，避免未启用平台的 SDK 占用内存。
    """

    _adapters: dict[str, type[PlatformAdapter]] = {}

    @classmethod
    def register(cls, platform_name: str, adapter_class: type[PlatformAdapter]) -> None:
        """注册新适配器类。

        Args:
            platform_name: 平台标识名称。
            adapter_class: 适配器类。
        """
        cls._adapters[platform_name.lower().strip()] = adapter_class

    @classmethod
    def get_adapter_class(cls, platform_name: str) -> type[PlatformAdapter] | None:
        """按需获取或动态加载平台适配器类。

        Args:
            platform_name: 平台标识名称（如 "aiocqhttp", "telegram" 等）。

        Returns:
            平台适配器类，若不支持或加载失败则返回 None。
        """
        platform_key = platform_name.lower().strip()
        if platform_key in cls._adapters:
            return cls._adapters[platform_key]

        if platform_key in _LAZY_ADAPTER_REGISTRY:
            module_rel_path, class_name = _LAZY_ADAPTER_REGISTRY[platform_key]
            try:
                module = importlib.import_module(module_rel_path, package=__package__)
                adapter_cls = getattr(module, class_name, None)
                if adapter_cls is not None:
                    cls._adapters[platform_key] = adapter_cls
                    return adapter_cls
            except ImportError:
                logger.warning(
                    f"平台 {platform_name} 的适配器模块 {module_rel_path} 无法加载，可能未安装对应依赖"
                )
                return None
            except Exception:
                logger.error(
                    f"加载平台 {platform_name} 的适配器模块时发生异常", exc_info=True
                )
                return None

        return None

    @classmethod
    def create(
        cls,
        platform_name: str,
        bot_instance: object,
        config: Mapping[str, object] | None = None,
    ) -> PlatformAdapter | None:
        """创建平台适配器实例。

        Args:
            platform_name: 平台名称（如 "aiocqhttp"、"telegram"）。
            bot_instance: 机器人实例。
            config: 配置字典。

        Returns:
            平台适配器实例，如果不支持则返回 None。
        """
        adapter_class = cls.get_adapter_class(platform_name)

        if adapter_class is None:
            return None

        try:
            return adapter_class(bot_instance, config)
        except Exception:
            # 记录异常，但不崩溃
            logger.error(f"为 {platform_name} 创建适配器时出错", exc_info=True)
            return None

    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """获取所有支持的平台名称。

        Returns:
            支持的平台名称列表。
        """
        return sorted(set(cls._adapters.keys()) | set(_LAZY_ADAPTER_REGISTRY.keys()))

    @classmethod
    def is_supported(cls, platform_name: str) -> bool:
        """检查平台是否被支持。

        Args:
            platform_name: 平台名称。

        Returns:
            如果支持返回 True，否则返回 False。
        """
        platform_key = platform_name.lower().strip()
        return platform_key in cls._adapters or platform_key in _LAZY_ADAPTER_REGISTRY
