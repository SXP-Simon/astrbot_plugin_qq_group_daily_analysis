"""
群聊分析结果实体
"""

from dataclasses import dataclass, field
from typing import List, Optional
import uuid
import time


@dataclass
class SummaryTopic:
    """话题摘要"""
    topic: str
    contributors: List[str]
    detail: str


@dataclass
class UserTitle:
    """用户称号/画像"""
    name: str
    user_id: str
    title: str
    mbti: str
    reason: str
    avatar_url: Optional[str] = None
    avatar_data: Optional[str] = None


@dataclass
class GoldenQuote:
    """金句"""
    content: str
    sender: str
    reason: str
    user_id: str = ""
    avatar_url: Optional[str] = None


@dataclass
class TokenUsage:
    """令牌使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class EmojiStatistics:
    """表情统计"""
    face_count: int = 0
    mface_count: int = 0
    bface_count: int = 0
    sface_count: int = 0
    other_emoji_count: int = 0
    face_details: dict = field(default_factory=dict)

    @property
    def total_emoji_count(self) -> int:
        return (
            self.face_count
            + self.mface_count
            + self.bface_count
            + self.sface_count
            + self.other_emoji_count
        )


@dataclass
class ActivityVisualization:
    """活动可视化数据"""
    hourly_activity: dict = field(default_factory=dict)
    daily_activity: dict = field(default_factory=dict)
    user_activity_ranking: list = field(default_factory=list)
    peak_hours: list = field(default_factory=list)
    activity_heatmap_data: dict = field(default_factory=dict)


@dataclass
class GroupStatistics:
    """群组统计"""
    message_count: int = 0
    total_characters: int = 0
    participant_count: int = 0
    most_active_period: str = ""
    emoji_count: int = 0
    emoji_statistics: EmojiStatistics = field(default_factory=EmojiStatistics)
    activity_visualization: ActivityVisualization = field(default_factory=ActivityVisualization)


@dataclass
class GroupAnalysisResult:
    """群聊分析结果实体"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    group_id: str = ""
    group_name: str = ""
    trace_id: str = ""
    platform: str = ""
    
    # 分析结果
    message_count: int = 0
    statistics: GroupStatistics = field(default_factory=GroupStatistics)
    topics: List[SummaryTopic] = field(default_factory=list)
    user_titles: List[UserTitle] = field(default_factory=list)
    golden_quotes: List[GoldenQuote] = field(default_factory=list)
    
    # 元数据
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    analysis_date: str = ""
    created_at: float = field(default_factory=time.time)
    
    def has_content(self) -> bool:
        """检查结果是否有分析内容"""
        return bool(self.topics or self.user_titles or self.golden_quotes)
