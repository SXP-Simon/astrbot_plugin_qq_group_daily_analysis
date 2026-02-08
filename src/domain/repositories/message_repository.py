"""
消息仓储接口 - 平台无关的抽象
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict

from ..value_objects.unified_message import UnifiedMessage
from ..value_objects.platform_capabilities import PlatformCapabilities
from ..value_objects.unified_group import UnifiedGroup, UnifiedMember


class IMessageRepository(ABC):
    """
    消息仓储接口
    
    每个平台适配器必须实现此接口。
    所有方法返回统一格式，隐藏平台差异。
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
        获取群组消息历史
        
        参数:
            group_id: 群组 ID
            days: 获取最近 N 天的消息
            max_count: 最大消息数量
            before_id: 获取此 ID 之前的消息（用于分页）
            
        返回:
            统一消息列表，按时间升序排列
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> PlatformCapabilities:
        """获取平台能力"""
        pass

    @abstractmethod
    def get_platform_name(self) -> str:
        """获取平台名称"""
        pass


class IMessageSender(ABC):
    """消息发送接口"""

    @abstractmethod
    async def send_text(
        self,
        group_id: str,
        text: str,
        reply_to: Optional[str] = None,
    ) -> bool:
        """发送文本消息"""
        pass

    @abstractmethod
    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """发送图片消息"""
        pass

    @abstractmethod
    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: Optional[str] = None,
    ) -> bool:
        """发送文件"""
        pass


class IGroupInfoRepository(ABC):
    """群组信息仓储接口"""

    @abstractmethod
    async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
        """获取群组信息"""
        pass

    @abstractmethod
    async def get_group_list(self) -> List[str]:
        """获取机器人所在的所有群组 ID"""
        pass

    @abstractmethod
    async def get_member_list(self, group_id: str) -> List[UnifiedMember]:
        """获取群组成员列表"""
        pass

    @abstractmethod
    async def get_member_info(
        self,
        group_id: str,
        user_id: str,
    ) -> Optional[UnifiedMember]:
        """获取指定成员信息"""
        pass
