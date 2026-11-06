"""
分析领域服务 - 领域层
负责用户维度的活跃度分析、发言习惯及活动模式识别。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

from ..value_objects.unified_message import MessageContentType, UnifiedMessage

if TYPE_CHECKING:
    from ..value_objects.analysis_results import UserActivityRanking
    from ..value_objects.analysis_results import UserActivityStats as UserActivityStats


class UserActivityPattern(TypedDict, total=False):
    """用户活跃时间与夜间发言比例。"""

    most_active_hour: int
    night_ratio: float
    hourly_distribution: dict[int, int]


class AnalysisDomainService:
    """分析领域服务 - 处理用户画像及行为分析"""

    def analyze_user_activity(
        self,
        messages: list[UnifiedMessage],
        bot_self_ids: list[str] | None = None,
    ) -> dict[str, UserActivityStats]:
        """分析用户活跃度。

        基于 UnifiedMessage 计算每个用户的发言数、字数、表情数等。

        Args:
            messages: 统一消息对象列表。
            bot_self_ids: 机器人自身 ID 列表，用于排除自身发言。

        Returns:
            dict[str, UserActivityStats]: 用户 ID 到活跃度统计字典的映射。
        """
        user_stats: dict[str, UserActivityStats] = {}

        bot_ids = set(bot_self_ids or [])

        for msg in messages:
            user_id = msg.sender_id

            # 跳过机器人自己的消息
            if user_id in bot_ids:
                continue

            stats = user_stats.setdefault(
                user_id,
                {
                    "message_count": 0,
                    "char_count": 0,
                    "emoji_count": 0,
                    "nickname": "",
                    "hours": {},
                    "reply_count": 0,
                },
            )
            stats["message_count"] += 1
            stats["nickname"] = msg.sender_card or msg.sender_name

            # 统计时间分布
            msg_time = datetime.fromtimestamp(msg.timestamp)
            hour = msg_time.hour
            stats["hours"][hour] = stats["hours"].get(hour, 0) + 1

            # 统计内容
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    stats["char_count"] += len(content.text or "")

                elif content.is_emoji():
                    stats["emoji_count"] += 1

                elif content.type == MessageContentType.REPLY:
                    stats["reply_count"] += 1

        return user_stats

    def get_top_users(
        self, user_activity: dict[str, UserActivityStats], limit: int = 10
    ) -> list[UserActivityRanking]:
        """获取最活跃的用户列表。

        Args:
            user_activity: 用户活跃度聚合数据字典。
            limit: 返回的用户数量上限。

        Returns:
            list[dict]: 排序后的前 N 名活跃用户列表。
        """
        users: list[UserActivityRanking] = []
        for user_id, stats in user_activity.items():
            users.append(
                {
                    "user_id": user_id,
                    "nickname": stats["nickname"],
                    "message_count": stats["message_count"],
                    "char_count": stats["char_count"],
                    "emoji_count": stats["emoji_count"],
                    "reply_count": stats["reply_count"],
                }
            )

        # 按消息数量排序
        users.sort(key=lambda x: x["message_count"], reverse=True)
        return users[:limit]

    def get_user_activity_pattern(
        self, user_activity: dict[str, UserActivityStats], user_id: str
    ) -> UserActivityPattern:
        """获取并识别指定用户的活动模式。

        Args:
            user_activity: 用户活跃度聚合数据字典。
            user_id: 目标用户 ID。

        Returns:
            dict: 用户活动模式字典（包含峰值时段、夜间发言比例、小时分布等）。
        """
        if user_id not in user_activity:
            return {}

        stats = user_activity[user_id]
        hours = stats["hours"]

        # 找出最活跃的时间段
        most_active_hour = max(hours.items(), key=lambda x: x[1])[0] if hours else 0

        # 计算夜间活跃度 (0-6点)
        night_messages = sum(hours[h] for h in range(6))
        night_ratio = (
            night_messages / stats["message_count"] if stats["message_count"] > 0 else 0
        )

        return {
            "most_active_hour": most_active_hour,
            "night_ratio": night_ratio,
            "hourly_distribution": dict(hours),
        }
