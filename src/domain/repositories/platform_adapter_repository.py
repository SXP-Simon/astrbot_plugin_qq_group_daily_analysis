"""跨平台适配器协议与仓储契约 (Platform Adapter Protocol)

定义 OneBot / QQOfficial / Telegram / Discord 等底层驱动必须实现的统一行为协议，
以及群文件、群相册等平台特有扩展能力的结构化行为协议 (Protocol)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..value_objects import (
        PlatformCapabilities,
        UnifiedGroup,
        UnifiedMember,
        UnifiedMessage,
    )


@runtime_checkable
class PlatformAdapterProtocol(Protocol):
    """跨平台适配器标准行为协议。"""

    @property
    def platform_id(self) -> str:
        """获取平台实例唯一标识。"""
        ...

    @property
    def capabilities(self) -> PlatformCapabilities:
        """获取平台能力特性集。"""
        ...

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: str | None = None,
        since_ts: int | float | None = None,
    ) -> list[UnifiedMessage]:
        """从平台拉取历史消息记录。"""
        ...

    async def send_text(self, group_id: str, text: str) -> bool:
        """发送纯文本消息。"""
        ...

    async def send_image(
        self, group_id: str, image_path: str, caption: str = ""
    ) -> bool:
        """发送图片消息。"""
        ...

    async def send_forward_msg(
        self,
        group_id: str,
        nodes: list[dict],
    ) -> bool:
        """发送合并转发消息。"""
        ...

    async def send_text_report(
        self,
        group_id: str,
        content: str,
        fallback_content: str | None = None,
    ) -> bool:
        """发送结构化文本分析报告。"""
        ...

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        """获取群组基础信息。"""
        ...

    async def get_group_member_list(self, group_id: str) -> list[UnifiedMember] | None:
        """获取群成员列表。"""
        ...

    async def get_user_avatar_url(
        self, user_id: str, size: int = 40
    ) -> str | None:
        """获取用户头像 URL。"""
        ...

    def remember_user_profile(
        self,
        user_id: str,
        nickname: str | None = None,
        avatar_url: str | None = None,
    ) -> None:
        """缓存并记录用户基础档案。"""
        ...

    async def is_group_muted(self, group_id: str) -> bool:
        """检查群组是否处于全员或机器人禁言状态。"""
        ...

    async def set_reaction(
        self,
        group_id: str,
        message_id: str,
        emoji: str | int,
        is_add: bool = True,
    ) -> bool:
        """设置或移除消息表情回应。"""
        ...

    def convert_to_raw_format(
        self, messages: list[UnifiedMessage]
    ) -> list[dict]:
        """将统一消息列表转换为平台原生字典结构。"""
        ...


@runtime_checkable
class GroupAlbumSupportProtocol(Protocol):
    """群相册上传与查询扩展能力协议。"""

    async def upload_group_album(
        self,
        group_id: str,
        image_path: str,
        album_id: str | None = None,
        album_name: str | None = None,
        strict_mode: bool = False,
    ) -> bool:
        """上传图片到群相册。"""
        ...

    async def find_album_id(
        self,
        group_id: str,
        album_name: str,
    ) -> str | None:
        """根据相册名称查找相册 ID。"""
        ...

    async def get_group_album_list(
        self,
        group_id: str,
    ) -> list[dict]:
        """获取群相册列表。"""
        ...


@runtime_checkable
class GroupFileSupportProtocol(Protocol):
    """群文件管理与上传扩展能力协议。"""

    async def upload_group_file_to_folder(
        self,
        group_id: str,
        file_path: str,
        filename: str | None = None,
        folder_id: str | None = None,
    ) -> bool:
        """上传文件到群文件指定文件夹。"""
        ...

    async def find_or_create_folder(
        self,
        group_id: str,
        folder_name: str,
    ) -> str | None:
        """查找或创建群文件子文件夹。"""
        ...

    async def create_group_file_folder(
        self,
        group_id: str,
        folder_name: str,
    ) -> str | None:
        """在群文件根目录下创建子文件夹。"""
        ...

    async def get_group_file_root_folders(
        self,
        group_id: str,
    ) -> list[dict]:
        """获取群文件根目录文件夹列表。"""
        ...
