"""
用户称号值对象 - 平台无关的用户称号表示

该值对象表示基于聊天行为分析分配给用户的称号/徽章。
它是不可变的，不包含任何平台特定的逻辑。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UserTitle:
    """
    值对象：用户称号/勋章

    Attributes:
        name (str): 用户昵称
        user_id (str): 用户唯一 ID
        title (str): 获得的称号名称
        mbti (str): 评估出的 MBTI 类型
        reason (str): 授予该称号的理由
    """

    name: str
    user_id: str
    title: str
    mbti: str = ""
    reason: str = ""

    def __post_init__(self):
        """确保 ID 为字符串。"""
        if not isinstance(self.user_id, str):
            object.__setattr__(self, "user_id", str(self.user_id))

    @classmethod
    def from_dict(cls, data: dict) -> "UserTitle":
        """解析持久化字典。"""
        user_id = data.get("user_id", "")

        return cls(
            name=data.get("name", "").strip(),
            user_id=str(user_id),
            title=data.get("title", "").strip(),
            mbti=data.get("mbti", "").strip().upper(),
            reason=data.get("reason", "").strip(),
        )

    def to_dict(self) -> dict:
        """导出字典。"""
        return {
            "name": self.name,
            "user_id": self.user_id,
            "title": self.title,
            "mbti": self.mbti,
            "reason": self.reason,
        }

    @property
    def is_valid(self) -> bool:
        """基本数据完整性验证。"""
        return bool(self.name.strip() and self.title.strip() and self.user_id)


@dataclass
class UserTitleCollection:
    """
    模型：称号容器

    Attributes:
        titles (list[UserTitle]): 称号列表
    """

    titles: list[UserTitle] = field(default_factory=list)

    def add(self, title: UserTitle) -> None:
        """添加称号。"""
        if title.is_valid:
            self.titles.append(title)

    def add_from_dict(self, data: dict) -> None:
        """解析并添加。"""
        self.add(UserTitle.from_dict(data))

    def get_by_user_id(self, user_id: str) -> UserTitle | None:
        """根据唯一 ID 检索称号。"""
        user_id_str = str(user_id)
        for title in self.titles:
            if title.user_id == user_id_str:
                return title
        return None

    def to_list(self) -> list[dict]:
        """导出映射列表。"""
        return [t.to_dict() for t in self.titles]

    def __len__(self) -> int:
        return len(self.titles)

    def __iter__(self):
        return iter(self.titles)
