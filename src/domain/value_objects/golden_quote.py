"""
金句值对象 - 平台无关的金句表示

该值对象表示从群聊消息中提取的精彩语录。
它是不可变的，不包含任何平台特定的逻辑。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GoldenQuote:
    """
    群聊分析的金句值对象。

    表示聊天中令人难忘/有趣的语录。
    设计上不可变 (frozen=True)。

    属性:
        content: 实际的语录内容
        sender: 发言者的显示名称
        reason: 该语录被选为金句的原因
        user_id: 平台无关的用户标识符（存储为字符串）
    """

    content: str
    sender: str
    reason: str = ""
    user_id: str = ""

    def __post_init__(self):
        """初始化后验证和规范化金句数据。"""
        # 确保 user_id 始终是字符串
        if not isinstance(self.user_id, str):
            object.__setattr__(self, "user_id", str(self.user_id))

    @classmethod
    def from_dict(cls, data: dict) -> "GoldenQuote":
        """
        从字典数据创建 GoldenQuote。

        参数:
            data: 包含金句数据的字典

        返回:
            GoldenQuote 实例
        """
        # 同时处理 'qq' 和 'user_id' 键以保持向后兼容
        user_id = data.get("user_id", data.get("qq", ""))

        return cls(
            content=data.get("content", "").strip(),
            sender=data.get("sender", "").strip(),
            reason=data.get("reason", "").strip(),
            user_id=str(user_id) if user_id else "",
        )

    def to_dict(self) -> dict:
        """
        将 GoldenQuote 转换为字典。

        返回:
            字典表示
        """
        return {
            "content": self.content,
            "sender": self.sender,
            "reason": self.reason,
            "user_id": self.user_id,
            "qq": int(self.user_id) if self.user_id.isdigit() else 0,  # 向后兼容
        }

    @property
    def is_valid(self) -> bool:
        """检查金句是否有有效数据。"""
        return bool(
            self.content
            and self.content.strip()
            and self.sender
            and self.sender.strip()
        )

    @property
    def qq(self) -> int:
        """获取 QQ 号码以保持向后兼容。"""
        try:
            return int(self.user_id)
        except (ValueError, TypeError):
            return 0

    def with_user_id(self, user_id: str) -> "GoldenQuote":
        """
        创建一个更新了 user_id 的新 GoldenQuote。

        由于 GoldenQuote 是冻结的，需要创建新实例。

        参数:
            user_id: 要设置的用户 ID

        返回:
            更新了 user_id 的新 GoldenQuote 实例
        """
        return GoldenQuote(
            content=self.content,
            sender=self.sender,
            reason=self.reason,
            user_id=str(user_id),
        )


@dataclass
class GoldenQuoteCollection:
    """
    带有实用方法的金句集合。

    这是可变的，以便逐步构建语录集合。
    """

    quotes: list[GoldenQuote] = field(default_factory=list)

    def add(self, quote: GoldenQuote) -> None:
        """添加金句到集合。"""
        if quote.is_valid:
            self.quotes.append(quote)

    def add_from_dict(self, data: dict) -> None:
        """从字典数据添加金句。"""
        quote = GoldenQuote.from_dict(data)
        self.add(quote)

    def to_list(self) -> list[dict]:
        """将所有语录转换为字典列表。"""
        return [q.to_dict() for q in self.quotes]

    def __len__(self) -> int:
        return len(self.quotes)

    def __iter__(self):
        return iter(self.quotes)
