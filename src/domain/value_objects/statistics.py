"""
统计值对象 - 平台无关的统计数据表示

该模块包含群聊分析期间收集的各种统计数据的值对象。
所有对象都是不可变的和平台无关的。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenUsage:
    """
    值对象：LLM 令牌消耗统计

    记录分析过程中消耗的 Prompt 和 Completion Token。

    Attributes:
        prompt_tokens (int): 提示词 Token 数
        completion_tokens (int): 回答 Token 数
        total_tokens (int): 总计 Token 数
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "TokenUsage":
        """从字典还原 TokenUsage 对象。"""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )

    def to_dict(self) -> dict:
        """转换为字典格式，用于序列化。"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def __add__(self, other: object) -> "TokenUsage":
        """支持 TokenUsage 对象的加法运算。"""
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
    值对象：表情符号统计

    汇总消息链中不同类别的表情使用情况。

    Attributes:
        standard_emoji_count (int): 标准 Unicode 表情数
        custom_emoji_count (int): 平台自定义表情数
        animated_emoji_count (int): 动态表情数
        sticker_count (int): 贴纸/大表情数
        other_emoji_count (int): 其他未知类型
        emoji_details (tuple[tuple[str, int], ...]): 表情 ID 与次数的详细列表
    """

    standard_emoji_count: int = 0
    custom_emoji_count: int = 0
    animated_emoji_count: int = 0
    sticker_count: int = 0
    other_emoji_count: int = 0
    emoji_details: tuple[tuple[str, int], ...] = field(default_factory=tuple)

    @property
    def total_count(self) -> int:
        """获取所有表情的总数。"""
        return (
            self.standard_emoji_count
            + self.custom_emoji_count
            + self.animated_emoji_count
            + self.sticker_count
            + self.other_emoji_count
        )

    @classmethod
    def from_dict(cls, data: dict) -> "EmojiStatistics":
        """从持久化字典构建统计对象。"""
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
        """转换为持久化字典，包含向后兼容字段。"""
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
    值对象：活动可视化数据

    存储用于生成图表的各种活跃度指标。

    Attributes:
        hourly_activity (tuple[tuple[int, int], ...]): 24 小时活跃分布
        daily_activity (tuple[tuple[str, int], ...]): 每日消息数分布
        user_activity_ranking (tuple[dict, ...]): 用户活跃排名数据
        peak_hours (tuple[int, ...]): 高峰小时 ID
        heatmap_data (tuple[Any, ...]): 热力图原始数据
    """

    hourly_activity: tuple[tuple[int, int], ...] = field(default_factory=tuple)
    daily_activity: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    user_activity_ranking: tuple[dict, ...] = field(default_factory=tuple)
    peak_hours: tuple[int, ...] = field(default_factory=tuple)
    heatmap_data: tuple = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict) -> "ActivityVisualization":
        """从字典反序列话可视化数据。"""
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
    值对象：综合群聊统计

    Attributes:
        message_count (int): 消息总数
        total_characters (int): 字符总数
        participant_count (int): 活跃人数
        most_active_period (str): 描述性的最活跃时段
        emoji_statistics (EmojiStatistics): 表情分类统计
        activity_visualization (ActivityVisualization): 可视化元数据
        token_usage (TokenUsage): LLM 消耗记录
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
        """计算平均每条消息的字符长度。"""
        if self.message_count == 0:
            return 0.0
        return self.total_characters / self.message_count

    @property
    def emoji_count(self) -> int:
        """返回表情总数（向后兼容）。"""
        return self.emoji_statistics.total_count

    @classmethod
    def from_dict(cls, data: dict) -> "GroupStatistics":
        """由字典数据构建完整的统计模型。"""
        emoji_data = data.get("emoji_statistics", {})
        if not emoji_data:
            # 向后兼容：从旧版本扁平字段中恢复
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
        """转换为可进行 JSON 序列化的字典。"""
        return {
            "message_count": self.message_count,
            "total_characters": self.total_characters,
            "participant_count": self.participant_count,
            "most_active_period": self.most_active_period,
            "emoji_count": self.emoji_count,  # 导出时也包含此字段以支持旧版阅读器
            "emoji_statistics": self.emoji_statistics.to_dict(),
            "activity_visualization": self.activity_visualization.to_dict(),
            "token_usage": self.token_usage.to_dict(),
        }


@dataclass
class UserStatistics:
    """
    可变模型：单个用户的行为分析

    用于在统计计算过程中作为状态累加器。

    Attributes:
        user_id (str): 用户唯一标示
        nickname (str): 用户名
        message_count (int): 消息条数
        char_count (int): 字符总数
        emoji_count (int): 表情总数
        reply_count (int): 被回复或回复的次数
        hours (dict[int, int]): 小时活跃频次 (0-23)
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
        """平均每条消息的字符数。"""
        if self.message_count == 0:
            return 0.0
        return self.char_count / self.message_count

    @property
    def emoji_ratio(self) -> float:
        """平均每条消息包含的表情数。"""
        if self.message_count == 0:
            return 0.0
        return self.emoji_count / self.message_count

    @property
    def night_ratio(self) -> float:
        """深夜活跃占比（凌晨 0 点至 6 点）。"""
        if self.message_count == 0:
            return 0.0
        night_messages = sum(self.hours.get(h, 0) for h in range(6))
        return night_messages / self.message_count

    @property
    def reply_ratio(self) -> float:
        """回复行为占比。"""
        if self.message_count == 0:
            return 0.0
        return self.reply_count / self.message_count

    def to_dict(self) -> dict:
        """返回详细的用户行为分析字典。"""
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
