"""
Platform Capabilities Value Object - Runtime decision support

Each platform adapter declares its capabilities,
application layer decides operations based on capabilities.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlatformCapabilities:
    """
    Platform capability description
    
    Design principles:
    1. All fields have default values (most conservative assumption)
    2. Immutable
    3. Provide convenient check methods
    """
    # Platform identification
    platform_name: str
    platform_version: str = "unknown"
    
    # Message retrieval capabilities
    supports_message_history: bool = False
    max_message_history_days: int = 0
    max_message_count: int = 0
    supports_message_search: bool = False
    
    # Group info capabilities
    supports_group_list: bool = False
    supports_group_info: bool = False
    supports_member_list: bool = False
    supports_member_info: bool = False
    
    # Message sending capabilities
    supports_text_message: bool = True
    supports_image_message: bool = False
    supports_file_message: bool = False
    supports_forward_message: bool = False
    supports_reply_message: bool = False
    max_text_length: int = 4096
    max_image_size_mb: float = 10.0
    
    # Special capabilities
    supports_at_all: bool = False
    supports_recall: bool = False
    supports_edit: bool = False
    
    # Avatar capabilities
    supports_user_avatar: bool = True
    supports_group_avatar: bool = False
    avatar_needs_api_call: bool = False
    avatar_sizes: tuple = (100,)
    
    # Check methods
    def can_analyze(self) -> bool:
        """Whether supports group chat analysis (core capability)"""
        return (
            self.supports_message_history 
            and self.max_message_history_days > 0
            and self.max_message_count > 0
        )

    def can_send_report(self, format: str = "image") -> bool:
        """Whether can send report"""
        if format == "text":
            return self.supports_text_message
        elif format == "image":
            return self.supports_image_message
        elif format == "pdf":
            return self.supports_file_message
        return False

    def get_effective_days(self, requested_days: int) -> int:
        """Get actual available days"""
        return min(requested_days, self.max_message_history_days)

    def get_effective_count(self, requested_count: int) -> int:
        """Get actual available message count"""
        return min(requested_count, self.max_message_count)


# Predefined platform capabilities
ONEBOT_V11_CAPABILITIES = PlatformCapabilities(
    platform_name="onebot",
    platform_version="v11",
    supports_message_history=True,
    max_message_history_days=7,
    max_message_count=10000,
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    supports_member_info=True,
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_forward_message=True,
    supports_reply_message=True,
    max_text_length=4500,
    supports_at_all=True,
    supports_recall=True,
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=False,
    avatar_sizes=(40, 100, 140, 160, 640),
)

TELEGRAM_CAPABILITIES = PlatformCapabilities(
    platform_name="telegram",
    platform_version="bot_api_7.x",
    supports_message_history=False,
    max_message_history_days=0,
    max_message_count=0,
    supports_group_list=False,
    supports_group_info=True,
    supports_member_list=True,
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=4096,
    max_image_size_mb=50.0,
    supports_edit=True,
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=True,
    avatar_sizes=(160, 320, 640),
)

DISCORD_CAPABILITIES = PlatformCapabilities(
    platform_name="discord",
    platform_version="api_v10",
    supports_message_history=True,
    max_message_history_days=30,
    max_message_count=10000,
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=2000,
    max_image_size_mb=8.0,
    supports_edit=True,
    supports_user_avatar=True,
    supports_group_avatar=True,
    avatar_needs_api_call=False,
    avatar_sizes=(16, 32, 64, 128, 256, 512, 1024, 2048, 4096),
)

SLACK_CAPABILITIES = PlatformCapabilities(
    platform_name="slack",
    platform_version="web_api",
    supports_message_history=True,
    max_message_history_days=90,
    max_message_count=1000,
    supports_group_list=True,
    supports_group_info=True,
    supports_member_list=True,
    supports_text_message=True,
    supports_image_message=True,
    supports_file_message=True,
    supports_reply_message=True,
    max_text_length=40000,
    supports_edit=True,
    supports_user_avatar=True,
    supports_group_avatar=False,
    avatar_needs_api_call=True,
    avatar_sizes=(24, 32, 48, 72, 192, 512, 1024),
)

# Capability lookup table
PLATFORM_CAPABILITIES = {
    "aiocqhttp": ONEBOT_V11_CAPABILITIES,
    "onebot": ONEBOT_V11_CAPABILITIES,
    "telegram": TELEGRAM_CAPABILITIES,
    "discord": DISCORD_CAPABILITIES,
    "slack": SLACK_CAPABILITIES,
}


def get_capabilities(platform_name: str) -> Optional[PlatformCapabilities]:
    """Get capabilities by platform name"""
    return PLATFORM_CAPABILITIES.get(platform_name.lower())
