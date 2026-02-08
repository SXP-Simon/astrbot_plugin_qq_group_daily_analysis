"""
平台适配器工厂
"""

from typing import Optional, Any, Dict, Type

from .base import PlatformAdapter


class PlatformAdapterFactory:
    """
    平台适配器工厂
    
    根据平台名称创建适配器实例。
    使用注册表模式便于扩展。
    """

    _adapters: Dict[str, Type[PlatformAdapter]] = {}

    @classmethod
    def register(cls, platform_name: str, adapter_class: Type[PlatformAdapter]):
        """注册新适配器"""
        cls._adapters[platform_name.lower()] = adapter_class

    @classmethod
    def create(
        cls,
        platform_name: str,
        bot_instance: Any,
        config: dict = None,
    ) -> Optional[PlatformAdapter]:
        """
        创建平台适配器
        
        参数:
            platform_name: 平台名称（如 "aiocqhttp"、"telegram"）
            bot_instance: AstrBot 机器人实例
            config: 配置字典
            
        返回:
            平台适配器实例，如果不支持则返回 None
        """
        adapter_class = cls._adapters.get(platform_name.lower())

        if adapter_class is None:
            return None

        try:
            return adapter_class(bot_instance, config)
        except Exception:
            # 记录异常，但不崩溃
            import logging
            logging.getLogger(__name__).error(f"为 {platform_name} 创建适配器时出错", exc_info=True)
            return None

    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """获取所有支持的平台名称"""
        return list(cls._adapters.keys())

    @classmethod
    def is_supported(cls, platform_name: str) -> bool:
        """检查平台是否被支持"""
        return platform_name.lower() in cls._adapters


# 导入适配器以注册它们
def _register_adapters():
    try:
        from .adapters.onebot_adapter import OneBotAdapter
        PlatformAdapterFactory.register("aiocqhttp", OneBotAdapter)
        PlatformAdapterFactory.register("onebot", OneBotAdapter)
    except ImportError:
        pass
    
    try:
        from .adapters.discord_adapter import DiscordAdapter
        PlatformAdapterFactory.register("discord", DiscordAdapter)
        PlatformAdapterFactory.register("discord_bot", DiscordAdapter) # Add alias
    except ImportError:
        pass


_register_adapters()
