"""
统一消息值对象 - 跨平台核心抽象

所有平台消息都转换为此格式进行分析。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MessageContentType(Enum):
    """消息内容类型枚举"""

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
    消息内容段值对象

    不可变，用于组成消息链
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
    统一消息格式 - 跨平台核心值对象

    设计原则：
    1. 只保留分析所需的字段
    2. 使用平台无关的类型
    3. 不可变 (frozen=True) - 线程安全
    4. 所有 ID 使用字符串 - 避免平台差异
    """

    # 基础标识
    message_id: str
    sender_id: str
    sender_name: str
    group_id: str

    # 消息内容
    text_content: str  # 提取的纯文本用于 LLM 分析
    contents: tuple[MessageContent, ...] = field(default_factory=tuple)

    # 时间信息
    timestamp: int = 0  # Unix 时间戳

    # 平台信息
    platform: str = "unknown"

    # 可选信息
    reply_to_id: str | None = None
    sender_card: str | None = None  # 群名片/昵称

    # 分析辅助方法
    def has_text(self) -> bool:
        """是否有文本内容"""
        return bool(self.text_content.strip())

    def get_display_name(self) -> str:
        """获取显示名称，优先使用群名片"""
        return self.sender_card or self.sender_name or self.sender_id

    def get_emoji_count(self) -> int:
        """获取表情数量"""
        return sum(1 for c in self.contents if c.is_emoji())

    def get_text_length(self) -> int:
        """获取文本长度"""
        return len(self.text_content)

    def get_datetime(self) -> datetime:
        """获取消息时间"""
        return datetime.fromtimestamp(self.timestamp)

    def to_analysis_format(self) -> str:
        """转换为分析格式（供 LLM 使用）"""
        name = self.get_display_name()
        return f"[{name}]: {self.text_content}"


# 类型别名
MessageList = list[UnifiedMessage]
