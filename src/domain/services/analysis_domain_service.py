"""
分析领域服务 - 领域层
负责用户维度的活跃度分析、发言习惯及活动模式识别。
"""

import re
from collections import defaultdict
from datetime import datetime

from ..value_objects.unified_message import MessageContentType, UnifiedMessage


class AnalysisDomainService:
    """分析领域服务 - 处理用户画像及行为分析"""

    # Discord 自定义表情正则 <:name:id> 或 <a:name:id>
    DISCORD_CUSTOM_EMOJI_PATTERN = r"<a?:.+?:\d+>"

    # 简单的 Unicode Emoji 正则范围
    UNICODE_EMOJI_PATTERN = (
        r"[\U0001F000-\U0001F9FF]|[\U00002600-\U000026FF]|[\U00002700-\U000027BF]"
    )

    def analyze_user_activity(
        self, messages: list[UnifiedMessage], bot_self_ids: list[str] = None
    ) -> dict[str, dict]:
        """
        分析用户活跃度。

        基于 UnifiedMessage 计算每个用户的发言数、字数、表情数等。
        """
        user_stats = defaultdict(
            lambda: {
                "message_count": 0,
                "char_count": 0,
                "emoji_count": 0,
                "nickname": "",
                "hours": defaultdict(int),
                "reply_count": 0,
            }
        )

        bot_ids = set(bot_self_ids or [])

        for msg in messages:
            user_id = msg.sender_id

            # 跳过机器人自己的消息
            if user_id in bot_ids:
                continue

            user_stats[user_id]["message_count"] += 1
            user_stats[user_id]["nickname"] = msg.sender_card or msg.sender_name

            # 统计时间分布
            msg_time = datetime.fromtimestamp(msg.timestamp)
            user_stats[user_id]["hours"][msg_time.hour] += 1

            # 统计内容
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    text = content.text or ""
                    user_stats[user_id]["char_count"] += len(text)

                    # 统计文本中的表情 (Discord/Unicode)
                    user_stats[user_id]["emoji_count"] += len(
                        re.findall(self.DISCORD_CUSTOM_EMOJI_PATTERN, text)
                    )
                    user_stats[user_id]["emoji_count"] += len(
                        re.findall(self.UNICODE_EMOJI_PATTERN, text)
                    )

                elif content.type == MessageContentType.EMOJI:
                    user_stats[user_id]["emoji_count"] += 1

                elif content.type == MessageContentType.REPLY:
                    user_stats[user_id]["reply_count"] += 1

        return dict(user_stats)

    def get_top_users(
        self, user_activity: dict[str, dict], limit: int = 10
    ) -> list[dict]:
        """获取最活跃的用户列表"""
        users = []
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
        self, user_activity: dict[str, dict], user_id: str
    ) -> dict:
        """获取并识别指定用户的活动模式"""
        if user_id not in user_activity:
            return {}

        stats = user_activity[user_id]
        hours = stats["hours"]

        # 找出最活跃的时间段
        most_active_hour = max(hours.items(), key=lambda x: x[1])[0] if hours else 0

        # 计算夜间活跃度 (0-6点)
        night_messages = sum(hours[h] for h in range(0, 6))
        night_ratio = (
            night_messages / stats["message_count"] if stats["message_count"] > 0 else 0
        )

        return {
            "most_active_hour": most_active_hour,
            "night_ratio": night_ratio,
            "hourly_distribution": dict(hours),
        }
