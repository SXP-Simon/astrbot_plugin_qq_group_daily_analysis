"""
金句值对象 - 平台无关的金句表示

该值对象表示从群聊消息中提取的精彩语录。
它是不可变的，不包含任何平台特定的逻辑。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenQuote:
    """
    值对象：群聊金句

    表示分析过程中提取出的具有代表性、幽默或深刻的消息语录。

    Attributes:
        content (str): 语录原文
        sender (str): 说话者的显示名称
        reason (str): 入选理由（由 LLM 生成）
        user_id (str): 用户唯一 ID
    """

    content: str
    sender: str
    reason: str = ""
    user_id: str = ""

    def __post_init__(self):
        """初始化后确保 user_id 类型正确。"""
        if not isinstance(self.user_id, str):
            object.__setattr__(self, "user_id", str(self.user_id))

    @classmethod
    def from_dict(cls, data: dict) -> "GoldenQuote":
        """从持久化字典构建金句对象。"""
        user_id = data.get("user_id", "")

        return cls(
            content=data.get("content", "").strip(),
            sender=data.get("sender", "").strip(),
            reason=data.get("reason", "").strip(),
            user_id=str(user_id) if user_id else "",
        )

    def to_dict(self) -> dict:
        """转换为持久化字典。"""
        return {
            "content": self.content,
            "sender": self.sender,
            "reason": self.reason,
            "user_id": self.user_id,
        }

    @property
    def is_valid(self) -> bool:
        """验证金句数据的完整性。"""
        return bool(self.content.strip() and self.sender.strip())

    def with_user_id(self, user_id: str) -> "GoldenQuote":
        """拷贝并更新用户 ID，返回新实例。"""
        return GoldenQuote(
            content=self.content,
            sender=self.sender,
            reason=self.reason,
            user_id=str(user_id),
        )


@dataclass
class GoldenQuoteCollection:
    """
    模型：金句容器

    提供对金句列表的高级操作封装。
    """

    quotes: list[GoldenQuote] = field(default_factory=list)

    def add(self, quote: GoldenQuote) -> None:
        """添加单个金句，执行有效性检查。"""
        if quote.is_valid:
            self.quotes.append(quote)

    def add_from_dict(self, data: dict) -> None:
        """从原始数据添加金句。"""
        self.add(GoldenQuote.from_dict(data))

    def to_list(self) -> list[dict]:
        """导出为字典列表。"""
        return [q.to_dict() for q in self.quotes]

    def __len__(self) -> int:
        return len(self.quotes)

    def __iter__(self):
        return iter(self.quotes)
