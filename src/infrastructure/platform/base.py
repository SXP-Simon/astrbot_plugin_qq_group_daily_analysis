"""
平台适配器基类
"""

from abc import ABC, abstractmethod
from typing import Any

from ...domain.repositories.avatar_repository import IAvatarRepository
from ...domain.repositories.message_repository import (
    IGroupInfoRepository,
    IMessageRepository,
    IMessageSender,
)
from ...domain.value_objects.platform_capabilities import PlatformCapabilities
from ...domain.value_objects.unified_message import UnifiedMessage


class PlatformAdapter(
    IMessageRepository, IMessageSender, IGroupInfoRepository, IAvatarRepository, ABC
):
    """
    基础设施：平台适配器基类

    继承自多个领域接口（仓储、发送器、群组信息、头像），
    充当领域层与具体聊天平台（如 OneBot, Discord）之间的中转站。

    Attributes:
        bot (Any): 平台对应的机器人 SDK 实例
        config (dict): 针对该平台的特定配置
    """

    def __init__(self, bot_instance: Any, config: dict | None = None):
        """
        初始化平台适配器。

        Args:
            bot_instance (Any): 后端机器人实例
            config (dict, optional): 平台特定配置项
        """
        self.bot = bot_instance
        self.config = config or {}
        self._capabilities: PlatformCapabilities | None = None

    @property
    def capabilities(self) -> PlatformCapabilities:
        """
        获取当前平台的能力描述对象。

        采用延迟加载机制，在首次访问时调用 `_init_capabilities`。

        Returns:
            PlatformCapabilities: 平台能力对象
        """
        if self._capabilities is None:
            self._capabilities = self._init_capabilities()
        return self._capabilities

    @abstractmethod
    def _init_capabilities(self) -> PlatformCapabilities:
        """
        初始化并返回当前平台的能力定义。

        子类必须实现此方法以声明其对历史记录、图片发送等功能的支持情况。

        Returns:
            PlatformCapabilities: 初始化后的能力对象
        """
        raise NotImplementedError

    def get_capabilities(self) -> PlatformCapabilities:
        """获取平台能力的便捷入口。"""
        return self.capabilities

    def get_platform_name(self) -> str:
        """获取当前适配器的平台标识名称。"""
        return self.capabilities.platform_name

    @abstractmethod
    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        """
        将平台无关的统一消息列表转换回当前平台的原生字典格式。

        此方法主要用于向后兼容，使新的统一接口能与依赖原生数据结构的旧版分析逻辑协同工作。

        Args:
            messages (list[UnifiedMessage]): 待转换的统一消息列表

        Returns:
            list[dict]: 转换后的平台原生消息字典列表
        """
        raise NotImplementedError
