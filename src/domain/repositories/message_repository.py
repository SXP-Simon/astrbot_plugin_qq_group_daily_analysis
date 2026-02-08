"""
Message Repository Interfaces - Platform-agnostic abstractions
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict

from ..value_objects.unified_message import UnifiedMessage
from ..value_objects.platform_capabilities import PlatformCapabilities
from ..value_objects.unified_group import UnifiedGroup, UnifiedMember


class IMessageRepository(ABC):
    """
    Message repository interface
    
    Each platform adapter must implement this interface.
    All methods return unified format, hiding platform differences.
    """

    @abstractmethod
    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: Optional[str] = None,
    ) -> List[UnifiedMessage]:
        """
        Fetch group message history
        
        Args:
            group_id: Group ID
            days: Fetch messages from last N days
            max_count: Maximum message count
            before_id: Fetch messages before this ID (for pagination)
            
        Returns:
            List of unified messages, sorted by time ascending
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> PlatformCapabilities:
        """Get platform capabilities"""
        pass

    @abstractmethod
    def get_platform_name(self) -> str:
        """Get platform name"""
        pass


class IMessageSender(ABC):
    """Message sender interface"""

    @abstractmethod
    async def send_text(
        self,
        group_id: str,
        text: str,
        reply_to: Optional[str] = None,
    ) -> bool:
        """Send text message"""
        pass

    @abstractmethod
    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """Send image message"""
        pass

    @abstractmethod
    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: Optional[str] = None,
    ) -> bool:
        """Send file"""
        pass


class IGroupInfoRepository(ABC):
    """Group info repository interface"""

    @abstractmethod
    async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
        """Get group information"""
        pass

    @abstractmethod
    async def get_group_list(self) -> List[str]:
        """Get all group IDs the bot is in"""
        pass

    @abstractmethod
    async def get_member_list(self, group_id: str) -> List[UnifiedMember]:
        """Get group member list"""
        pass

    @abstractmethod
    async def get_member_info(
        self,
        group_id: str,
        user_id: str,
    ) -> Optional[UnifiedMember]:
        """Get specific member info"""
        pass
