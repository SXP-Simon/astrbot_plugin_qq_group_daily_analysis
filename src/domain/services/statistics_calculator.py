"""
Statistics Calculator - Domain service for computing chat statistics

This service calculates various statistics from unified messages.
It is platform-agnostic and works with the domain value objects.
"""

from datetime import datetime
from typing import Dict, List, Optional

from ..value_objects import UnifiedMessage
from ..value_objects.statistics import (
    GroupStatistics,
    UserStatistics,
    EmojiStatistics,
    ActivityVisualization,
    TokenUsage,
)


class StatisticsCalculator:
    """
    Domain service for calculating group chat statistics.

    This service processes UnifiedMessage objects and produces
    platform-agnostic statistics.
    """

    def __init__(self, bot_user_ids: Optional[List[str]] = None):
        """
        Initialize the statistics calculator.

        Args:
            bot_user_ids: List of bot user IDs to filter out from statistics
        """
        self.bot_user_ids = set(bot_user_ids or [])

    def calculate_group_statistics(
        self,
        messages: List[UnifiedMessage],
        token_usage: Optional[TokenUsage] = None,
    ) -> GroupStatistics:
        """
        Calculate comprehensive group statistics from messages.

        Args:
            messages: List of unified messages to analyze
            token_usage: Optional token usage from LLM analysis

        Returns:
            GroupStatistics object with computed statistics
        """
        if not messages:
            return GroupStatistics()

        # Filter out bot messages
        filtered_messages = [
            msg for msg in messages if msg.sender_id not in self.bot_user_ids
        ]

        if not filtered_messages:
            return GroupStatistics()

        # Calculate basic statistics
        message_count = len(filtered_messages)
        total_characters = sum(len(msg.text_content) for msg in filtered_messages)
        unique_senders = set(msg.sender_id for msg in filtered_messages)
        participant_count = len(unique_senders)

        # Calculate emoji statistics
        emoji_stats = self._calculate_emoji_statistics(filtered_messages)

        # Calculate activity visualization
        activity_viz = self._calculate_activity_visualization(filtered_messages)

        # Determine most active period
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
        self, messages: List[UnifiedMessage]
    ) -> Dict[str, UserStatistics]:
        """
        Calculate per-user statistics from messages.

        Args:
            messages: List of unified messages to analyze

        Returns:
            Dictionary mapping user_id to UserStatistics
        """
        user_stats: Dict[str, UserStatistics] = {}

        for msg in messages:
            # Skip bot messages
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

            # Count replies
            if msg.reply_to_id:
                stats.reply_count += 1

            # Track hourly activity
            hour = msg.timestamp.hour
            stats.hours[hour] = stats.hours.get(hour, 0) + 1

        return user_stats

    def get_top_users(
        self,
        user_stats: Dict[str, UserStatistics],
        limit: int = 10,
        min_messages: int = 5,
    ) -> List[Dict]:
        """
        Get top users by message count.

        Args:
            user_stats: Dictionary of user statistics
            limit: Maximum number of users to return
            min_messages: Minimum messages required to be included

        Returns:
            List of top user dictionaries sorted by message count
        """
        eligible_users = [
            stats for stats in user_stats.values() if stats.message_count >= min_messages
        ]

        sorted_users = sorted(
            eligible_users, key=lambda x: x.message_count, reverse=True
        )

        return [
            {
                "user_id": u.user_id,
                "nickname": u.nickname,
                "name": u.nickname,  # Backward compatibility
                "message_count": u.message_count,
                "avg_chars": round(u.average_chars, 1),
                "emoji_ratio": round(u.emoji_ratio, 2),
                "night_ratio": round(u.night_ratio, 2),
                "reply_ratio": round(u.reply_ratio, 2),
            }
            for u in sorted_users[:limit]
        ]

    def _calculate_emoji_statistics(
        self, messages: List[UnifiedMessage]
    ) -> EmojiStatistics:
        """Calculate emoji usage statistics from messages."""
        standard_count = 0
        custom_count = 0
        animated_count = 0
        sticker_count = 0
        other_count = 0
        emoji_details: Dict[str, int] = {}

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
        self, messages: List[UnifiedMessage]
    ) -> ActivityVisualization:
        """Calculate activity visualization data from messages."""
        hourly: Dict[int, int] = {h: 0 for h in range(24)}
        daily: Dict[str, int] = {}
        user_counts: Dict[str, int] = {}

        for msg in messages:
            # Hourly activity
            hour = msg.timestamp.hour
            hourly[hour] += 1

            # Daily activity
            date_str = msg.timestamp.strftime("%Y-%m-%d")
            daily[date_str] = daily.get(date_str, 0) + 1

            # User activity
            user_counts[msg.sender_id] = user_counts.get(msg.sender_id, 0) + 1

        # Calculate peak hours (top 3)
        sorted_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [h for h, _ in sorted_hours[:3]]

        # User activity ranking
        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        user_ranking = [
            {"user_id": uid, "count": count} for uid, count in sorted_users[:20]
        ]

        return ActivityVisualization(
            hourly_activity=tuple(hourly.items()),
            daily_activity=tuple(daily.items()),
            user_activity_ranking=tuple(user_ranking),
            peak_hours=tuple(peak_hours),
            heatmap_data=tuple(),  # Can be extended for heatmap visualization
        )

    def _determine_most_active_period(
        self, activity: ActivityVisualization
    ) -> str:
        """Determine the most active time period description."""
        hourly = dict(activity.hourly_activity)

        if not hourly:
            return "Unknown"

        # Find peak hour
        peak_hour = max(hourly, key=hourly.get)

        # Categorize time periods
        if 6 <= peak_hour < 12:
            return "Morning (6:00-12:00)"
        elif 12 <= peak_hour < 18:
            return "Afternoon (12:00-18:00)"
        elif 18 <= peak_hour < 24:
            return "Evening (18:00-24:00)"
        else:
            return "Late Night (0:00-6:00)"
