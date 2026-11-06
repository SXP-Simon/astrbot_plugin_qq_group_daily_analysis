"""
统一消息值对象 - 跨平台核心抽象

所有平台消息都转换为此格式进行分析。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TypedDict

from ...shared.type_guards import is_string_mapping


class AnalysisTextMessage(TypedDict):
    """交给提示词构建器的文本消息。"""

    time: str
    sender: str
    content: str
    user_id: str


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
    字段禁止重新赋值；raw_data 可能包含可变容器，仅供接入和兼容读取，
    不保证深度不可变，业务处理不得原地修改它。

    Attributes:
        type (MessageContentType): 内容类型
        text (str): 文本内容（仅当类型为 TEXT 或包含文本描述时）
        url (str): 资源链接（图片、视频、文件等）
        emoji_id (str): 表情 ID
        emoji_name (str): 表情名称
        at_user_id (str): 被 @ 的用户 ID
        raw_data (object): 平台转换及旧快照兼容所需的原始数据，读取前检查类型
    """

    type: MessageContentType
    text: str = ""
    url: str = ""
    emoji_id: str = ""
    emoji_name: str = ""
    at_user_id: str = ""
    raw_data: object = None

    def is_emoji(self) -> bool:
        """识别统一表情及旧快照中以图片保存的表情。

        Returns:
            是否应计入表情统计；明确的图片子类型优先于摘要文本。
        """
        if self.type == MessageContentType.EMOJI:
            return True
        if self.type != MessageContentType.IMAGE:
            return False
        if is_string_mapping(self.raw_data):
            sub_type = self.raw_data.get("sub_type")
            if sub_type is not None:
                return str(sub_type) == "1"
            summary = str(self.raw_data.get("summary", ""))
        else:
            summary = str(self.raw_data or "")
        return "动画表情" in summary or "表情" in summary


@dataclass(frozen=True)
class UnifiedMessage:
    """
    核心值对象：统一消息格式

    跨平台抽象层，将不同平台的原始消息转换为统一格式进行分析。
    采用“只读”设计，确保分析逻辑的一致性。

    Attributes:
        message_id (str): 来源会话内的消息标识，不保证跨平台全局唯一
        sender_id (str): 发送者唯一 ID
        sender_name (str): 发送者昵称
        group_id (str): 群组/会话唯一 ID
        text_content (str): 当前阶段的纯文本；适配器提取，清洗服务同步更新
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
    def get_display_name(self, *, use_card: bool = True) -> str:
        """
        获取用户显示名称。
        默认优先群名片；关闭名片优先时先用昵称，最后回退到用户 ID。

        Args:
            use_card: 是否优先使用群名片。

        Returns:
            str: 格式化后的显示名称
        """
        if use_card:
            return self.sender_card or self.sender_name or self.sender_id
        return self.sender_name or self.sender_card or self.sender_id

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
