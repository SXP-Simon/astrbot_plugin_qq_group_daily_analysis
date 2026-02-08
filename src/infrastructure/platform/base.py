"""
平台适配器基类
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict

from ...domain.repositories.message_repository import (
    IMessageRepository,
    IMessageSender,
    IGroupInfoRepository,
)
from ...domain.repositories.avatar_repository import IAvatarRepository
from ...domain.value_objects.platform_capabilities import PlatformCapabilities
from ...domain.value_objects.unified_message import UnifiedMessage
from ...domain.value_objects.unified_group import UnifiedGroup, UnifiedMember


class PlatformAdapter(
    IMessageRepository, 
    IMessageSender, 
    IGroupInfoRepository, 
    IAvatarRepository,
    ABC
):
    """
    平台适配器基类
    
    组合消息仓储、消息发送、群组信息和头像接口。
    每个平台适配器继承此类并实现所有方法。
    """

    def __init__(self, bot_instance: Any, config: dict = None):
        self.bot = bot_instance
        self.config = config or {}
        self._capabilities: Optional[PlatformCapabilities] = None

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
