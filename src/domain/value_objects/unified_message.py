"""
Unified Message Value Object - Cross-platform core abstraction

All platform messages are converted to this format for analysis.
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Tuple
from enum import Enum
from datetime import datetime


class MessageContentType(Enum):
    """Message content type enumeration"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    EMOJI = "emoji"
    REPLY = "reply"
    FORWARD = "forward"
    AT = "at"
    VOICE = "voice"
    VIDEO = "video"
    LOCATION = "location"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MessageContent:
    """
    Message content segment value object
    
    Immutable, used to compose message chains
    """
    type: MessageContentType
    text: str = ""
    url: str = ""
    emoji_id: str = ""
    emoji_name: str = ""
    at_user_id: str = ""
    raw_data: Any = None

    def is_text(self) -> bool:
        return self.type == MessageContentType.TEXT

    def is_emoji(self) -> bool:
        return self.type == MessageContentType.EMOJI


@dataclass(frozen=True)
class UnifiedMessage:
    """
    Unified message format - Cross-platform core value object
    
    Design principles:
    1. Only keep fields needed for analysis
    2. Use platform-agnostic types
    3. Immutable (frozen=True) - thread-safe
    4. All IDs are strings - avoid platform differences
    """
    # Basic identification
    message_id: str
    sender_id: str
    sender_name: str
    group_id: str
    
    # Message content
    text_content: str  # Extracted plain text for LLM analysis
    contents: Tuple[MessageContent, ...] = field(default_factory=tuple)
    
    # Time information
    timestamp: int = 0  # Unix timestamp
    
    # Platform information
    platform: str = "unknown"
    
    # Optional information
    reply_to_id: Optional[str] = None
    sender_card: Optional[str] = None  # Group card/nickname
    
    # Analysis helper methods
    def has_text(self) -> bool:
        """Whether has text content"""
        return bool(self.text_content.strip())

    def get_display_name(self) -> str:
        """Get display name, prefer group card"""
        return self.sender_card or self.sender_name or self.sender_id

    def get_emoji_count(self) -> int:
        """Get emoji count"""
        return sum(1 for c in self.contents if c.is_emoji())

    def get_text_length(self) -> int:
        """Get text length"""
        return len(self.text_content)

    def get_datetime(self) -> datetime:
        """Get message datetime"""
        return datetime.fromtimestamp(self.timestamp)

    def to_analysis_format(self) -> str:
        """Convert to analysis format (for LLM)"""
        name = self.get_display_name()
        return f"[{name}]: {self.text_content}"


# Type alias
MessageList = list[UnifiedMessage]
