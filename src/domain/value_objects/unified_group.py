"""
统一群组值对象 - 跨平台群组抽象
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnifiedMember:
    """
    值对象：统一成员信息

    Attributes:
        user_id (str): 用户唯一 ID
        nickname (str): 用户昵称
        card (str, optional): 群名片
        role (str): 角色（owner/admin/member）
        join_time (int, optional): 入群时间（秒级时间戳）
        avatar_url (str, optional): 头像网络链接
        avatar_data (str, optional): 头像 Base64 数据
    """

    user_id: str
    nickname: str
    card: str | None = None
    role: str = "member"
    join_time: int | None = None
    avatar_url: str | None = None
    avatar_data: str | None = None


@dataclass(frozen=True)
class UnifiedGroup:
    """
    值对象：统一群组信息

    Attributes:
        group_id (str): 群组唯一 ID
        group_name (str): 群组名称
        member_count (int): 成员数量
        owner_id (str, optional): 群主 ID
        create_time (int, optional): 创建时间
        description (str, optional): 群简介/公告
        platform (str): 来源平台
    """

    group_id: str
    group_name: str
    member_count: int = 0
    owner_id: str | None = None
    create_time: int | None = None
    description: str | None = None
    platform: str = "unknown"
