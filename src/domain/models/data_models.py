"""
数据模型定义
包含所有分析相关的数据结构
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SummaryTopic:
    """话题总结数据结构"""

    topic: str
    contributors: list[str]
    detail: str
    contributor_ids: list[str] = field(
        default_factory=list
    )  # 贡献者ID列表 (用于显示头像)

    def is_valid(self) -> bool:
        """检查话题模型是否有效"""
        return bool(self.topic and self.topic.strip())

    def add_contributor(self, name: str, user_id: str = "") -> None:
        """安全添加贡献者并去重"""
        name = name.strip()
        if name and name not in self.contributors:
            self.contributors.append(name)
        user_id = str(user_id).strip()
        if user_id and user_id not in self.contributor_ids:
            self.contributor_ids.append(user_id)


@dataclass
class UserTitle:
    """用户称号数据结构"""

    name: str
    user_id: str  # 原 qq 字段
    title: str
    mbti: str
    reason: str

    def is_valid(self) -> bool:
        """检查用户称号模型是否有效"""
        return bool(self.user_id and self.name and self.title)


@dataclass
class GoldenQuote:
    """群聊金句数据结构"""

    content: str
    sender: str
    reason: str
    user_id: str = ""  # 原 qq 字段

    def is_valid(self) -> bool:
        """检查金句是否有效"""
        return bool(self.content and self.content.strip())


@dataclass
class QualityDimension:
    """聊天质量维度数据结构"""

    name: str  # 维度名称
    percentage: float  # 占比
    comment: str  # 犀利点评
    color: str = "#607d8b"  # 颜色

    def is_valid(self) -> bool:
        """检查维度是否有效"""
        return bool(self.name and 0.0 <= self.percentage <= 100.0)


@dataclass
class QualityReview:
    """聊天质量锐评数据结构"""

    title: str
    subtitle: str
    dimensions: list[QualityDimension]
    summary: str

    def is_valid(self) -> bool:
        """检查锐评整体是否合法"""
        return bool(self.title and self.dimensions)

    def normalize(self) -> None:
        """将各维度占比归一化到 100% 范围之内"""
        total = sum(d.percentage for d in self.dimensions)
        if total > 0 and abs(total - 100.0) > 0.01:
            for d in self.dimensions:
                d.percentage = round((d.percentage / total) * 100.0, 1)


@dataclass
class TokenUsage:
    """Token使用统计"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class EmojiStatistics:
    """表情统计数据结构"""

    face_count: int = 0  # QQ基础表情数量
    mface_count: int = 0  # 动画表情数量
    bface_count: int = 0  # 超级表情数量
    sface_count: int = 0  # 小表情数量
    other_emoji_count: int = 0  # 其他表情数量
    face_details: dict = field(default_factory=dict)  # 具体表情ID统计 {face_id: count}

    @property
    def total_emoji_count(self) -> int:
        """总表情数量"""
        return (
            self.face_count
            + self.mface_count
            + self.bface_count
            + self.sface_count
            + self.other_emoji_count
        )


@dataclass
class ActivityVisualization:
    """活跃度可视化数据结构"""

    hourly_activity: dict = field(default_factory=dict)  # {hour: count}
    daily_activity: dict = field(default_factory=dict)  # {date: count}
    user_activity_ranking: list = field(default_factory=list)  # 用户活跃度排行
    peak_hours: list = field(default_factory=list)  # 高峰时段
    activity_heatmap_data: dict = field(default_factory=dict)  # 热力图数据


@dataclass
class GroupStatistics:
    """群聊统计数据结构"""

    message_count: int
    total_characters: int
    participant_count: int
    most_active_period: str
    golden_quotes: list[GoldenQuote]
    emoji_count: int  # 保持向后兼容
    emoji_statistics: EmojiStatistics = field(default_factory=EmojiStatistics)
    activity_visualization: ActivityVisualization = field(
        default_factory=ActivityVisualization
    )
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    chat_quality_review: Optional["QualityReview"] = None
