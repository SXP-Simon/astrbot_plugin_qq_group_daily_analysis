"""
头像仓储接口 - 跨平台头像抽象
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict


class IAvatarRepository(ABC):
    """
    头像仓储接口
    
    不同平台获取头像的方式不同：
    - QQ/OneBot: URL 模板 (q1.qlogo.cn)
    - Telegram: API 调用 (getUserProfilePhotos + getFile)
    - Discord: CDN URL 模板 (cdn.discordapp.com)
    - Slack: users.info API profile.image_* 字段
    """

    @abstractmethod
    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """
        获取用户头像 URL
        
        参数:
            user_id: 用户 ID
            size: 期望的头像尺寸（将选择最接近的可用尺寸）
            
        返回:
            头像 URL，如果不可用则返回 None
        """
        pass

    @abstractmethod
    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """
        获取用户头像的 Base64 数据
        
        用于需要嵌入图片的场景（如 HTML 模板渲染）
        
        返回:
            Base64 编码的图片数据 (data:image/png;base64,...)，
            如果不可用则返回 None
        """
        pass

    @abstractmethod
    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取群组头像 URL"""
        pass

    @abstractmethod
    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """
        批量获取用户头像 URL
        
        用于报告生成时需要一次获取多个头像
        """
        pass

    def get_default_avatar_url(self) -> str:
        """获取默认头像 URL（当用户头像不可用时）"""
        return "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTEyIDEyYzIuMjEgMCA0LTEuNzkgNC00cy0xLjc5LTQtNC00LTQgMS43OS00IDQgMS43OSA0IDQgNHptMCAyYy0yLjY3IDAtOCAxLjM0LTggNHYyaDE2di0yYzAtMi42Ni01LjMzLTQtOC00eiIvPjwvc3ZnPg=="
