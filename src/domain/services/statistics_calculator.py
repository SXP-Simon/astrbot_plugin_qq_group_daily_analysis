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
    领域服务：统计计算器

    负责处理统一格式的消息流，并生成多维度的统计分析结果。

    Attributes:
        bot_user_ids (set[str]): 需要在统计中过滤掉的机器人 ID 集合
    """

    def __init__(self, bot_user_ids: list[str] | None = None):
        """
        初始化统计计算器。

        Args:
            bot_user_ids (list[str], optional): 机器人用户 ID 列表
        """
        self.bot_user_ids = set(bot_user_ids or [])

    def calculate_group_statistics(
        self,
        messages: list[UnifiedMessage],
        token_usage: TokenUsage | None = None,
    ) -> GroupStatistics:
        """
        根据一组消息计算综合群组统计数据。

        Args:
            messages (list[UnifiedMessage]): 待分析的消息列表
            token_usage (TokenUsage, optional): 关联的 LLM 令牌消耗

        Returns:
            GroupStatistics: 计算出的群组统计对象
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
        为每个独立用户计算详细的行为统计。

        Args:
            messages (list[UnifiedMessage]): 待分析的消息列表

        Returns:
            dict[str, UserStatistics]: 用户 ID 到统计对象的映射
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
            stats.emoji_count += msg.get_emoji_count()

            # 计算回复数
            if msg.reply_to_id:
                stats.reply_count += 1

            # 跟踪每小时活动
            hour = msg.get_datetime().hour
            stats.hours[hour] = stats.hours.get(hour, 0) + 1

        return user_stats

    def get_top_users(
        self,
        user_stats: dict[str, UserStatistics],
        limit: int = 10,
        min_messages: int = 5,
    ) -> list[dict]:
        """
        获取基于消息活跃度的前 N 名用户排行。

        Args:
            user_stats (dict[str, UserStatistics]): 用户统计映射
            limit (int): 返回的最大数量
            min_messages (int): 进入排行的最低消息门槛

        Returns:
            list[dict]: 排序后的用户摘要字典列表
        """
        eligible_users = [
            stats
            for stats in user_stats.values()
            if stats.message_count >= min_messages
        ]

        # 按消息数降序排序
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
        """
        内部方法：扫描消息流并汇总表情符号及贴纸的使用频次。

        Args:
            messages (list[UnifiedMessage]): 待扫描的消息列表

        Returns:
            EmojiStatistics: 包含标准表情、自定义表情、贴纸等分类计数的统计对象
        """
        standard_count = 0
        custom_count = 0
        animated_count = 0
        sticker_count = 0
        other_count = 0
        emoji_details: dict[str, int] = {}

        for msg in messages:
            for content in msg.contents:
                if content.is_emoji():
                    emoji_id = content.emoji_id or "unknown"
                    emoji_details[emoji_id] = emoji_details.get(emoji_id, 0) + 1

                    emoji_type = (
                        content.raw_data.get("emoji_type", "standard")
                        if isinstance(content.raw_data, dict)
                        else "standard"
                    )
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
        """
        内部方法：计算群组在时间轴（小时/日期）上的活跃分布。

        Args:
            messages (list[UnifiedMessage]): 消息列表

        Returns:
            ActivityVisualization: 包含 24 小时活跃分布、每日活跃趋势、峰值小时及用户排名的对象
        """
        hourly: dict[int, int] = dict.fromkeys(range(24), 0)
        daily: dict[str, int] = {}
        user_counts: dict[str, int] = {}

        for msg in messages:
            dt = msg.get_datetime()
            # 每小时活动
            hour = dt.hour
            hourly[hour] += 1

            # 每日活动
            date_str = dt.strftime("%Y-%m-%d")
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
            heatmap_data=(),
        )

    def _determine_most_active_period(self, activity: ActivityVisualization) -> str:
        """
        内部方法：根据 24 小时分布数据判定群组的最活跃时段文字描述。

        Args:
            activity (ActivityVisualization): 活跃分布数据

        Returns:
            str: 语义化的时间段描述 (如 '上午 (6:00-12:00)')
        """
        hourly = dict(activity.hourly_activity)

        if not hourly or all(count == 0 for count in hourly.values()):
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
