"""
统计计算器 - 计算聊天统计的领域服务

该服务从统一消息计算各种统计数据。
它是平台无关的，与领域值对象配合使用。
"""

from ..value_objects import UnifiedMessage
from ..value_objects.statistics import (
    ActivityVisualization,
    EmojiStatistics,
    GroupStatistics,
    TokenUsage,
    UserStatistics,
)


class StatisticsCalculator:
    """
    计算群聊统计的领域服务。

    该服务处理 UnifiedMessage 对象并生成
    平台无关的统计数据。
    """

    def __init__(self, bot_user_ids: list[str] | None = None):
        """
        初始化统计计算器。

        参数:
            bot_user_ids: 要从统计中过滤的机器人用户 ID 列表
        """
        self.bot_user_ids = set(bot_user_ids or [])

    def calculate_group_statistics(
        self,
        messages: list[UnifiedMessage],
        token_usage: TokenUsage | None = None,
    ) -> GroupStatistics:
        """
        从消息计算综合群组统计。

        参数:
            messages: 要分析的统一消息列表
            token_usage: LLM 分析的可选令牌使用量

        返回:
            包含计算统计的 GroupStatistics 对象
        """
        if not messages:
            return GroupStatistics()

        # 过滤机器人消息
        filtered_messages = [
            msg for msg in messages if msg.sender_id not in self.bot_user_ids
        ]

        if not filtered_messages:
            return GroupStatistics()

        # 计算基本统计
        message_count = len(filtered_messages)
        total_characters = sum(len(msg.text_content) for msg in filtered_messages)
        unique_senders = {msg.sender_id for msg in filtered_messages}
        participant_count = len(unique_senders)

        # 计算表情统计
        emoji_stats = self._calculate_emoji_statistics(filtered_messages)

        # 计算活动可视化
        activity_viz = self._calculate_activity_visualization(filtered_messages)

        # 确定最活跃时段
        most_active_period = self._determine_most_active_period(activity_viz)

        return GroupStatistics(
            message_count=message_count,
            total_characters=total_characters,
            participant_count=participant_count,
            most_active_period=most_active_period,
            emoji_statistics=emoji_stats,
            activity_visualization=activity_viz,
            token_usage=token_usage or TokenUsage(),
        )

    def calculate_user_statistics(
        self, messages: list[UnifiedMessage]
    ) -> dict[str, UserStatistics]:
        """
        从消息计算单用户统计。

        参数:
            messages: 要分析的统一消息列表

        返回:
            user_id 到 UserStatistics 的映射字典
        """
        user_stats: dict[str, UserStatistics] = {}

        for msg in messages:
            # 跳过机器人消息
            if msg.sender_id in self.bot_user_ids:
                continue

            user_id = msg.sender_id

            if user_id not in user_stats:
                user_stats[user_id] = UserStatistics(
                    user_id=user_id,
                    nickname=msg.sender_name,
                )

            stats = user_stats[user_id]
            stats.message_count += 1
            stats.char_count += len(msg.text_content)
            stats.emoji_count += msg.emoji_count

            # 计算回复数
            if msg.reply_to_id:
                stats.reply_count += 1

            # 跟踪每小时活动
            hour = msg.timestamp.hour
            stats.hours[hour] = stats.hours.get(hour, 0) + 1

        return user_stats

    def get_top_users(
        self,
        user_stats: dict[str, UserStatistics],
        limit: int = 10,
        min_messages: int = 5,
    ) -> list[dict]:
        """
        按消息数获取活跃用户排行。

        参数:
            user_stats: 用户统计字典
            limit: 返回的最大用户数
            min_messages: 被包含所需的最少消息数

        返回:
            按消息数排序的活跃用户字典列表
        """
        eligible_users = [
            stats
            for stats in user_stats.values()
            if stats.message_count >= min_messages
        ]

        sorted_users = sorted(
            eligible_users, key=lambda x: x.message_count, reverse=True
        )

        return [
            {
                "user_id": u.user_id,
                "nickname": u.nickname,
                "name": u.nickname,  # 向后兼容
                "message_count": u.message_count,
                "avg_chars": round(u.average_chars, 1),
                "emoji_ratio": round(u.emoji_ratio, 2),
                "night_ratio": round(u.night_ratio, 2),
                "reply_ratio": round(u.reply_ratio, 2),
            }
            for u in sorted_users[:limit]
        ]

    def _calculate_emoji_statistics(
        self, messages: list[UnifiedMessage]
    ) -> EmojiStatistics:
        """从消息计算表情使用统计。"""
        standard_count = 0
        custom_count = 0
        animated_count = 0
        sticker_count = 0
        other_count = 0
        emoji_details: dict[str, int] = {}

        for msg in messages:
            for content in msg.contents:
                if content.type.value == "emoji":
                    emoji_id = content.metadata.get("emoji_id", "unknown")
                    emoji_details[emoji_id] = emoji_details.get(emoji_id, 0) + 1

                    emoji_type = content.metadata.get("emoji_type", "standard")
                    if emoji_type == "standard":
                        standard_count += 1
                    elif emoji_type == "custom":
                        custom_count += 1
                    elif emoji_type == "animated":
                        animated_count += 1
                    elif emoji_type == "sticker":
                        sticker_count += 1
                    else:
                        other_count += 1

        return EmojiStatistics(
            standard_emoji_count=standard_count,
            custom_emoji_count=custom_count,
            animated_emoji_count=animated_count,
            sticker_count=sticker_count,
            other_emoji_count=other_count,
            emoji_details=tuple(emoji_details.items()),
        )

    def _calculate_activity_visualization(
        self, messages: list[UnifiedMessage]
    ) -> ActivityVisualization:
        """从消息计算活动可视化数据。"""
        hourly: dict[int, int] = dict.fromkeys(range(24), 0)
        daily: dict[str, int] = {}
        user_counts: dict[str, int] = {}

        for msg in messages:
            # 每小时活动
            hour = msg.timestamp.hour
            hourly[hour] += 1

            # 每日活动
            date_str = msg.timestamp.strftime("%Y-%m-%d")
            daily[date_str] = daily.get(date_str, 0) + 1

            # 用户活动
            user_counts[msg.sender_id] = user_counts.get(msg.sender_id, 0) + 1

        # 计算高峰时段（前 3 名）
        sorted_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [h for h, _ in sorted_hours[:3]]

        # 用户活跃度排名
        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        user_ranking = [
            {"user_id": uid, "count": count} for uid, count in sorted_users[:20]
        ]

        return ActivityVisualization(
            hourly_activity=tuple(hourly.items()),
            daily_activity=tuple(daily.items()),
            user_activity_ranking=tuple(user_ranking),
            peak_hours=tuple(peak_hours),
            heatmap_data=(),  # 可扩展用于热力图可视化
        )

    def _determine_most_active_period(self, activity: ActivityVisualization) -> str:
        """确定最活跃时间段描述。"""
        hourly = dict(activity.hourly_activity)

        if not hourly:
            return "未知"

        # 找到高峰时段
        peak_hour = max(hourly, key=hourly.get)

        # 分类时间段
        if 6 <= peak_hour < 12:
            return "上午 (6:00-12:00)"
        elif 12 <= peak_hour < 18:
            return "下午 (12:00-18:00)"
        elif 18 <= peak_hour < 24:
            return "晚间 (18:00-24:00)"
        else:
            return "深夜 (0:00-6:00)"
