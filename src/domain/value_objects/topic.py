"""
话题值对象 - 平台无关的话题表示

该值对象表示从群聊消息中提取的讨论话题。
它是不可变的，不包含任何平台特定的逻辑。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Topic:
    """
    群聊分析的话题值对象。

    表示一个包含参与者和详情的讨论话题。
    设计上不可变 (frozen=True)。

    属性:
        name: 话题标题/名称
        contributors: 参与该话题讨论的用户名列表
        detail: 话题讨论的详细描述或摘要
    """

    name: str
    contributors: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""

    def __post_init__(self):
        """初始化后验证话题数据。"""
        if not self.name or not self.name.strip():
            object.__setattr__(self, "name", "未知话题")

        # 确保 contributors 是元组以保证不可变性
        if isinstance(self.contributors, list):
            object.__setattr__(self, "contributors", tuple(self.contributors))

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        """
        从字典数据创建 Topic。

        参数:
            data: 包含话题数据的字典

        返回:
            Topic 实例
        """
        contributors = data.get("contributors", [])
        if isinstance(contributors, list):
            contributors = tuple(contributors)

        return cls(
            name=data.get("topic", data.get("name", "")).strip(),
            contributors=contributors,
            detail=data.get("detail", "").strip(),
        )

    def to_dict(self) -> dict:
        """
        将 Topic 转换为字典。

        返回:
            字典表示
        """
        return {
            "topic": self.name,
            "contributors": list(self.contributors),
            "detail": self.detail,
        }

    @property
    def contributor_count(self) -> int:
        """获取参与者数量。"""
        return len(self.contributors)

    @property
    def is_valid(self) -> bool:
        """检查话题是否有有效数据。"""
        return bool(self.name and self.name.strip() and self.detail and self.detail.strip())


@dataclass
class TopicCollection:
    """
    带有实用方法的话题集合。

    这是可变的，以便逐步构建话题集合。
    """

    topics: List[Topic] = field(default_factory=list)

    def add(self, topic: Topic) -> None:
        """添加话题到集合。"""
        if topic.is_valid:
            self.topics.append(topic)

    def add_from_dict(self, data: dict) -> None:
        """从字典数据添加话题。"""
        topic = Topic.from_dict(data)
        self.add(topic)

    def to_list(self) -> List[dict]:
        """将所有话题转换为字典列表。"""
        return [t.to_dict() for t in self.topics]

    def __len__(self) -> int:
        return len(self.topics)

    def __iter__(self):
        return iter(self.topics)
