"""
群聊分析结果值对象 (Analysis Result Value Objects)

定义每日群聊分析、质量锐评、话题提取与发言统计产生的不可变值对象。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SummaryTopic:
    """话题总结值对象。

    Attributes:
        topic: 话题名称。
        contributors: 贡献者昵称列表。
        detail: 话题讨论详情概要。
        contributor_ids: 贡献者用户 ID 列表（用于多模态头像渲染）。
    """

    topic: str
    contributors: list[str]
    detail: str
    contributor_ids: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """检查话题值对象是否有效。

        Returns:
            bool: 话题名称非空时返回 True。
        """
        return bool(self.topic and self.topic.strip())

    def add_contributor(self, name: str, user_id: str = "") -> None:
        """安全添加贡献者并去重。

        Args:
            name: 贡献者昵称。
            user_id: 贡献者用户唯一标识。
        """
        name = name.strip()
        if name and name not in self.contributors:
            self.contributors.append(name)
        user_id = str(user_id).strip()
        if user_id and user_id not in self.contributor_ids:
            self.contributor_ids.append(user_id)


@dataclass
class UserTitle:
    """用户称号与人格画像值对象。

    Attributes:
        name: 用户群昵称。
        user_id: 用户唯一标识 ID（如 QQ 号/Telegram 用户 ID）。
        title: LLM 评定的个性化头衔。
        mbti: MBTI 人格类型代码。
        reason: 头衔与人格评定理由。
    """

    name: str
    user_id: str
    title: str
    mbti: str
    reason: str

    def is_valid(self) -> bool:
        """检查用户称号值对象是否有效。

        Returns:
            bool: 标识、昵称和头衔均非空时返回 True。
        """
        return bool(self.user_id and self.name and self.title)


@dataclass
class GoldenQuote:
    """群聊精选金句值对象。

    Attributes:
        content: 金句发言内容。
        sender: 发言者昵称。
        reason: 入选理由/幽默点评。
        user_id: 发言者用户 ID。
    """

    content: str
    sender: str
    reason: str
    user_id: str = ""

    def is_valid(self) -> bool:
        """检查金句是否有效。

        Returns:
            bool: 金句内容非空时返回 True。
        """
        return bool(self.content and self.content.strip())


@dataclass
class QualityDimension:
    """聊天质量维度评分值对象。

    Attributes:
        name: 质量维度名称（如水群指数、干货浓度）。
        percentage: 百分比占比 (0.0~100.0)。
        comment: 犀利点评。
        color: 渲染颜色色值。
    """

    name: str
    percentage: float
    comment: str
    color: str = "#607d8b"

    def is_valid(self) -> bool:
        """检查维度评分是否有效。

        Returns:
            bool: 维度名非空且占比在 0~100 范围内返回 True。
        """
        return bool(self.name and 0.0 <= self.percentage <= 100.0)


@dataclass
class QualityReview:
    """聊天质量整体锐评值对象。

    Attributes:
        title: 锐评主标题。
        subtitle: 锐评副标题。
        dimensions: 质量多维度评分列表。
        summary: 总结点评段落。
    """

    title: str
    subtitle: str
    dimensions: list[QualityDimension]
    summary: str

    def is_valid(self) -> bool:
        """检查锐评整体是否合法。

        Returns:
            bool: 主标题与维度列表非空时返回 True。
        """
        return bool(self.title and self.dimensions)

    def normalize(self) -> None:
        """将各维度占比归一化到 100% 范围之内。"""
        total = sum(d.percentage for d in self.dimensions)
        if total > 0 and abs(total - 100.0) > 0.01:
            for d in self.dimensions:
                d.percentage = round((d.percentage / total) * 100.0, 1)


@dataclass
class TokenUsage:
    """LLM Token 消耗统计值对象。

    Attributes:
        prompt_tokens: 提示词 Token 数。
        completion_tokens: 生成补全 Token 数。
        total_tokens: 总计消耗 Token 数。
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class EmojiStatistics:
    """群聊表情包与 Face 使用统计值对象。

    Attributes:
        face_count: 平台基础表情数量。
        mface_count: 动画表情数量。
        bface_count: 大表情/超级表情数量。
        sface_count: 小表情数量。
        other_emoji_count: 其他自定义表情数量。
        face_details: 表情 ID 详细分布字典 {face_id: count}。
    """

    face_count: int = 0
    mface_count: int = 0
    bface_count: int = 0
    sface_count: int = 0
    other_emoji_count: int = 0
    face_details: dict = field(default_factory=dict)

    @property
    def total_emoji_count(self) -> int:
        """计算表情总数量。

        Returns:
            int: 所有分类表情的总和。
        """
        return (
            self.face_count
            + self.mface_count
            + self.bface_count
            + self.sface_count
            + self.other_emoji_count
        )


@dataclass
class ActivityVisualization:
    """群活跃度时序与热力图数据值对象。

    Attributes:
        hourly_activity: 按小时统计的发言量分布 {hour: count}。
        daily_activity: 按日期统计的发言量分布 {date: count}。
        user_activity_ranking: 用户发言榜单数据列表。
        peak_hours: 发言高峰时段列表。
        activity_heatmap_data: 24x7 活跃度热力图矩阵数据。
    """

    hourly_activity: dict = field(default_factory=dict)
    daily_activity: dict = field(default_factory=dict)
    user_activity_ranking: list = field(default_factory=list)
    peak_hours: list = field(default_factory=list)
    activity_heatmap_data: dict = field(default_factory=dict)


@dataclass
class GroupStatistics:
    """群聊每日统计汇总数据聚合值对象。

    Attributes:
        message_count: 总消息数。
        total_characters: 总字符数。
        participant_count: 参与发言人数。
        most_active_period: 最活跃时段描述。
        golden_quotes: 精选金句列表。
        emoji_count: 表情总计数（向后兼容）。
        emoji_statistics: 详细表情统计值对象。
        activity_visualization: 活跃度时序与图表数据值对象。
        token_usage: 本次分析消耗的 Token 统计值对象。
        chat_quality_review: 聊天质量锐评值对象（可选）。
    """

    message_count: int
    total_characters: int
    participant_count: int
    most_active_period: str
    golden_quotes: list[GoldenQuote]
    emoji_count: int
    emoji_statistics: EmojiStatistics = field(default_factory=EmojiStatistics)
    activity_visualization: ActivityVisualization = field(
        default_factory=ActivityVisualization
    )
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    chat_quality_review: QualityReview | None = None
