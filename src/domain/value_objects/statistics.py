"""
统计值对象 - 平台无关的统计数据表示

该模块包含群聊分析期间收集的各种统计数据的值对象。
所有对象都是不可变的和平台无关的。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenUsage:
    """
    LLM API 调用的令牌使用统计。

    设计上不可变 (frozen=True)。

    属性:
        prompt_tokens: 提示词中的令牌数
        completion_tokens: 补全中的令牌数
        total_tokens: 使用的总令牌数
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "TokenUsage":
        """从字典创建 TokenUsage。"""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """将两个 TokenUsage 对象相加。"""
        if not isinstance(other, TokenUsage):
            return NotImplemented
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass(frozen=True)
class EmojiStatistics:
    """
    表情使用统计。

    消息中表情使用的平台无关表示。
    设计上不可变 (frozen=True)。

    属性:
        standard_emoji_count: 标准 Unicode 表情数量
        custom_emoji_count: 平台特定自定义表情数量
        animated_emoji_count: 动态表情数量
        sticker_count: 贴纸数量
        other_emoji_count: 其他表情类型数量
        emoji_details: 按表情 ID/名称的详细分类
    """

    standard_emoji_count: int = 0
    custom_emoji_count: int = 0
    animated_emoji_count: int = 0
    sticker_count: int = 0
    other_emoji_count: int = 0
    emoji_details: tuple = field(default_factory=tuple)

    @property
    def total_count(self) -> int:
        """获取表情总数。"""
        return (
            self.standard_emoji_count
            + self.custom_emoji_count
            + self.animated_emoji_count
            + self.sticker_count
            + self.other_emoji_count
        )

    @classmethod
    def from_dict(cls, data: dict) -> "EmojiStatistics":
        """从字典创建 EmojiStatistics。"""
        details = data.get("face_details", data.get("emoji_details", {}))
        if isinstance(details, dict):
            details = tuple(details.items())

        return cls(
            standard_emoji_count=data.get(
                "face_count", data.get("standard_emoji_count", 0)
            ),
            custom_emoji_count=data.get(
                "mface_count", data.get("custom_emoji_count", 0)
            ),
            animated_emoji_count=data.get(
                "bface_count", data.get("animated_emoji_count", 0)
            ),
            sticker_count=data.get("sface_count", data.get("sticker_count", 0)),
            other_emoji_count=data.get("other_emoji_count", 0),
            emoji_details=details,
        )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "standard_emoji_count": self.standard_emoji_count,
            "custom_emoji_count": self.custom_emoji_count,
            "animated_emoji_count": self.animated_emoji_count,
            "sticker_count": self.sticker_count,
            "other_emoji_count": self.other_emoji_count,
            "total_emoji_count": self.total_count,
            "emoji_details": dict(self.emoji_details),
            # 向后兼容
            "face_count": self.standard_emoji_count,
            "mface_count": self.custom_emoji_count,
            "bface_count": self.animated_emoji_count,
            "sface_count": self.sticker_count,
        }


@dataclass(frozen=True)
class ActivityVisualization:
    """
    活动可视化数据。

    聊天活动模式的平台无关表示。
    设计上不可变 (frozen=True)。

    属性:
        hourly_activity: 按小时统计的消息数 (0-23)
        daily_activity: 按日期统计的消息数
        user_activity_ranking: 用户活跃度排名列表
        peak_hours: 活动高峰时段列表
        heatmap_data: 活动热力图可视化数据
    """

    hourly_activity: tuple = field(default_factory=tuple)
    daily_activity: tuple = field(default_factory=tuple)
    user_activity_ranking: tuple = field(default_factory=tuple)
    peak_hours: tuple = field(default_factory=tuple)
    heatmap_data: tuple = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict) -> "ActivityVisualization":
        """从字典创建 ActivityVisualization。"""
        hourly = data.get("hourly_activity", {})
        daily = data.get("daily_activity", {})
        ranking = data.get("user_activity_ranking", [])
        peaks = data.get("peak_hours", [])
        heatmap = data.get("activity_heatmap_data", data.get("heatmap_data", {}))

        return cls(
            hourly_activity=tuple(hourly.items())
            if isinstance(hourly, dict)
            else tuple(hourly),
            daily_activity=tuple(daily.items())
            if isinstance(daily, dict)
            else tuple(daily),
            user_activity_ranking=tuple(ranking),
            peak_hours=tuple(peaks),
            heatmap_data=tuple(heatmap.items())
            if isinstance(heatmap, dict)
            else tuple(heatmap),
        )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "hourly_activity": dict(self.hourly_activity),
            "daily_activity": dict(self.daily_activity),
            "user_activity_ranking": list(self.user_activity_ranking),
            "peak_hours": list(self.peak_hours),
            "activity_heatmap_data": dict(self.heatmap_data),
        }


@dataclass(frozen=True)
class GroupStatistics:
    """
    综合群聊统计。

    群聊统计数据的平台无关表示。
    设计上不可变 (frozen=True)。

    属性:
        message_count: 消息总数
        total_characters: 所有消息的总字符数
        participant_count: 唯一参与者数量
        most_active_period: 最活跃时间段描述
        emoji_statistics: 表情使用统计
        activity_visualization: 活动模式数据
        token_usage: 分析使用的 LLM 令牌
    """

    message_count: int = 0
    total_characters: int = 0
    participant_count: int = 0
    most_active_period: str = ""
    emoji_statistics: EmojiStatistics = field(default_factory=EmojiStatistics)
    activity_visualization: ActivityVisualization = field(
        default_factory=ActivityVisualization
    )
    token_usage: TokenUsage = field(default_factory=TokenUsage)

    @property
    def average_message_length(self) -> float:
        """计算平均消息长度。"""
        if self.message_count == 0:
            return 0.0
        return self.total_characters / self.message_count

    @property
    def emoji_count(self) -> int:
        """获取表情总数以保持向后兼容。"""
        return self.emoji_statistics.total_count

    @classmethod
    def from_dict(cls, data: dict) -> "GroupStatistics":
        """从字典创建 GroupStatistics。"""
        emoji_data = data.get("emoji_statistics", {})
        if not emoji_data:
            # 向后兼容：从扁平字段构建
            emoji_data = {
                "face_count": data.get("emoji_count", 0),
            }

        activity_data = data.get("activity_visualization", {})
        token_data = data.get("token_usage", {})

        return cls(
            message_count=data.get("message_count", 0),
            total_characters=data.get("total_characters", 0),
            participant_count=data.get("participant_count", 0),
            most_active_period=data.get("most_active_period", ""),
            emoji_statistics=EmojiStatistics.from_dict(emoji_data),
            activity_visualization=ActivityVisualization.from_dict(activity_data),
            token_usage=TokenUsage.from_dict(token_data),
        )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "message_count": self.message_count,
            "total_characters": self.total_characters,
            "participant_count": self.participant_count,
            "most_active_period": self.most_active_period,
            "emoji_count": self.emoji_count,  # 向后兼容
            "emoji_statistics": self.emoji_statistics.to_dict(),
            "activity_visualization": self.activity_visualization.to_dict(),
            "token_usage": self.token_usage.to_dict(),
        }


@dataclass
class UserStatistics:
    """
    单用户统计（可变以便在分析期间累积）。

    属性:
        user_id: 平台无关的用户标识符
        nickname: 用户显示名称
        message_count: 发送的消息数
        char_count: 发送的总字符数
        emoji_count: 使用的表情数
        reply_count: 回复次数
        hours: 按小时统计的消息数 (0-23)
    """

    user_id: str
    nickname: str = ""
    message_count: int = 0
    char_count: int = 0
    emoji_count: int = 0
    reply_count: int = 0
    hours: dict[int, int] = field(default_factory=lambda: dict.fromkeys(range(24), 0))

    @property
    def average_chars(self) -> float:
        """计算每条消息的平均字符数。"""
        if self.message_count == 0:
            return 0.0
        return self.char_count / self.message_count

    @property
    def emoji_ratio(self) -> float:
        """计算每条消息的表情比率。"""
        if self.message_count == 0:
            return 0.0
        return self.emoji_count / self.message_count

    @property
    def night_ratio(self) -> float:
        """计算夜间活动比率 (0-6 点)。"""
        if self.message_count == 0:
            return 0.0
        night_messages = sum(self.hours.get(h, 0) for h in range(6))
        return night_messages / self.message_count

    @property
    def reply_ratio(self) -> float:
        """计算回复比率。"""
        if self.message_count == 0:
            return 0.0
        return self.reply_count / self.message_count

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "message_count": self.message_count,
            "char_count": self.char_count,
            "emoji_count": self.emoji_count,
            "reply_count": self.reply_count,
            "avg_chars": round(self.average_chars, 1),
            "emoji_ratio": round(self.emoji_ratio, 2),
            "night_ratio": round(self.night_ratio, 2),
            "reply_ratio": round(self.reply_ratio, 2),
            "hours": self.hours,
        }
