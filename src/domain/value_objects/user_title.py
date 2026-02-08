"""
用户称号值对象 - 平台无关的用户称号表示

该值对象表示基于聊天行为分析分配给用户的称号/徽章。
它是不可变的，不包含任何平台特定的逻辑。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UserTitle:
    """
    群聊分析的用户称号值对象。

    表示基于用户行为分配的称号/徽章。
    设计上不可变 (frozen=True)。

    属性:
        name: 用户显示名称
        user_id: 平台无关的用户标识符（存储为字符串）
        title: 分配给用户的称号/徽章
        mbti: MBTI 人格类型评估
        reason: 分配该称号的原因说明
    """

    name: str
    user_id: str
    title: str
    mbti: str = ""
    reason: str = ""

    def __post_init__(self):
        """初始化后验证和规范化用户称号数据。"""
        # 确保 user_id 始终是字符串
        if not isinstance(self.user_id, str):
            object.__setattr__(self, "user_id", str(self.user_id))

    @classmethod
    def from_dict(cls, data: dict) -> "UserTitle":
        """
        从字典数据创建 UserTitle。

        参数:
            data: 包含用户称号数据的字典

        返回:
            UserTitle 实例
        """
        # 同时处理 'qq' 和 'user_id' 键以保持向后兼容
        user_id = data.get("user_id", data.get("qq", ""))

        return cls(
            name=data.get("name", "").strip(),
            user_id=str(user_id),
            title=data.get("title", "").strip(),
            mbti=data.get("mbti", "").strip().upper(),
            reason=data.get("reason", "").strip(),
        )

    def to_dict(self) -> dict:
        """
        将 UserTitle 转换为字典。

        返回:
            字典表示
        """
        return {
            "name": self.name,
            "user_id": self.user_id,
            "qq": int(self.user_id) if self.user_id.isdigit() else 0,  # 向后兼容
            "title": self.title,
            "mbti": self.mbti,
            "reason": self.reason,
        }

    @property
    def is_valid(self) -> bool:
        """检查用户称号是否有有效数据。"""
        return bool(
            self.name
            and self.name.strip()
            and self.title
            and self.title.strip()
            and self.user_id
        )

    @property
    def qq(self) -> int:
        """获取 QQ 号码以保持向后兼容。"""
        try:
            return int(self.user_id)
        except (ValueError, TypeError):
            return 0


@dataclass
class UserTitleCollection:
    """
    带有实用方法的用户称号集合。

    这是可变的，以便逐步构建称号集合。
    """

    titles: list[UserTitle] = field(default_factory=list)

    def add(self, title: UserTitle) -> None:
        """添加用户称号到集合。"""
        if title.is_valid:
            self.titles.append(title)

    def add_from_dict(self, data: dict) -> None:
        """从字典数据添加用户称号。"""
        title = UserTitle.from_dict(data)
        self.add(title)

    def get_by_user_id(self, user_id: str) -> UserTitle | None:
        """根据用户 ID 获取称号。"""
        user_id_str = str(user_id)
        for title in self.titles:
            if title.user_id == user_id_str:
                return title
        return None

    def to_list(self) -> list[dict]:
        """将所有称号转换为字典列表。"""
        return [t.to_dict() for t in self.titles]

    def __len__(self) -> int:
        return len(self.titles)

    def __iter__(self):
        return iter(self.titles)
