"""
话题值对象 - 平台无关的话题表示

该值对象表示从群聊消息中提取的讨论话题。
它是不可变的，不包含任何平台特定的逻辑。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Topic:
    """
    值对象：讨论话题

    表示从聊天记录中总结出的一个核心讨论点。

    Attributes:
        name (str): 话题名称
        contributors (tuple[str, ...]): 核心贡献者列表（不可变）
        detail (str): 话题详情摘要
    """

    name: str
    contributors: tuple[str, ...] = field(default_factory=tuple)
    detail: str = ""

    def __post_init__(self):
        """数据规范化。"""
        if not self.name or not self.name.strip():
            object.__setattr__(self, "name", "未知话题")

        if isinstance(self.contributors, list):
            object.__setattr__(self, "contributors", tuple(self.contributors))

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        """从字典还原话题对象。"""
        contributors = data.get("contributors", [])
        if isinstance(contributors, list):
            contributors = tuple(contributors)

        return cls(
            name=data.get("topic", data.get("name", "")).strip(),
            contributors=contributors,
            detail=data.get("detail", "").strip(),
        )

    def to_dict(self) -> dict:
        """导出为序列化字典。"""
        return {
            "topic": self.name,
            "contributors": list(self.contributors),
            "detail": self.detail,
        }

    @property
    def contributor_count(self) -> int:
        """参与讨论的人数。"""
        return len(self.contributors)

    @property
    def is_valid(self) -> bool:
        """验证话题数据的有效性。"""
        return bool(self.name.strip() and self.detail.strip())


@dataclass
class TopicCollection:
    """
    模型：话题集合

    Attributes:
        topics (list[Topic]): 话题列表
    """

    topics: list[Topic] = field(default_factory=list)

    def add(self, topic: Topic) -> None:
        """添加话题并进行有效性检查。"""
        if topic.is_valid:
            self.topics.append(topic)

    def add_from_dict(self, data: dict) -> None:
        """从原始数据添加。"""
        self.add(Topic.from_dict(data))

    def to_list(self) -> list[dict]:
        """导出字典列表。"""
        return [t.to_dict() for t in self.topics]

    def __len__(self) -> int:
        return len(self.topics)

    def __iter__(self):
        return iter(self.topics)
