"""
分析结果序列化与反序列化器 (Analysis Result Serializer)

负责领域数据模型 (GroupStatistics, SummaryTopic, QualityReview 等) 与 JSON 友好结构之间的相互转换。
"""

from __future__ import annotations

import dataclasses
import enum
from datetime import date, datetime, time

from ...domain.value_objects import (
    ActivityVisualization,
    AnalysisResultPayload,
    EmojiStatistics,
    GoldenQuote,
    GroupStatistics,
    QualityDimension,
    QualityReview,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)


class AnalysisResultSerializer:
    """领域分析结果序列化与快照转换器。"""

    @staticmethod
    def to_json_friendly(obj: object) -> object:
        """递归将领域模型、dataclass、Enum、datetime 等转换为标准 JSON 原生数据结构。

        Args:
            obj: 任意输入对象。

        Returns:
            JSON 原生类型（dict, list, int, float, str, bool, None）。
        """
        if obj is None:
            return None
        if isinstance(obj, enum.Enum):
            return obj.value
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return AnalysisResultSerializer.to_json_friendly(dataclasses.asdict(obj))
        if isinstance(obj, (set, tuple)):
            return [AnalysisResultSerializer.to_json_friendly(item) for item in obj]
        if isinstance(obj, list):
            return [AnalysisResultSerializer.to_json_friendly(item) for item in obj]
        if isinstance(obj, dict):
            return {
                str(k): AnalysisResultSerializer.to_json_friendly(v)
                for k, v in obj.items()
            }
        to_dict_fn = getattr(obj, "to_dict", None)
        if callable(to_dict_fn):
            try:
                return AnalysisResultSerializer.to_json_friendly(to_dict_fn())
            except Exception:
                pass
        return obj

    @classmethod
    def serialize(cls, analysis_result: dict[str, object]) -> dict[str, object]:
        """将包含领域对象的 analysis_result 序列化为 JSON 友好的 dict 快照。

        Args:
            analysis_result: 包含领域模型的分析结果字典。

        Returns:
            JSON 友好的序列化字典。
        """
        return {
            "statistics": cls.to_json_friendly(analysis_result.get("statistics")),
            "topics": cls.to_json_friendly(analysis_result.get("topics", [])),
            "user_titles": cls.to_json_friendly(analysis_result.get("user_titles", [])),
            "user_analysis": cls.to_json_friendly(
                analysis_result.get("user_analysis", {})
            ),
            "chat_quality_review": cls.to_json_friendly(
                analysis_result.get("chat_quality_review")
            ),
        }

    @classmethod
    def deserialize(cls, data: dict[str, object]) -> AnalysisResultPayload:
        """将持久化的 JSON 快照还原为包含领域数据模型的 analysis_result。

        Args:
            data: 持久化或传输的 JSON 数据字典。

        Returns:
            还原后的领域模型字典。
        """
        stats_raw = data.get("statistics", {})
        if not isinstance(stats_raw, dict):
            stats_raw = {}

        golden_quotes = [
            GoldenQuote(**g) if isinstance(g, dict) else g
            for g in stats_raw.get("golden_quotes", [])
        ]
        emoji_stats_raw = stats_raw.get("emoji_statistics", {})
        emoji_stats = (
            EmojiStatistics(**emoji_stats_raw)
            if isinstance(emoji_stats_raw, dict)
            else EmojiStatistics()
        )
        act_viz_raw = stats_raw.get("activity_visualization", {})
        if isinstance(act_viz_raw, dict):
            hourly_act = act_viz_raw.get("hourly_activity")
            if isinstance(hourly_act, dict):
                act_viz_raw["hourly_activity"] = {
                    int(k) if str(k).isdigit() else k: v for k, v in hourly_act.items()
                }
            act_viz = ActivityVisualization(**act_viz_raw)
        else:
            act_viz = ActivityVisualization()
        token_usage_raw = stats_raw.get("token_usage", {})
        token_usage = (
            TokenUsage(**token_usage_raw)
            if isinstance(token_usage_raw, dict)
            else TokenUsage()
        )

        quality_raw = data.get("chat_quality_review") or stats_raw.get(
            "chat_quality_review"
        )
        quality_review = None
        if isinstance(quality_raw, dict):
            dims = [
                QualityDimension(**d) if isinstance(d, dict) else d
                for d in quality_raw.get("dimensions", [])
            ]
            quality_review = QualityReview(
                title=str(quality_raw.get("title", "群聊质量锐评")),
                subtitle=str(quality_raw.get("subtitle", "")),
                dimensions=dims,
                summary=str(quality_raw.get("summary", "")),
            )

        stats = GroupStatistics(
            message_count=int(stats_raw.get("message_count", 0)),
            total_characters=int(stats_raw.get("total_characters", 0)),
            participant_count=int(stats_raw.get("participant_count", 0)),
            most_active_period=str(stats_raw.get("most_active_period", "")),
            golden_quotes=golden_quotes,
            emoji_count=int(stats_raw.get("emoji_count", 0)),
            emoji_statistics=emoji_stats,
            activity_visualization=act_viz,
            token_usage=token_usage,
            chat_quality_review=quality_review,
        )

        raw_topics = data.get("topics")
        topics = [
            SummaryTopic(**t) if isinstance(t, dict) else t
            for t in (raw_topics if isinstance(raw_topics, list) else [])
            if isinstance(t, (dict, SummaryTopic))
        ]
        raw_user_titles = data.get("user_titles")
        user_titles = [
            UserTitle(**t) if isinstance(t, dict) else t
            for t in (raw_user_titles if isinstance(raw_user_titles, list) else [])
            if isinstance(t, (dict, UserTitle))
        ]

        raw_user_analysis = data.get("user_analysis")
        user_analysis: dict[str, object] = (
            raw_user_analysis if isinstance(raw_user_analysis, dict) else {}
        )

        return {
            "statistics": stats,
            "topics": topics,
            "user_titles": user_titles,
            "user_analysis": user_analysis,
            "chat_quality_review": quality_review,
        }
