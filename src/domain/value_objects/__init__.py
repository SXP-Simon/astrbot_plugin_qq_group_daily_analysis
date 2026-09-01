# 值对象
from .platform_capabilities import PLATFORM_CAPABILITIES, PlatformCapabilities
from .unified_group import UnifiedGroup, UnifiedMember
from .unified_message import MessageContent, MessageContentType, UnifiedMessage

__all__ = [
    # 核心平台抽象
    "UnifiedMessage",
    "MessageContent",
    "MessageContentType",
    "PlatformCapabilities",
    "PLATFORM_CAPABILITIES",
    "UnifiedGroup",
    "UnifiedMember",
]
