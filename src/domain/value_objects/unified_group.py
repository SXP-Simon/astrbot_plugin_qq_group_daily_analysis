"""
统一群组值对象 - 跨平台群组抽象
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UnifiedMember:
    """统一成员信息"""
    user_id: str
    nickname: str
    card: Optional[str] = None  # 群名片
    role: str = "member"  # owner, admin, member
    join_time: Optional[int] = None
    avatar_url: Optional[str] = None
    avatar_data: Optional[str] = None  # Base64 用于模板渲染


@dataclass(frozen=True)
class UnifiedGroup:
    """统一群组信息"""
    group_id: str
    group_name: str
    member_count: int = 0
    owner_id: Optional[str] = None
    create_time: Optional[int] = None
    description: Optional[str] = None
    platform: str = "unknown"
