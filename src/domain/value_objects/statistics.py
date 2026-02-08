"""
Statistics Value Objects - Platform-agnostic statistics representations

This module contains value objects for various statistics collected during
group chat analysis. All objects are immutable and platform-agnostic.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class TokenUsage:
    """
    Token usage statistics for LLM API calls.

    Immutable by design (frozen=True).

    Attributes:
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total tokens used
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "TokenUsage":
        """Create TokenUsage from dictionary."""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Add two TokenUsage objects together."""
        if not isinstance(other, TokenUsage):
            return NotImplemented
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass(frozen=True)
class EmojiStatistics:
    """
    Emoji usage statistics.

    Platform-agnostic representation of emoji usage in messages.
    Immutable by design (frozen=True).

    Attributes:
        standard_emoji_count: Standard unicode emoji count
        custom_emoji_count: Platform-specific custom emoji count
        animated_emoji_count: Animated emoji count
        sticker_count: Sticker count
        other_emoji_count: Other emoji types count
        emoji_details: Detailed breakdown by emoji ID/name
    """

    standard_emoji_count: int = 0
    custom_emoji_count: int = 0
    animated_emoji_count: int = 0
    sticker_count: int = 0
    other_emoji_count: int = 0
    emoji_details: tuple = field(default_factory=tuple)

    @property
    def total_count(self) -> int:
        """Get total emoji count."""
        return (
            self.standard_emoji_count
            + self.custom_emoji_count
            + self.animated_emoji_count
            + self.sticker_count
            + self.other_emoji_count
        )

    @classmethod
    def from_dict(cls, data: dict) -> "EmojiStatistics":
        """Create EmojiStatistics from dictionary."""
        details = data.get("face_details", data.get("emoji_details", {}))
        if isinstance(details, dict):
            details = tuple(details.items())

        return cls(
            standard_emoji_count=data.get("face_count", data.get("standard_emoji_count", 0)),
            custom_emoji_count=data.get("mface_count", data.get("custom_emoji_count", 0)),
            animated_emoji_count=data.get("bface_count", data.get("animated_emoji_count", 0)),
            sticker_count=data.get("sface_count", data.get("sticker_count", 0)),
            other_emoji_count=data.get("other_emoji_count", 0),
            emoji_details=details,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "standard_emoji_count": self.standard_emoji_count,
            "custom_emoji_count": self.custom_emoji_count,
            "animated_emoji_count": self.animated_emoji_count,
            "sticker_count": self.sticker_count,
            "other_emoji_count": self.other_emoji_count,
            "total_emoji_count": self.total_count,
            "emoji_details": dict(self.emoji_details),
            # Backward compatibility
            "face_count": self.standard_emoji_count,
            "mface_count": self.custom_emoji_count,
            "bface_count": self.animated_emoji_count,
            "sface_count": self.sticker_count,
        }


@dataclass(frozen=True)
class ActivityVisualization:
    """
    Activity visualization data.

    Platform-agnostic representation of chat activity patterns.
    Immutable by design (frozen=True).

    Attributes:
        hourly_activity: Message count by hour (0-23)
        daily_activity: Message count by date
        user_activity_ranking: Ranked list of user activity
        peak_hours: List of peak activity hours
        heatmap_data: Data for activity heatmap visualization
    """

    hourly_activity: tuple = field(default_factory=tuple)
    daily_activity: tuple = field(default_factory=tuple)
    user_activity_ranking: tuple = field(default_factory=tuple)
    peak_hours: tuple = field(default_factory=tuple)
    heatmap_data: tuple = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict) -> "ActivityVisualization":
        """Create ActivityVisualization from dictionary."""
        hourly = data.get("hourly_activity", {})
        daily = data.get("daily_activity", {})
        ranking = data.get("user_activity_ranking", [])
        peaks = data.get("peak_hours", [])
        heatmap = data.get("activity_heatmap_data", data.get("heatmap_data", {}))

        return cls(
            hourly_activity=tuple(hourly.items()) if isinstance(hourly, dict) else tuple(hourly),
            daily_activity=tuple(daily.items()) if isinstance(daily, dict) else tuple(daily),
            user_activity_ranking=tuple(ranking),
            peak_hours=tuple(peaks),
            heatmap_data=tuple(heatmap.items()) if isinstance(heatmap, dict) else tuple(heatmap),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hourly_activity": dict(self.hourly_activity),
            "daily_activity": dict(self.daily_activity),
            "user_activity_ranking": list(self.user_activity_ranking),
            "peak_hours": list(self.peak_hours),
            "activity_heatmap_data": dict(self.heatmap_data),
        }


@dataclass(frozen=True)
class GroupStatistics:
    """
    Comprehensive group chat statistics.

    Platform-agnostic representation of group chat statistics.
    Immutable by design (frozen=True).

    Attributes:
        message_count: Total number of messages
        total_characters: Total character count across all messages
        participant_count: Number of unique participants
        most_active_period: Description of the most active time period
        emoji_statistics: Emoji usage statistics
        activity_visualization: Activity pattern data
        token_usage: LLM token usage for analysis
    """

    message_count: int = 0
    total_characters: int = 0
    participant_count: int = 0
    most_active_period: str = ""
    emoji_statistics: EmojiStatistics = field(default_factory=EmojiStatistics)
    activity_visualization: ActivityVisualization = field(default_factory=ActivityVisualization)
    token_usage: TokenUsage = field(default_factory=TokenUsage)

    @property
    def average_message_length(self) -> float:
        """Calculate average message length."""
        if self.message_count == 0:
            return 0.0
        return self.total_characters / self.message_count

    @property
    def emoji_count(self) -> int:
        """Get total emoji count for backward compatibility."""
        return self.emoji_statistics.total_count

    @classmethod
    def from_dict(cls, data: dict) -> "GroupStatistics":
        """Create GroupStatistics from dictionary."""
        emoji_data = data.get("emoji_statistics", {})
        if not emoji_data:
            # Backward compatibility: construct from flat fields
            emoji_data = {
                "face_count": data.get("emoji_count", 0),
            }

        activity_data = data.get("activity_visualization", {})
        token_data = data.get("token_usage", {})

        return cls(
            message_count=data.get("message_count", 0),
            total_characters=data.get("total_characters", 0),
            participant_count=data.get("participant_count", 0),
            most_active_period=data.get("most_active_period", ""),
            emoji_statistics=EmojiStatistics.from_dict(emoji_data),
            activity_visualization=ActivityVisualization.from_dict(activity_data),
            token_usage=TokenUsage.from_dict(token_data),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "message_count": self.message_count,
            "total_characters": self.total_characters,
            "participant_count": self.participant_count,
            "most_active_period": self.most_active_period,
            "emoji_count": self.emoji_count,  # Backward compatibility
            "emoji_statistics": self.emoji_statistics.to_dict(),
            "activity_visualization": self.activity_visualization.to_dict(),
            "token_usage": self.token_usage.to_dict(),
        }


@dataclass
class UserStatistics:
    """
    Per-user statistics (mutable for accumulation during analysis).

    Attributes:
        user_id: Platform-agnostic user identifier
        nickname: User's display name
        message_count: Number of messages sent
        char_count: Total characters sent
        emoji_count: Number of emojis used
        reply_count: Number of replies made
        hours: Message count by hour (0-23)
    """

    user_id: str
    nickname: str = ""
    message_count: int = 0
    char_count: int = 0
    emoji_count: int = 0
    reply_count: int = 0
    hours: Dict[int, int] = field(default_factory=lambda: {h: 0 for h in range(24)})

    @property
    def average_chars(self) -> float:
        """Calculate average characters per message."""
        if self.message_count == 0:
            return 0.0
        return self.char_count / self.message_count

    @property
    def emoji_ratio(self) -> float:
        """Calculate emoji per message ratio."""
        if self.message_count == 0:
            return 0.0
        return self.emoji_count / self.message_count

    @property
    def night_ratio(self) -> float:
        """Calculate night activity ratio (0-6 hours)."""
        if self.message_count == 0:
            return 0.0
        night_messages = sum(self.hours.get(h, 0) for h in range(6))
        return night_messages / self.message_count

    @property
    def reply_ratio(self) -> float:
        """Calculate reply ratio."""
        if self.message_count == 0:
            return 0.0
        return self.reply_count / self.message_count

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "message_count": self.message_count,
            "char_count": self.char_count,
            "emoji_count": self.emoji_count,
            "reply_count": self.reply_count,
            "avg_chars": round(self.average_chars, 1),
            "emoji_ratio": round(self.emoji_ratio, 2),
            "night_ratio": round(self.night_ratio, 2),
            "reply_ratio": round(self.reply_ratio, 2),
            "hours": self.hours,
        }
