"""
统一群组值对象 - 跨平台群组抽象
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnifiedMember:
    """统一成员信息"""

    user_id: str
    nickname: str
    card: str | None = None  # 群名片
    role: str = "member"  # owner, admin, member
    join_time: int | None = None
    avatar_url: str | None = None
    avatar_data: str | None = None  # Base64 用于模板渲染


@dataclass(frozen=True)
class UnifiedGroup:
    """统一群组信息"""

    group_id: str
    group_name: str
    member_count: int = 0
    owner_id: str | None = None
    create_time: int | None = None
    description: str | None = None
    platform: str = "unknown"
