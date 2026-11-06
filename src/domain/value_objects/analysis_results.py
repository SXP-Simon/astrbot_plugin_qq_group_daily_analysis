"""
群聊分析结果值对象 (Analysis Result Value Objects)

定义每日群聊分析、质量锐评、话题提取与发言统计产生的不可变值对象。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NotRequired, TypedDict

from ...shared.type_guards import is_object_list, is_object_mapping, is_string_mapping

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..repositories.platform_adapter_repository import PlatformAdapterProtocol


class SummaryTopicPayload(TypedDict, total=False):
    """话题持久化字段，允许读取缺少可选字段的旧批次。"""

    topic: str
    contributors: list[str]
    detail: str
    contributor_ids: list[str]


class GoldenQuotePayload(TypedDict, total=False):
    """金句持久化字段。"""

    content: str
    sender: str
    reason: str
    user_id: str


class UserActivityStats(TypedDict):
    """消息清理后生成的用户统计，不包含外部原始字段。"""

    message_count: int
    char_count: int
    emoji_count: int
    nickname: str
    hours: dict[int, int]
    reply_count: int


class UserActivityPayload(TypedDict, total=False):
    """批次中的用户活跃度字段，兼容旧版 active_hours。"""

    name: str
    nickname: str
    message_count: int
    char_count: int
    emoji_count: int
    reply_count: int
    hours: dict[int, int] | None
    active_hours: list[int]
    last_message_time: int


class MergedUserActivity(TypedDict):
    """合并服务初始化后完整的用户统计结构。"""

    nickname: str
    message_count: int
    char_count: int
    emoji_count: int
    reply_count: int
    hours: dict[int, int]
    last_message_time: int


class QualityDimensionPayload(TypedDict, total=False):
    """质量维度的持久化字段。"""

    name: str
    percentage: float
    comment: str
    color: str


class QualityReviewPayload(TypedDict, total=False):
    """聊天质量锐评的持久化字段。"""

    title: str
    subtitle: str
    dimensions: list[QualityDimensionPayload]
    summary: str


class UserActivityRanking(TypedDict):
    """报告中展示的用户活跃度排名条目。"""

    user_id: str
    name: NotRequired[str]
    nickname: NotRequired[str]
    message_count: int
    char_count: NotRequired[int]
    emoji_count: NotRequired[int]
    reply_count: NotRequired[int]


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
    contributor_ids: list[str] = field(default_factory=list[str])

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

    def to_dict(self) -> SummaryTopicPayload:
        """将话题总结值对象序列化为字典。"""
        return {
            "topic": self.topic,
            "contributors": list(self.contributors),
            "detail": self.detail,
            "contributor_ids": list(self.contributor_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> SummaryTopic:
        """从字典反序列化生成 SummaryTopic 值对象。"""
        raw_contribs = data.get("contributors", [])
        contribs = (
            [str(c) for c in raw_contribs if c is not None]
            if is_object_list(raw_contribs)
            else []
        )
        raw_ids = data.get("contributor_ids", [])
        c_ids = (
            [str(cid) for cid in raw_ids if cid is not None]
            if is_object_list(raw_ids)
            else []
        )
        return cls(
            topic=str(data.get("topic", "") or ""),
            contributors=contribs,
            detail=str(data.get("detail", "") or ""),
            contributor_ids=c_ids,
        )


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

    def to_dict(self) -> dict[str, object]:
        """将用户称号值对象序列化为字典。"""
        return {
            "name": self.name,
            "user_id": self.user_id,
            "title": self.title,
            "mbti": self.mbti,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> UserTitle:
        """从字典反序列化生成 UserTitle 值对象。"""
        return cls(
            name=str(data.get("name", "") or ""),
            user_id=str(data.get("user_id", "") or ""),
            title=str(data.get("title", "") or ""),
            mbti=str(data.get("mbti", "") or ""),
            reason=str(data.get("reason", "") or ""),
        )


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

    def to_dict(self) -> GoldenQuotePayload:
        """将金句值对象序列化为字典。"""
        return {
            "content": self.content,
            "sender": self.sender,
            "reason": self.reason,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> GoldenQuote:
        """从字典反序列化生成 GoldenQuote 值对象。"""
        return cls(
            content=str(data.get("content", "") or ""),
            sender=str(data.get("sender", "") or ""),
            reason=str(data.get("reason", "") or ""),
            user_id=str(data.get("user_id", "") or ""),
        )


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

    def to_dict(self) -> QualityDimensionPayload:
        """将维度评分值对象序列化为字典。"""
        return {
            "name": self.name,
            "percentage": self.percentage,
            "comment": self.comment,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> QualityDimension:
        """从字典反序列化生成 QualityDimension 值对象。"""
        try:
            pct = float(str(data.get("percentage", 0.0) or 0.0))
        except (TypeError, ValueError):
            pct = 0.0
        return cls(
            name=str(data.get("name", "") or ""),
            percentage=pct,
            comment=str(data.get("comment", "") or ""),
            color=str(data.get("color", "#607d8b") or "#607d8b"),
        )


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

    def to_dict(self) -> QualityReviewPayload:
        """将锐评值对象序列化为字典。"""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "dimensions": [
                {
                    "name": d.name,
                    "percentage": d.percentage,
                    "comment": d.comment,
                    "color": d.color,
                }
                for d in self.dimensions
            ],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> QualityReview:
        """从字典反序列化生成 QualityReview 值对象。"""
        raw_dims = data.get("dimensions", [])
        dims: list[QualityDimension] = []
        if is_object_list(raw_dims):
            for item in raw_dims:
                if is_string_mapping(item):
                    try:
                        pct = float(str(item.get("percentage", 0.0) or 0.0))
                    except (TypeError, ValueError):
                        pct = 0.0
                    dims.append(
                        QualityDimension(
                            name=str(item.get("name", "") or ""),
                            percentage=pct,
                            comment=str(item.get("comment", "") or ""),
                            color=str(item.get("color", "#607d8b") or "#607d8b"),
                        )
                    )
        return cls(
            title=str(data.get("title", "")),
            subtitle=str(data.get("subtitle", "")),
            dimensions=dims,
            summary=str(data.get("summary", "")),
        )


@dataclass
class ComicStoryboard:
    """漫画分镜场景值对象。

    Attributes:
        scene: 分镜画面生图提示词/场景描述。
    """

    scene: str

    def is_valid(self) -> bool:
        """检查分镜场景是否有效。

        Returns:
            bool: 场景描述非空时返回 True。
        """
        return bool(self.scene and self.scene.strip())

    def to_dict(self) -> dict[str, object]:
        """将分镜场景序列化为字典。"""
        return {"scene": self.scene}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ComicStoryboard:
        """从字典反序列化生成 ComicStoryboard 值对象。"""
        return cls(scene=str(data.get("scene", "") or ""))


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

    def to_dict(self) -> dict[str, int]:
        """将 Token 消耗统计序列化为字典。"""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TokenUsage:
        """从字典反序列化生成 TokenUsage 值对象。"""

        def _to_int(val: object) -> int:
            try:
                return int(str(val or 0))
            except (TypeError, ValueError):
                return 0

        return cls(
            prompt_tokens=_to_int(data.get("prompt_tokens", 0)),
            completion_tokens=_to_int(data.get("completion_tokens", 0)),
            total_tokens=_to_int(data.get("total_tokens", 0)),
        )

    @classmethod
    def from_llm_response(cls, response: object) -> TokenUsage:
        """从 AstrBot LLMResponse 或原始响应对象解析生成 TokenUsage 值对象 (ACL 防腐)。

        兼容 AstrBot TokenUsage 属性 (input, output, total)、OpenAI Usage 对象
        (prompt_tokens, completion_tokens, total_tokens) 以及字典结构。

        Args:
            response: LLM 响应对象或其 raw_completion 字典。

        Returns:
            TokenUsage: 强类型 Token 消耗统计值对象。
        """
        if response is None:
            return cls()

        usage = getattr(response, "usage", None)
        if not usage:
            raw_comp = getattr(response, "raw_completion", None)
            if raw_comp and is_string_mapping(raw_comp):
                usage = raw_comp.get("usage")

        if not usage and is_string_mapping(response):
            usage = response.get("usage") or response

        if not usage:
            return cls()

        def _get_val(*keys_or_attrs: str) -> int:
            for k in keys_or_attrs:
                if is_string_mapping(usage) and k in usage:
                    try:
                        return int(str(usage[k] or 0))
                    except (TypeError, ValueError):
                        pass
                elif hasattr(usage, k):
                    try:
                        return int(str(getattr(usage, k, 0) or 0))
                    except (TypeError, ValueError):
                        pass
            return 0

        prompt_tokens = _get_val("input", "prompt_tokens")
        completion_tokens = _get_val("output", "completion_tokens")
        total_tokens = _get_val("total", "total_tokens")
        if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
            total_tokens = prompt_tokens + completion_tokens

        return cls(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


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
    face_details: dict[str, int] = field(default_factory=dict[str, int])

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

    def to_dict(self) -> dict[str, int | dict[str, int]]:
        """将表情统计值对象序列化为字典。"""
        return {
            "face_count": self.face_count,
            "mface_count": self.mface_count,
            "bface_count": self.bface_count,
            "sface_count": self.sface_count,
            "other_emoji_count": self.other_emoji_count,
            "face_details": dict(self.face_details),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> EmojiStatistics:
        """从字典反序列化生成 EmojiStatistics 值对象。"""
        raw_details = data.get("face_details", {})

        def _to_int(val: object) -> int:
            try:
                return int(str(val or 0))
            except (TypeError, ValueError):
                return 0

        return cls(
            face_count=_to_int(data.get("face_count", 0)),
            mface_count=_to_int(data.get("mface_count", 0)),
            bface_count=_to_int(data.get("bface_count", 0)),
            sface_count=_to_int(data.get("sface_count", 0)),
            other_emoji_count=_to_int(data.get("other_emoji_count", 0)),
            face_details={key: _to_int(value) for key, value in raw_details.items()}
            if is_string_mapping(raw_details)
            else {},
        )


class PeakHourPayload(TypedDict):
    """发言高峰小时及该时段的消息数。"""

    hour: int
    count: int


class HourlyChartPoint(TypedDict):
    """按小时展示的活跃度图表数据点。"""

    hour: int
    count: int
    percentage: float


class ActivityHeatmapPayload(TypedDict, total=False):
    """小时消息与表情分布的图表数据。"""

    hourly_max: int
    emoji_max: int
    hourly_normalized: dict[int, float]
    emoji_normalized: dict[int, float]
    activity_levels: dict[int, str]


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

    hourly_activity: dict[int, int] = field(default_factory=dict[int, int])
    daily_activity: dict[str, int] = field(default_factory=dict[str, int])
    user_activity_ranking: list[UserActivityRanking] = field(
        default_factory=list[UserActivityRanking]
    )
    peak_hours: list[PeakHourPayload | int] = field(
        default_factory=list[PeakHourPayload | int]
    )
    activity_heatmap_data: ActivityHeatmapPayload = field(
        default_factory=lambda: ActivityHeatmapPayload()
    )

    def to_dict(self) -> dict[str, object]:
        """将活跃度时序与图表数据序列化为字典。"""
        return {
            "hourly_activity": dict(self.hourly_activity),
            "daily_activity": dict(self.daily_activity),
            "user_activity_ranking": list(self.user_activity_ranking),
            "peak_hours": list(self.peak_hours),
            "activity_heatmap_data": dict(self.activity_heatmap_data),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ActivityVisualization:
        """从字典反序列化生成 ActivityVisualization 值对象。"""
        hourly_raw = data.get("hourly_activity")
        hourly_parsed: dict[int, int] = {}
        if is_object_mapping(hourly_raw):
            for key, value in hourly_raw.items():
                if not isinstance(key, (str, int)):
                    continue
                try:
                    normalized_key = int(key)
                    count = int(str(value or 0))
                except (TypeError, ValueError):
                    continue
                hourly_parsed[normalized_key] = count

        daily_raw = data.get("daily_activity")
        daily_activity: dict[str, int] = {}
        if is_string_mapping(daily_raw):
            for key, value in daily_raw.items():
                try:
                    daily_activity[key] = int(str(value or 0))
                except (TypeError, ValueError):
                    daily_activity[key] = 0

        ranking_raw = data.get("user_activity_ranking")
        user_ranking: list[UserActivityRanking] = []
        if is_object_list(ranking_raw):
            for item in ranking_raw:
                if not is_string_mapping(item):
                    continue
                count = item.get("message_count", 0)
                if not isinstance(count, int):
                    continue
                ranking: UserActivityRanking = {
                    "user_id": str(item.get("user_id", "")),
                    "message_count": count,
                }
                for name_key in ("name", "nickname"):
                    name = item.get(name_key)
                    if isinstance(name, str):
                        ranking[name_key] = name
                for count_key in ("char_count", "emoji_count", "reply_count"):
                    count = item.get(count_key)
                    if isinstance(count, int):
                        ranking[count_key] = count
                user_ranking.append(ranking)

        peak_raw = data.get("peak_hours")
        peak_hours: list[PeakHourPayload | int] = []
        for item in peak_raw if is_object_list(peak_raw) else []:
            if isinstance(item, int):
                peak_hours.append(item)
            elif is_string_mapping(item):
                hour, count = item.get("hour"), item.get("count")
                if isinstance(hour, int) and isinstance(count, int):
                    peak_hours.append({"hour": hour, "count": count})

        heatmap_raw = data.get("activity_heatmap_data")
        heatmap_data: ActivityHeatmapPayload = {}
        if is_string_mapping(heatmap_raw):
            for maximum_key in ("hourly_max", "emoji_max"):
                maximum = heatmap_raw.get(maximum_key)
                if isinstance(maximum, int):
                    heatmap_data[maximum_key] = maximum
            for normalized_key in ("hourly_normalized", "emoji_normalized"):
                values = heatmap_raw.get(normalized_key)
                if is_object_mapping(values):
                    normalized: dict[int, float] = {}
                    for hour, amount in values.items():
                        if (
                            isinstance(hour, (int, str))
                            and str(hour).isdigit()
                            and isinstance(amount, (int, float))
                        ):
                            normalized[int(hour)] = float(amount)
                    heatmap_data[normalized_key] = normalized
            levels_raw = heatmap_raw.get("activity_levels")
            if is_object_mapping(levels_raw):
                heatmap_data["activity_levels"] = {
                    int(hour): level
                    for hour, level in levels_raw.items()
                    if isinstance(hour, (int, str))
                    and str(hour).isdigit()
                    and isinstance(level, str)
                }

        return cls(
            hourly_activity=hourly_parsed,
            daily_activity=daily_activity,
            user_activity_ranking=user_ranking,
            peak_hours=peak_hours,
            activity_heatmap_data=heatmap_data,
        )


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

    def to_dict(self) -> dict[str, object]:
        """将群聊统计聚合值对象序列化为字典。"""
        return {
            "message_count": self.message_count,
            "total_characters": self.total_characters,
            "participant_count": self.participant_count,
            "most_active_period": self.most_active_period,
            "golden_quotes": [g.to_dict() for g in self.golden_quotes],
            "emoji_count": self.emoji_count,
            "emoji_statistics": self.emoji_statistics.to_dict(),
            "activity_visualization": self.activity_visualization.to_dict(),
            "token_usage": self.token_usage.to_dict(),
            "chat_quality_review": self.chat_quality_review.to_dict()
            if self.chat_quality_review
            else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> GroupStatistics:
        """从字典反序列化生成 GroupStatistics 值对象。"""

        def _to_int(val: object) -> int:
            try:
                return int(str(val or 0))
            except (TypeError, ValueError):
                return 0

        raw_quotes = data.get("golden_quotes", [])
        quotes: list[GoldenQuote] = []
        if is_object_list(raw_quotes):
            for q in raw_quotes:
                if is_string_mapping(q):
                    quotes.append(GoldenQuote.from_dict(q))
                elif isinstance(q, GoldenQuote):
                    quotes.append(q)

        raw_emoji = data.get("emoji_statistics", {})
        emoji_stats = (
            EmojiStatistics.from_dict(raw_emoji)
            if is_string_mapping(raw_emoji)
            else EmojiStatistics()
        )

        raw_viz = data.get("activity_visualization", {})
        viz = (
            ActivityVisualization.from_dict(raw_viz)
            if is_string_mapping(raw_viz)
            else ActivityVisualization()
        )

        raw_tokens = data.get("token_usage", {})
        tokens = (
            TokenUsage.from_dict(raw_tokens)
            if is_string_mapping(raw_tokens)
            else TokenUsage()
        )

        raw_quality = data.get("chat_quality_review")
        quality = (
            QualityReview.from_dict(raw_quality)
            if is_string_mapping(raw_quality)
            else (raw_quality if isinstance(raw_quality, QualityReview) else None)
        )

        return cls(
            message_count=_to_int(data.get("message_count", 0)),
            total_characters=_to_int(data.get("total_characters", 0)),
            participant_count=_to_int(data.get("participant_count", 0)),
            most_active_period=str(data.get("most_active_period", "") or ""),
            golden_quotes=quotes,
            emoji_count=_to_int(data.get("emoji_count", 0)),
            emoji_statistics=emoji_stats,
            activity_visualization=viz,
            token_usage=tokens,
            chat_quality_review=quality,
        )


class ComicTopicPayload(TypedDict):
    """漫画分镜提取话题数据结构"""

    topic: str
    summary: str


@dataclass
class ComicTopic:
    """漫画分镜话题领域模型"""

    topic: str
    summary: str
    heat_score: float = 0.0

    def to_dict(self) -> ComicTopicPayload:
        return {
            "topic": self.topic,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ComicTopic:
        """从字典反序列化生成 ComicTopic 领域模型。"""
        try:
            score = float(str(data.get("heat_score", 0.0) or 0.0))
        except (TypeError, ValueError):
            score = 0.0
        return cls(
            topic=str(data.get("topic", "") or ""),
            summary=str(data.get("summary", "") or ""),
            heat_score=score,
        )


class _AnalysisResultOptional(TypedDict, total=False):
    timestamp: str


class AnalysisResultPayload(_AnalysisResultOptional):
    """领域分析结果字典快照契约"""

    statistics: GroupStatistics
    topics: list[SummaryTopic]
    user_titles: list[UserTitle]
    user_analysis: dict[str, object]
    chat_quality_review: QualityReview | None


class GroupHistoryTopicPayload(TypedDict):
    """历史归档话题摘要契约"""

    topic: str
    detail: str


class GroupHistorySummaryPayload(TypedDict):
    """每日群聊分析归档摘要数据契约"""

    message_count: int
    participant_count: int
    topics: list[GroupHistoryTopicPayload]
    user_titles_count: int
    generated_at: str


class OneBotAlbumPayload(TypedDict, total=False):
    """OneBot 相册元数据契约"""

    album_id: str
    albumId: str
    album_name: str
    albumName: str
    name: str
    pic_total: int


class OneBotHistoryFetchParams(TypedDict, total=False):
    """OneBot 历史消息拉取参数契约"""

    group_id: int | str
    message_seq: int | str
    seq: int | str
    count: int
    message_id: int | str
    reverseOrder: bool


class DrawingProviderConfigPayload(TypedDict, total=False):
    """绘图服务商预设与配置契约"""

    api_url: str
    api_key: str


class QQOfficialMemberProfile(TypedDict, total=False):
    """QQ 官方机器人成员资料缓存契约"""

    nickname: str
    avatar_url: str
    model: str
    api_protocol: str
    image_size: str
    aspect_ratio: str
    image_quality: str
    background: str
    output_format: str
    timeout: int
    proxy: str | None


class AnalysisExportPayload(TypedDict, total=False):
    """群聊分析导出渲染数据聚合契约"""

    statistics: GroupStatistics
    topics: list[SummaryTopic]
    user_titles: list[UserTitle]
    user_analysis: dict[str, object]
    chat_quality_review: QualityReview | None
    generated_at: str
    group_id: str
    date_str: str


class CheckpointSummaryPayload(TypedDict, total=False):
    """阶段 Checkpoint 摘要元数据契约"""

    checkpoint_id: str
    group_id: str
    date_str: str
    stage_name: str
    trace_id: str
    created_at: float
    created_at_formatted: str
    expire_at: float
    data_size: int
    data_size_bytes: int


class CheckpointDetailPayload(TypedDict, total=False):
    """阶段 Checkpoint 详情数据契约"""

    checkpoint_id: str
    group_id: str
    date_str: str
    stage_name: str
    trace_id: str
    created_at: float
    created_at_formatted: str
    expire_at: float
    data: object
    checkpoint_data: object
    data_size: int
    data_size_bytes: int
    metadata: CheckpointSummaryPayload


@dataclass
class AnalysisResult:
    """领域分析聚合结果 (Analysis Result Aggregate)

    封装单次群聊日常分析产出的全量领域聚合，提供严格的类型检查与安全转换。
    """

    statistics: GroupStatistics
    topics: list[SummaryTopic] = field(default_factory=list[SummaryTopic])
    user_titles: list[UserTitle] = field(default_factory=list[UserTitle])
    user_analysis: dict[str, object] = field(default_factory=dict[str, object])
    chat_quality_review: QualityReview | None = None

    def to_dict(self) -> AnalysisResultPayload:
        return {
            "statistics": self.statistics,
            "topics": list(self.topics),
            "user_titles": list(self.user_titles),
            "user_analysis": self.user_analysis,
            "chat_quality_review": self.chat_quality_review,
        }


class DailyAnalysisExecutionResult(TypedDict, total=False):
    """每日群聊分析应用服务执行结果契约"""

    success: bool
    reason: str
    error: str
    analysis_result: AnalysisResultPayload
    messages_count: int
    adapter: PlatformAdapterProtocol
    group_id: str
    platform_id: str
    date_str: str
    fallback_to_fresh_run: bool
    fallback_reason: str
    resumed_from: str
    analysis_success: bool
    report_sent: bool


class ComicAnalysisExecutionResult(TypedDict, total=False):
    """漫画话题分析应用服务执行结果契约"""

    success: bool
    reason: str
    error: str
    topics: list[ComicTopic]
    token_usage: TokenUsage
    messages_count: int
    adapter: PlatformAdapterProtocol
    group_id: str
    platform_id: str


class IncrementalTriggerStatePayload(TypedDict, total=False):
    """增量分析群状态持久化契约"""

    count: int
    version: int
    last_event_ts: float
    last_triggered_at: float
    platform_id: str
    group_id: str


class GroupHistoryPayload(TypedDict, total=False):
    """群历史分析持久化数据结构契约"""

    group_id: str
    last_updated: str
    daily: dict[str, AnalysisResultPayload]


class ComicCharacterConfig(TypedDict, total=False):
    """漫画角色方案中由业务读取的配置字段。"""

    __template_key: str
    name: str
    enable: bool
    persona_id: str
    storyboard_prompt: str
    reference_images: str | list[str]


def parse_user_activity(data: object) -> dict[str, UserActivityPayload]:
    """还原历史用户统计，忽略无法识别的条目并规范小时键。

    Args:
        data: 持久化的用户统计映射。

    Returns:
        已校验字段的用户统计。
    """
    user_stats: dict[str, UserActivityPayload] = {}
    if is_string_mapping(data):
        for user_id, raw_user in data.items():
            if not is_string_mapping(raw_user):
                continue
            user: UserActivityPayload = {}
            for name_key in ("name", "nickname"):
                name = raw_user.get(name_key)
                if isinstance(name, str):
                    user[name_key] = name
            for count_key in (
                "message_count",
                "char_count",
                "emoji_count",
                "reply_count",
                "last_message_time",
            ):
                count = raw_user.get(count_key)
                if isinstance(count, int):
                    user[count_key] = count
            raw_hours = raw_user.get("hours")
            if is_object_mapping(raw_hours):
                user["hours"] = {
                    int(hour): count
                    for hour, count in raw_hours.items()
                    if isinstance(hour, (str, int))
                    and str(hour).isdigit()
                    and isinstance(count, int)
                }
            elif "hours" in raw_user:
                user["hours"] = None
            raw_active_hours = raw_user.get("active_hours")
            if is_object_list(raw_active_hours):
                user["active_hours"] = [
                    hour for hour in raw_active_hours if isinstance(hour, int)
                ]
            user_stats[user_id] = user

    return user_stats
