"""
统计分析模块
负责用户活跃度分析和其他统计功能
"""

from collections import defaultdict
from datetime import datetime

from .utils import InfoUtils


import re


class UserAnalyzer:
    """用户分析器"""

    # Discord 自定义表情正则 <:name:id> 或 <a:name:id>
    DISCORD_CUSTOM_EMOJI_PATTERN = r"<a?:.+?:\d+>"

    # 简单的 Unicode Emoji 正则范围 (覆盖大多数常见 Emoji)
    UNICODE_EMOJI_PATTERN = (
        r"[\U0001F000-\U0001F9FF]|[\U00002600-\U000026FF]|[\U00002700-\U000027BF]"
    )

    def __init__(self, config_manager):
        self.config_manager = config_manager

    def analyze_users(self, messages: list[dict]) -> dict[str, dict]:
        """分析用户活跃度"""
        # 获取机器人QQ号列表用于过滤
        bot_qq_ids = self.config_manager.get_bot_qq_ids()

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

        for msg in messages:
            sender = msg.get("sender", {})
            user_id = str(sender.get("user_id", ""))

            # 跳过机器人自己的消息，避免进入统计
            if bot_qq_ids and user_id in [str(qq) for qq in bot_qq_ids]:
                continue

            nickname = InfoUtils.get_user_nickname(self.config_manager, sender)

            user_stats[user_id]["message_count"] += 1
            user_stats[user_id]["nickname"] = nickname

            # 统计时间分布
            msg_time = datetime.fromtimestamp(msg.get("time", 0))
            user_stats[user_id]["hours"][msg_time.hour] += 1

            # 处理消息内容
            for content in msg.get("message", []):
                if content.get("type") == "text":
                    text = content.get("data", {}).get("text", "")
                    user_stats[user_id]["char_count"] += len(text)

                    # 统计文本中的 Discord 自定义表情
                    discord_emojis = re.findall(self.DISCORD_CUSTOM_EMOJI_PATTERN, text)
                    user_stats[user_id]["emoji_count"] += len(discord_emojis)

                    # 统计文本中的 Unicode Emoji
                    unicode_emojis = re.findall(self.UNICODE_EMOJI_PATTERN, text)
                    user_stats[user_id]["emoji_count"] += len(unicode_emojis)

                elif content.get("type") == "face":
                    # QQ基础表情
                    user_stats[user_id]["emoji_count"] += 1
                elif content.get("type") == "mface":
                    # 动画表情/魔法表情
                    user_stats[user_id]["emoji_count"] += 1
                elif content.get("type") == "bface":
                    # 超级表情
                    user_stats[user_id]["emoji_count"] += 1
                elif content.get("type") == "sface":
                    # 小表情
                    user_stats[user_id]["emoji_count"] += 1
                elif content.get("type") == "image":
                    # 检查是否是动画表情（通过summary字段判断）
                    data = content.get("data", {})
                    summary = data.get("summary", "")
                    if "动画表情" in summary or "表情" in summary:
                        # 动画表情（以image形式发送）
                        user_stats[user_id]["emoji_count"] += 1
                elif content.get("type") == "reply":
                    user_stats[user_id]["reply_count"] += 1

        return dict(user_stats)

    def get_top_users(
        self, user_analysis: dict[str, dict], limit: int = 10
    ) -> list[dict]:
        """获取最活跃的用户"""
        # 获取机器人QQ号列表用于过滤
        bot_qq_ids = self.config_manager.get_bot_qq_ids()

        users = []
        for user_id, stats in user_analysis.items():
            # 过滤机器人自己
            if bot_qq_ids and str(user_id) in [str(qq) for qq in bot_qq_ids]:
                continue

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
        self, user_analysis: dict[str, dict], user_id: str
    ) -> dict:
        """获取用户活动模式"""
        if user_id not in user_analysis:
            return {}

        stats = user_analysis[user_id]
        hours = stats["hours"]

        # 找出最活跃的时间段
        most_active_hour = max(hours.items(), key=lambda x: x[1])[0] if hours else 0

        # 计算夜间活跃度
        night_messages = sum(hours[h] for h in range(0, 6))
        night_ratio = (
            night_messages / stats["message_count"] if stats["message_count"] > 0 else 0
        )

        return {
            "most_active_hour": most_active_hour,
            "night_ratio": night_ratio,
            "hourly_distribution": dict(hours),
        }
