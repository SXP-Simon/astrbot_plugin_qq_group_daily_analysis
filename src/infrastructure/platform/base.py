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
    平台适配器基类

    组合消息仓储、消息发送、群组信息和头像接口。
    每个平台适配器继承此类并实现所有方法。
    """

    def __init__(self, bot_instance: Any, config: dict = None):
        self.bot = bot_instance
        self.config = config or {}
        self._capabilities: PlatformCapabilities | None = None

    @property
    def capabilities(self) -> PlatformCapabilities:
        """平台能力（延迟初始化）"""
        if self._capabilities is None:
            self._capabilities = self._init_capabilities()
        return self._capabilities

    @abstractmethod
    def _init_capabilities(self) -> PlatformCapabilities:
        """初始化平台能力，子类必须实现"""
        raise NotImplementedError

    def get_capabilities(self) -> PlatformCapabilities:
        return self.capabilities

    def get_platform_name(self) -> str:
        return self.capabilities.platform_name

    @abstractmethod
    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        """
        将统一消息格式转换为平台原生格式。

        此方法由各平台适配器实现，返回该平台的原生消息格式。
        用于与现有分析器的向后兼容。

        参数：
            messages: UnifiedMessage 列表

        返回：
            平台原生格式的消息字典列表
        """
        raise NotImplementedError
