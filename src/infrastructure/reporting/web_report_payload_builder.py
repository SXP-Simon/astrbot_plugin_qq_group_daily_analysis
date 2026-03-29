"""
网页日报 payload 构建器。
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from ...utils.logger import logger

AvatarDataGetter = Callable[[str], Awaitable[str | None]]
NicknameGetter = Callable[[str], Awaitable[str | None]]

_MENTION_PATTERN = re.compile(r"\[(\d+)\]")


class WebReportPayloadBuilder:
    """将分析结果转换为可上传到 Worker 的结构化 JSON。"""

    def __init__(self, config_manager):
        self.config_manager = config_manager

    async def build(
        self,
        analysis_result: dict[str, Any],
        avatar_data_getter: AvatarDataGetter | None = None,
        nickname_getter: NicknameGetter | None = None,
    ) -> dict[str, Any]:
        statistics = analysis_result["statistics"]
        topics = [
            self._serialize_topic(topic)
            for topic in analysis_result.get("topics", []) or []
        ]
        user_titles = [
            self._serialize_user_title(title)
            for title in analysis_result.get("user_titles", []) or []
        ]
        golden_quotes = [
            self._serialize_golden_quote(quote)
            for quote in self._extract_golden_quotes(analysis_result)
        ]
        chat_quality_review = self._serialize_chat_quality_review(
            analysis_result.get("chat_quality_review")
            or self._get_value(statistics, "chat_quality_review")
        )
        user_analysis = self._normalize_user_analysis(
            analysis_result.get("user_analysis", {}) or {}
        )

        user_directory = await self._build_user_directory(
            topics=topics,
            user_titles=user_titles,
            golden_quotes=golden_quotes,
            user_analysis=user_analysis,
            avatar_data_getter=avatar_data_getter,
            nickname_getter=nickname_getter,
        )

        return {
            "version": 1,
            "template": self.config_manager.get_report_template(),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "statistics": self._serialize_statistics(statistics),
            "topics": topics,
            "user_titles": user_titles,
            "golden_quotes": golden_quotes,
            "chat_quality_review": chat_quality_review,
            "user_directory": user_directory,
        }

    async def _build_user_directory(
        self,
        *,
        topics: list[dict[str, Any]],
        user_titles: list[dict[str, Any]],
        golden_quotes: list[dict[str, Any]],
        user_analysis: dict[str, dict[str, Any]],
        avatar_data_getter: AvatarDataGetter | None,
        nickname_getter: NicknameGetter | None,
    ) -> dict[str, dict[str, str]]:
        user_ids = set()
        display_name_hints: dict[str, str] = {}

        for title in user_titles:
            user_id = str(title.get("user_id", "") or "")
            if user_id:
                user_ids.add(user_id)
                if title.get("name"):
                    display_name_hints[user_id] = str(title["name"])

        for quote in golden_quotes:
            user_id = str(quote.get("user_id", "") or "")
            if user_id:
                user_ids.add(user_id)
                if quote.get("sender"):
                    display_name_hints[user_id] = str(quote["sender"])

        for topic in topics:
            user_ids.update(_MENTION_PATTERN.findall(topic.get("detail", "") or ""))

        for quote in golden_quotes:
            user_ids.update(_MENTION_PATTERN.findall(quote.get("reason", "") or ""))

        for user_id, user_info in user_analysis.items():
            if user_id in user_ids:
                hinted_name = user_info.get("nickname") or user_info.get("name")
                if hinted_name:
                    display_name_hints[user_id] = str(hinted_name)

        user_directory: dict[str, dict[str, str]] = {}
        for user_id in sorted(user_ids):
            display_name = display_name_hints.get(user_id)
            if self._is_placeholder_display_name(display_name, user_id):
                display_name = None

            if not display_name and nickname_getter:
                try:
                    display_name = await nickname_getter(user_id)
                except Exception as exc:
                    logger.warning(f"获取网页日报昵称失败 {user_id}: {exc}")

            if self._is_placeholder_display_name(display_name, user_id):
                display_name = user_id

            avatar_data = ""
            if avatar_data_getter:
                try:
                    avatar_data = str(await avatar_data_getter(user_id) or "")
                except Exception as exc:
                    logger.warning(f"获取网页日报头像失败 {user_id}: {exc}")

            user_directory[user_id] = {
                "name": str(display_name),
                "avatar_data": avatar_data,
            }

        return user_directory

    def _serialize_statistics(self, statistics: Any) -> dict[str, Any]:
        activity_visualization = (
            self._get_value(statistics, "activity_visualization") or {}
        )
        token_usage = self._get_value(statistics, "token_usage") or {}

        return {
            "message_count": self._get_int(statistics, "message_count"),
            "participant_count": self._get_int(statistics, "participant_count"),
            "total_characters": self._get_int(statistics, "total_characters"),
            "emoji_count": self._get_int(statistics, "emoji_count"),
            "most_active_period": str(
                self._get_value(statistics, "most_active_period", "") or ""
            ),
            "hourly_activity": self._normalize_hourly_activity(
                self._get_value(activity_visualization, "hourly_activity", {}) or {}
            ),
            "token_usage": {
                "prompt_tokens": self._get_int(token_usage, "prompt_tokens"),
                "completion_tokens": self._get_int(token_usage, "completion_tokens"),
                "total_tokens": self._get_int(token_usage, "total_tokens"),
            },
        }

    def _serialize_topic(self, topic: Any) -> dict[str, Any]:
        contributors = self._get_value(topic, "contributors", []) or []
        return {
            "topic": str(
                self._get_value(topic, "topic", self._get_value(topic, "name", ""))
                or ""
            ),
            "contributors": [str(item) for item in contributors if item],
            "detail": str(self._get_value(topic, "detail", "") or ""),
        }

    def _serialize_user_title(self, title: Any) -> dict[str, Any]:
        return {
            "user_id": str(self._get_value(title, "user_id", "") or ""),
            "name": str(self._get_value(title, "name", "") or ""),
            "title": str(self._get_value(title, "title", "") or ""),
            "mbti": str(self._get_value(title, "mbti", "") or ""),
            "reason": str(self._get_value(title, "reason", "") or ""),
        }

    def _serialize_golden_quote(self, quote: Any) -> dict[str, Any]:
        return {
            "user_id": str(self._get_value(quote, "user_id", "") or ""),
            "sender": str(self._get_value(quote, "sender", "") or ""),
            "content": str(self._get_value(quote, "content", "") or ""),
            "reason": str(self._get_value(quote, "reason", "") or ""),
        }

    def _serialize_chat_quality_review(self, review: Any) -> dict[str, Any] | None:
        if not review:
            return None

        dimensions = []
        for dimension in self._get_value(review, "dimensions", []) or []:
            dimensions.append(
                {
                    "name": str(self._get_value(dimension, "name", "") or ""),
                    "percentage": self._get_float(dimension, "percentage"),
                    "comment": str(self._get_value(dimension, "comment", "") or ""),
                    "color": str(
                        self._get_value(dimension, "color", "#607d8b") or "#607d8b"
                    ),
                }
            )

        return {
            "title": str(self._get_value(review, "title", "") or ""),
            "subtitle": str(self._get_value(review, "subtitle", "") or ""),
            "dimensions": dimensions,
            "summary": str(self._get_value(review, "summary", "") or ""),
        }

    def _extract_golden_quotes(self, analysis_result: dict[str, Any]) -> list[Any]:
        statistics = analysis_result["statistics"]
        quotes = self._get_value(statistics, "golden_quotes", [])
        return list(quotes or [])

    def _normalize_hourly_activity(self, hourly_activity: Any) -> dict[str, int]:
        if isinstance(hourly_activity, dict):
            items = hourly_activity.items()
        else:
            items = hourly_activity or []

        normalized: dict[str, int] = {}
        for hour, count in items:
            normalized[str(hour)] = self._coerce_int(count)
        return normalized

    def _normalize_user_analysis(
        self,
        user_analysis: dict[Any, Any],
    ) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        for user_id, raw_info in user_analysis.items():
            if isinstance(raw_info, dict):
                normalized[str(user_id)] = raw_info
        return normalized

    @staticmethod
    def _get_value(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _get_int(self, obj: Any, key: str) -> int:
        return self._coerce_int(self._get_value(obj, key, 0))

    @staticmethod
    def _get_float(obj: Any, key: str) -> float:
        try:
            value = obj.get(key, 0) if isinstance(obj, dict) else getattr(obj, key, 0)
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _coerce_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _is_placeholder_display_name(name: str | None, user_id: str) -> bool:
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized.lower() in {"unknown", "none", "null", "nil", "undefined"}:
            return True
        return normalized == str(user_id).strip()
