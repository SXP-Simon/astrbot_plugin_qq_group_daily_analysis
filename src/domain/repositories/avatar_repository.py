"""
Avatar Repository Interface - Cross-platform avatar abstraction
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict


class IAvatarRepository(ABC):
    """
    Avatar repository interface
    
    Different platforms have different ways to get avatars:
    - QQ/OneBot: URL template (q1.qlogo.cn)
    - Telegram: API call (getUserProfilePhotos + getFile)
    - Discord: CDN URL template (cdn.discordapp.com)
    - Slack: users.info API profile.image_* fields
    """

    @abstractmethod
    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """
        Get user avatar URL
        
        Args:
            user_id: User ID
            size: Desired avatar size (will pick closest available)
            
        Returns:
            Avatar URL, or None if unavailable
        """
        pass

    @abstractmethod
    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """
        Get user avatar as Base64 data
        
        For scenarios needing embedded images (e.g., HTML template rendering)
        
        Returns:
            Base64 encoded image data (data:image/png;base64,...),
            or None if unavailable
        """
        pass

    @abstractmethod
    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """Get group avatar URL"""
        pass

    @abstractmethod
    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """
        Batch get user avatar URLs
        
        For report generation needing multiple avatars at once
        """
        pass

    def get_default_avatar_url(self) -> str:
        """Get default avatar URL (when user avatar unavailable)"""
        return "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTEyIDEyYzIuMjEgMCA0LTEuNzkgNC00cy0xLjc5LTQtNC00LTQgMS43OS00IDQgMS43OSA0IDQgNHptMCAyYy0yLjY3IDAtOCAxLjM0LTggNHYyaDE2di0yYzAtMi42Ni01LjMzLTQtOC00eiIvPjwvc3ZnPg=="
