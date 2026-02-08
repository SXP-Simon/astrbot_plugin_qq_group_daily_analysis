"""
Unified Group Value Objects - Cross-platform group abstraction
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UnifiedMember:
    """Unified member information"""
    user_id: str
    nickname: str
    card: Optional[str] = None  # Group card
    role: str = "member"  # owner, admin, member
    join_time: Optional[int] = None
    avatar_url: Optional[str] = None
    avatar_data: Optional[str] = None  # Base64 for template rendering

    def get_display_name(self) -> str:
        return self.card or self.nickname or self.user_id


@dataclass(frozen=True)
class UnifiedGroup:
    """Unified group information"""
    group_id: str
    group_name: str
    member_count: int = 0
    owner_id: Optional[str] = None
    create_time: Optional[int] = None
    description: Optional[str] = None
    platform: str = "unknown"
