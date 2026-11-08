"""
增量分析实体 — 滑动窗口批次存储架构

核心概念：
- IncrementalBatch: 单次增量分析产生的独立批次数据，按批次独立存储
- IncrementalState: 报告生成时由多个批次合并而成的聚合视图（不再持久化）

滑动窗口设计：
- 每次增量分析产生一个 IncrementalBatch，独立存储到 KV
- 最终报告时按 analysis_days × 24h 的时间窗口查询批次并合并
- 支持同一天多次发送报告，每次都基于当前时间窗口内的所有批次
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypedDict

from ...shared.type_guards import is_object_list, is_string_mapping
from ..value_objects.analysis_results import (
    GoldenQuote,
    GoldenQuotePayload,
    MergedUserActivity,
    QualityReview,
    QualityReviewPayload,
    SummaryTopic,
    SummaryTopicPayload,
    TokenUsage,
    UserActivityPayload,
    UserActivityRanking,
    parse_user_activity,
)


class IncrementalBatchPayload(TypedDict, total=False):
    group_id: str
    batch_id: str
    timestamp: float
    messages_count: int
    characters_count: int
    hourly_msg_counts: dict[str, int]
    hourly_char_counts: dict[str, int]
    user_stats: dict[str, UserActivityPayload]
    emoji_stats: dict[str, int | dict[str, int]]
    topics: list[SummaryTopicPayload]
    golden_quotes: list[GoldenQuotePayload]
    token_usage: dict[str, int]
    chat_quality_review: QualityReviewPayload | None
    last_message_timestamp: int
    participant_ids: list[str]


@dataclass(frozen=True)
class IncrementalBatchPage:
    """同一次批次索引读取得到的分页概览。"""

    items: list[IncrementalBatchPayload]
    total: int
    page: int
    page_size: int
    last_message_timestamp: int | None


@dataclass
class IncrementalBatch:
    """
    单次增量分析批次数据

    每次增量分析执行完毕后产生一个 IncrementalBatch，
    包含该批次的所有统计数据和 LLM 分析结果，独立存储到 KV。

    Attributes:
        group_id: 群组 ID
        batch_id: 批次唯一标识（UUID）
        timestamp: 批次创建时间戳（epoch）
        messages_count: 本批次分析的消息数量
        characters_count: 本批次的总字符数
        hourly_msg_counts: 按小时的消息计数 {hour_str: count}
        hourly_char_counts: 按小时的字符计数 {hour_str: count}
        user_stats: 用户统计 {user_id: {name, message_count, char_count, ...}}
        emoji_stats: 表情统计 {emoji_type: count}
        topics: 本批次提取的话题列表
        golden_quotes: 本批次提取的金句列表
        token_usage: 本批次 token 消耗 {prompt_tokens, completion_tokens, total_tokens}
        chat_quality_review: 本批次提取的聊天质量锐评
        last_message_timestamp: 本批次最后一条消息的时间戳
        participant_ids: 本批次参与者 ID 列表
    """

    group_id: str = ""
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    # 统计数据
    messages_count: int = 0
    characters_count: int = 0
    hourly_msg_counts: dict[str, int] = field(default_factory=dict[str, int])
    hourly_char_counts: dict[str, int] = field(default_factory=dict[str, int])

    # 用户活跃数据
    user_stats: dict[str, UserActivityPayload] = field(
        default_factory=dict[str, UserActivityPayload]
    )

    # 表情统计
    emoji_stats: dict[str, int | dict[str, int]] = field(
        default_factory=dict[str, int | dict[str, int]]
    )

    # LLM 分析结果
    topics: list[SummaryTopicPayload] = field(default_factory=list[SummaryTopicPayload])
    golden_quotes: list[GoldenQuotePayload] = field(
        default_factory=list[GoldenQuotePayload]
    )

    # Token 消耗
    token_usage: dict[str, int] = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    )

    # 增量追踪
    chat_quality_review: QualityReviewPayload | None = None
    last_message_timestamp: int = 0
    participant_ids: list[str] = field(default_factory=list[str])

    def to_dict(self) -> IncrementalBatchPayload:
        """序列化为字典，用于 KV 存储"""
        return {
            "group_id": self.group_id,
            "batch_id": self.batch_id,
            "timestamp": self.timestamp,
            "messages_count": self.messages_count,
            "characters_count": self.characters_count,
            "hourly_msg_counts": self.hourly_msg_counts,
            "hourly_char_counts": self.hourly_char_counts,
            "user_stats": self.user_stats,
            "emoji_stats": self.emoji_stats,
            "topics": self.topics,
            "golden_quotes": self.golden_quotes,
            "token_usage": self.token_usage,
            "chat_quality_review": self.chat_quality_review,
            "last_message_timestamp": self.last_message_timestamp,
            "participant_ids": self.participant_ids,
        }

    @classmethod
    def from_dict(cls, data: object) -> IncrementalBatch:
        """从字典反序列化"""
        if not is_string_mapping(data):
            raise ValueError("增量批次必须是字段名称为字符串的字典")

        user_stats = parse_user_activity(data.get("user_stats", {}))

        emoji_stats: dict[str, int | dict[str, int]] = {}
        raw_emoji = data.get("emoji_stats", {})
        if is_string_mapping(raw_emoji):
            for key, value in raw_emoji.items():
                if isinstance(value, int):
                    emoji_stats[key] = value
                elif is_string_mapping(value):
                    emoji_stats[key] = {
                        name: count
                        for name, count in value.items()
                        if isinstance(count, int)
                    }

        raw_topics = data.get("topics", [])
        topics = (
            [
                SummaryTopic.from_dict(item).to_dict()
                for item in raw_topics
                if is_string_mapping(item)
            ]
            if is_object_list(raw_topics)
            else []
        )
        raw_quotes = data.get("golden_quotes", [])
        quotes = (
            [
                GoldenQuote.from_dict(item).to_dict()
                for item in raw_quotes
                if is_string_mapping(item)
            ]
            if is_object_list(raw_quotes)
            else []
        )
        raw_tokens = data.get("token_usage", {})
        tokens = (
            TokenUsage.from_dict(raw_tokens)
            if is_string_mapping(raw_tokens)
            else TokenUsage()
        )
        raw_quality = data.get("chat_quality_review")
        quality = (
            QualityReview.from_dict(raw_quality).to_dict()
            if is_string_mapping(raw_quality)
            else None
        )
        raw_participants = data.get("participant_ids", [])
        participant_ids = (
            [item for item in raw_participants if isinstance(item, str)]
            if is_object_list(raw_participants)
            else []
        )

        # 批次身份和游标无法解释时拒绝加载，避免把错误数据推进分析游标。
        group_id = data.get("group_id", "")
        batch_id = data.get("batch_id", "")
        timestamp = data.get("timestamp", 0.0)
        last_timestamp = data.get("last_message_timestamp", 0)
        messages_count = data.get("messages_count", 0)
        characters_count = data.get("characters_count", 0)
        if (
            not isinstance(group_id, str)
            or not isinstance(batch_id, str)
            or not isinstance(timestamp, (int, float))
            or not isinstance(last_timestamp, int)
            or not isinstance(messages_count, int)
            or not isinstance(characters_count, int)
        ):
            raise ValueError("增量批次的标识、时间戳或计数格式无效")
        raw_hourly_messages = data.get("hourly_msg_counts", {})
        hourly_messages = (
            {
                key: value
                for key, value in raw_hourly_messages.items()
                if isinstance(value, int)
            }
            if is_string_mapping(raw_hourly_messages)
            else {}
        )
        raw_hourly_characters = data.get("hourly_char_counts", {})
        hourly_characters = (
            {
                key: value
                for key, value in raw_hourly_characters.items()
                if isinstance(value, int)
            }
            if is_string_mapping(raw_hourly_characters)
            else {}
        )
        return cls(
            group_id=group_id,
            batch_id=batch_id,
            timestamp=timestamp,
            messages_count=messages_count,
            characters_count=characters_count,
            hourly_msg_counts=hourly_messages,
            hourly_char_counts=hourly_characters,
            user_stats=user_stats,
            emoji_stats=emoji_stats,
            topics=topics,
            golden_quotes=quotes,
            token_usage=tokens.to_dict(),
            chat_quality_review=quality,
            last_message_timestamp=last_timestamp,
            participant_ids=participant_ids,
        )

    def get_summary(self) -> dict[str, object]:
        """获取批次摘要信息"""
        return {
            "batch_id": self.batch_id[:8],
            "timestamp": datetime.fromtimestamp(self.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "messages_count": self.messages_count,
            "topics_count": len(self.topics),
            "quotes_count": len(self.golden_quotes),
            "participants": len(self.participant_ids),
        }


@dataclass
class IncrementalState:
    """
    增量分析聚合视图（报告时使用）

    由多个 IncrementalBatch 合并而成，不直接持久化。
    IncrementalMergeService.merge_batches() 负责从批次列表构建此对象。

    Attributes:
        group_id: 群组 ID
        window_start: 滑动窗口起始时间戳
        window_end: 滑动窗口结束时间戳
        topics: 合并去重后的话题列表
        golden_quotes: 合并去重后的金句列表
        hourly_message_counts: 合并后的每小时消息计数 {hour_str: count}
        hourly_character_counts: 合并后的每小时字符计数 {hour_str: count}
        user_activities: 合并后的用户活跃数据
        emoji_counts: 合并后的表情统计
        total_message_count: 窗口内总消息数
        total_character_count: 窗口内总字符数
        total_analysis_count: 窗口内批次数量
        total_token_usage: 累计 token 消耗
        last_analyzed_message_timestamp: 最后分析消息时间戳
        all_participant_ids: 所有参与者 ID 集合
    """

    # 标识信息
    group_id: str = ""
    window_start: float = 0.0
    window_end: float = 0.0

    # 合并后的 LLM 分析结果
    topics: list[SummaryTopicPayload] = field(default_factory=list[SummaryTopicPayload])
    golden_quotes: list[GoldenQuotePayload] = field(
        default_factory=list[GoldenQuotePayload]
    )
    chat_quality_review: QualityReviewPayload | None = None
    all_quality_reviews: list[QualityReviewPayload] = field(
        default_factory=list[QualityReviewPayload]
    )  # 存储所有批次的质量锐评，用于最终报告时的汇总分析

    # 合并后的统计数据（按小时）
    hourly_message_counts: dict[str, int] = field(default_factory=dict[str, int])
    hourly_character_counts: dict[str, int] = field(default_factory=dict[str, int])

    # 用户活跃数据
    user_activities: dict[str, MergedUserActivity] = field(
        default_factory=dict[str, MergedUserActivity]
    )

    # 表情统计
    emoji_counts: dict[str, int | dict[str, int]] = field(
        default_factory=dict[str, int | dict[str, int]]
    )

    # 汇总统计
    total_message_count: int = 0
    total_character_count: int = 0
    total_analysis_count: int = 0
    total_token_usage: dict[str, int] = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    )

    # 增量跟踪
    last_analyzed_message_timestamp: int = 0
    all_participant_ids: set[str] = field(default_factory=set[str])

    # 元数据
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def get_peak_hours(self, top_n: int = 3) -> list[int]:
        """
        获取消息最活跃的时段。

        Args:
            top_n: 返回前 N 个最活跃的小时

        Returns:
            list[int]: 活跃小时列表，按消息量降序
        """
        if not self.hourly_message_counts:
            return []
        sorted_hours = sorted(
            self.hourly_message_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [int(h) for h, _ in sorted_hours[:top_n]]

    def get_most_active_period(self) -> str:
        """
        获取最活跃时段的描述字符串。

        Returns:
            str: 如 "20:00-21:00"
        """
        peak = self.get_peak_hours(1)
        if not peak:
            return "未知"
        hour = peak[0]
        return f"{hour:02d}:00-{hour + 1:02d}:00"

    def get_user_activity_ranking(self, top_n: int = 10) -> list[UserActivityRanking]:
        """
        获取用户活跃度排名。

        Args:
            top_n: 返回前 N 名

        Returns:
            list[dict]: 按消息数降序排列的用户列表
        """
        users: list[UserActivityRanking] = []
        for user_id, data in self.user_activities.items():
            users.append(
                {
                    "user_id": user_id,
                    "name": data.get("nickname", user_id),
                    "message_count": data.get("message_count", 0),
                    "char_count": data.get("char_count", 0),
                }
            )
        users.sort(key=lambda x: x["message_count"], reverse=True)
        return users[:top_n]

    def get_window_date_str(self) -> str:
        """
        获取窗口的日期范围字符串，用于报告显示。

        Returns:
            str: 如 "2024-01-15" 或 "2024-01-14 ~ 2024-01-15"
        """
        if self.window_start <= 0 or self.window_end <= 0:
            return datetime.now().strftime("%Y-%m-%d")

        start_date = datetime.fromtimestamp(self.window_start).strftime("%Y-%m-%d")
        end_date = datetime.fromtimestamp(self.window_end).strftime("%Y-%m-%d")

        if start_date == end_date:
            return end_date
        return f"{start_date} ~ {end_date}"

    def get_summary(self) -> dict[str, object]:
        """
        获取当前增量状态的摘要信息，用于状态查询命令。

        Returns:
            dict: 包含关键统计信息的摘要
        """
        return {
            "group_id": self.group_id,
            "window": self.get_window_date_str(),
            "total_messages": self.total_message_count,
            "total_characters": self.total_character_count,
            "total_analyses": self.total_analysis_count,
            "topics_count": len(self.topics),
            "quotes_count": len(self.golden_quotes),
            "participants": len(self.all_participant_ids),
            "total_tokens": self.total_token_usage.get("total_tokens", 0),
            "last_analysis_time": (
                datetime.fromtimestamp(self.updated_at).strftime("%H:%M:%S")
                if self.updated_at
                else "无"
            ),
            "peak_hours": self.get_peak_hours(3),
        }

    @staticmethod
    def is_duplicate_topic(
        new_topic: SummaryTopicPayload,
        existing_topics: list[SummaryTopicPayload],
        threshold: float = 0.6,
    ) -> bool:
        """
        检测话题是否与已有话题重复。

        使用简单的字符重叠相似度判断。
        当新话题的名称与已有话题名称相似度超过阈值时，认为是重复话题。

        Args:
            new_topic: 待检测的新话题
            existing_topics: 已有话题列表
            threshold: 相似度阈值（0-1），默认 0.6

        Returns:
            bool: 是否重复
        """
        new_name = new_topic.get("topic", "")
        if not new_name:
            return False

        for existing in existing_topics:
            existing_name = existing.get("topic", "")
            if not existing_name:
                continue
            similarity = IncrementalState.char_overlap_similarity(
                new_name, existing_name
            )
            if similarity >= threshold:
                return True
        return False

    @staticmethod
    def is_duplicate_quote(
        new_quote: GoldenQuotePayload,
        existing_quotes: list[GoldenQuotePayload],
        threshold: float = 0.7,
    ) -> bool:
        """
        检测金句是否与已有金句重复。

        Args:
            new_quote: 待检测的新金句
            existing_quotes: 已有金句列表
            threshold: 相似度阈值（0-1），默认 0.7

        Returns:
            bool: 是否重复
        """
        new_content = new_quote.get("content", "")
        if not new_content:
            return False

        for existing in existing_quotes:
            existing_content = existing.get("content", "")
            if not existing_content:
                continue
            similarity = IncrementalState.char_overlap_similarity(
                new_content, existing_content
            )
            if similarity >= threshold:
                return True
        return False

    @staticmethod
    def char_overlap_similarity(s1: str, s2: str) -> float:
        """
        计算两个字符串的字符重叠相似度（Jaccard 相似系数）。

        Args:
            s1: 第一个字符串
            s2: 第二个字符串

        Returns:
            float: 相似度值（0-1）
        """
        if not s1 or not s2:
            return 0.0
        set1 = set(s1)
        set2 = set(s2)
        intersection = set1 & set2
        union = set1 | set2
        if not union:
            return 0.0
        return len(intersection) / len(union)
