"""
Platform Adapter Factory
"""

from typing import Optional, Any, Dict, Type

from .base import PlatformAdapter


class PlatformAdapterFactory:
    """
    Platform adapter factory
    
    Creates adapter instances based on platform name.
    Uses registry pattern for easy extension.
    """

    _adapters: Dict[str, Type[PlatformAdapter]] = {}

    @classmethod
    def register(cls, platform_name: str, adapter_class: Type[PlatformAdapter]):
        """Register a new adapter"""
        cls._adapters[platform_name.lower()] = adapter_class

    @classmethod
    def create(
        cls,
        platform_name: str,
        bot_instance: Any,
        config: dict = None,
    ) -> Optional[PlatformAdapter]:
        """
        Create platform adapter
        
        Args:
            platform_name: Platform name (e.g., "aiocqhttp", "telegram")
            bot_instance: AstrBot bot instance
            config: Configuration dict
            
        Returns:
            Platform adapter instance, or None if unsupported
        """
        adapter_class = cls._adapters.get(platform_name.lower())

        if adapter_class is None:
            return None

        try:
            return adapter_class(bot_instance, config)
        except Exception:
            return None

    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """Get all supported platform names"""
        return list(cls._adapters.keys())

    @classmethod
    def is_supported(cls, platform_name: str) -> bool:
        """Check if platform is supported"""
        return platform_name.lower() in cls._adapters


# Import adapters to register them
def _register_adapters():
    try:
        from .adapters.onebot_adapter import OneBotAdapter
        PlatformAdapterFactory.register("aiocqhttp", OneBotAdapter)
        PlatformAdapterFactory.register("onebot", OneBotAdapter)
    except ImportError:
        pass


_register_adapters()
