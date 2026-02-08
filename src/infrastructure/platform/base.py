"""
Platform Adapter Base Class
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
    Platform adapter base class
    
    Combines message repository, message sender, group info, and avatar interfaces.
    Each platform adapter inherits this class and implements all methods.
    """

    def __init__(self, bot_instance: Any, config: dict = None):
        self.bot = bot_instance
        self.config = config or {}
        self._capabilities: Optional[PlatformCapabilities] = None

    @property
    def capabilities(self) -> PlatformCapabilities:
        """Platform capabilities (lazy initialization)"""
        if self._capabilities is None:
            self._capabilities = self._init_capabilities()
        return self._capabilities

    @abstractmethod
    def _init_capabilities(self) -> PlatformCapabilities:
        """Initialize platform capabilities, subclass must implement"""
        raise NotImplementedError

    def get_capabilities(self) -> PlatformCapabilities:
        return self.capabilities

    def get_platform_name(self) -> str:
        return self.capabilities.platform_name
