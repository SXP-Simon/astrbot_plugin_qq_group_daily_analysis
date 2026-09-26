"""
分析结果序列化与反序列化器 (Analysis Result Serializer)

负责领域数据模型 (GroupStatistics, SummaryTopic, QualityReview 等) 与 JSON 友好结构之间的相互转换。
"""

from __future__ import annotations

import dataclasses
import enum
from datetime import date, datetime, time

from ...domain.value_objects import (
    AnalysisResultPayload,
    GroupStatistics,
    QualityReview,
    SummaryTopic,
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
        stats = (
            GroupStatistics.from_dict(stats_raw)
            if isinstance(stats_raw, dict)
            else (
                stats_raw
                if isinstance(stats_raw, GroupStatistics)
                else GroupStatistics(0, 0, 0, "", [], 0)
            )
        )

        quality_raw = data.get("chat_quality_review")
        quality_review = (
            QualityReview.from_dict(quality_raw)
            if isinstance(quality_raw, dict)
            else (
                quality_raw
                if isinstance(quality_raw, QualityReview)
                else stats.chat_quality_review
            )
        )
        if stats.chat_quality_review is None and quality_review is not None:
            stats.chat_quality_review = quality_review

        raw_topics = data.get("topics")
        topics: list[SummaryTopic] = []
        if isinstance(raw_topics, list):
            for t in raw_topics:
                if isinstance(t, dict):
                    topics.append(SummaryTopic.from_dict(t))
                elif isinstance(t, SummaryTopic):
                    topics.append(t)

        raw_user_titles = data.get("user_titles")
        user_titles: list[UserTitle] = []
        if isinstance(raw_user_titles, list):
            for t in raw_user_titles:
                if isinstance(t, dict):
                    user_titles.append(UserTitle.from_dict(t))
                elif isinstance(t, UserTitle):
                    user_titles.append(t)

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
