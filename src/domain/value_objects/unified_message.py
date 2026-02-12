"""
统一消息值对象 - 跨平台核心抽象

所有平台消息都转换为此格式进行分析。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MessageContentType(Enum):
    """
    枚举：消息内容类型

    用于标识 MessageContent 的具体类型。
    """

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
    值对象：消息内容段

    表示消息链中的一个组成部分（如文本、图片、表情等）。
    该对象是不可变的，用于保证数据流的纯净。

    Attributes:
        type (MessageContentType): 内容类型
        text (str): 文本内容（仅当类型为 TEXT 或包含文本描述时）
        url (str): 资源链接（图片、视频、文件等）
        emoji_id (str): 表情 ID
        emoji_name (str): 表情名称
        at_user_id (str): 被 @ 的用户 ID
        raw_data (Any): 平台原始数据，用于扩展
    """

    type: MessageContentType
    text: str = ""
    url: str = ""
    emoji_id: str = ""
    emoji_name: str = ""
    at_user_id: str = ""
    raw_data: Any = None

    def is_text(self) -> bool:
        """检查是否为文本内容。"""
        return self.type == MessageContentType.TEXT

    def is_emoji(self) -> bool:
        """检查是否为表情内容。"""
        return self.type == MessageContentType.EMOJI

    @property
    def target_id(self) -> str:
        """
        获取被 @ 的用户 ID（兼容旧代码）。

        Alias for at_user_id.
        """
        return self.at_user_id


@dataclass(frozen=True)
class UnifiedMessage:
    """
    核心值对象：统一消息格式

    跨平台抽象层，将不同平台的原始消息转换为统一格式进行分析。
    采用“只读”设计，确保分析逻辑的一致性。

    Attributes:
        message_id (str): 消息唯一标识符
        sender_id (str): 发送者唯一 ID
        sender_name (str): 发送者昵称
        group_id (str): 群组/会话唯一 ID
        text_content (str): 经过清洗后的纯文本内容，主要用于 LLM 分析
        contents (tuple[MessageContent, ...]): 结构化消息链
        timestamp (int): Unix 时间戳（秒）
        platform (str): 来源平台名称（如 onebot, discord 等）
        reply_to_id (str, optional): 被回复的消息 ID
        sender_card (str, optional): 平台特定的群名片或特别备注
    """

    # 基础标识
    message_id: str
    sender_id: str
    sender_name: str
    group_id: str

    # 消息内容
    text_content: str
    contents: tuple[MessageContent, ...] = field(default_factory=tuple)

    # 时间信息
    timestamp: int = 0

    # 平台信息
    platform: str = "unknown"

    # 可选信息
    reply_to_id: str | None = None
    sender_card: str | None = None

    # 分析辅助方法
    def has_text(self) -> bool:
        """
        判断消息是否包含非空文本。

        Returns:
            bool: 包含有效文本则返回 True
        """
        return bool(self.text_content.strip())

    def get_display_name(self) -> str:
        """
        获取用户显示名称。
        优先级：群名片 > 昵称 > 用户 ID。

        Returns:
            str: 格式化后的显示名称
        """
        return self.sender_card or self.sender_name or self.sender_id

    def get_emoji_count(self) -> int:
        """
        计算消息链中包含的表情数量。

        Returns:
            int: 表情总数
        """
        return sum(1 for c in self.contents if c.is_emoji())

    def get_text_length(self) -> int:
        """
        获取文本内容的字符长度。

        Returns:
            int: 字符数
        """
        return len(self.text_content)

    def get_datetime(self) -> datetime:
        """
        将 Unix 时间戳转换为 datetime 对象。

        Returns:
            datetime: 本地化后的时间对象
        """
        return datetime.fromtimestamp(self.timestamp)

    def to_analysis_format(self) -> str:
        """
        转换为供 LLM 消费的分析格式。

        Returns:
            str: 格式如 "[用户名]: 消息内容" 的字符串
        """
        name = self.get_display_name()
        return f"[{name}]: {self.text_content}"


# 类型别名
MessageList = list[UnifiedMessage]
