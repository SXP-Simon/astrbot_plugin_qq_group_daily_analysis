"""
统计领域服务 - 领域层
负责核心统计逻辑的计算，不依赖于具体的平台或基础设施。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

from ..value_objects import EmojiStatistics, GroupStatistics, TokenUsage
from ..value_objects.unified_message import (
    MessageContentType,
    UnifiedMessage,
)

if TYPE_CHECKING:
    from ..repositories.visualization_repository import IActivityVisualizer


class StatisticsService:
    """统计服务 - 处理群聊数据的聚合统计"""

    activity_visualizer: IActivityVisualizer

    def __init__(self, activity_visualizer: IActivityVisualizer) -> None:
        """初始化统计领域服务。

        Args:
            activity_visualizer: 活跃度图表可视化生成器实现。
        """
        self.activity_visualizer = activity_visualizer

    def calculate_group_statistics(
        self, messages: list[UnifiedMessage]
    ) -> GroupStatistics:
        """计算群组基础统计数据。

        基于统一消息格式(UnifiedMessage)进行计算，确保跨平台一致性。

        Args:
            messages: 统一消息对象列表。

        Returns:
            GroupStatistics: 群聊基础统计与可视化数据模型。
        """
        total_chars = 0
        participants: set[str] = set()
        hour_counts: dict[int, int] = defaultdict(int)
        emoji_statistics = EmojiStatistics()

        for msg in messages:
            participants.add(msg.sender_id)

            # 统计时间分布
            msg_time = datetime.fromtimestamp(msg.timestamp)
            hour_counts[msg_time.hour] += 1

            # 处理消息内容
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    total_chars += len(content.text or "")
                elif content.type == MessageContentType.EMOJI:
                    emoji_statistics.face_count += 1
                    # 尝试保留原始表情详情（如果适配器提供了）
                    face_id = content.emoji_id or "unknown"
                    emoji_statistics.face_details[f"emoji_{face_id}"] = (
                        emoji_statistics.face_details.get(f"emoji_{face_id}", 0) + 1
                    )
                elif content.type == MessageContentType.IMAGE:
                    # 兼容识别“图片形态的表情”:
                    # 1) 优先使用 onebot sub_type=1 信号
                    # 2) 若无该字段，再回退到历史 summary 文本匹配
                    if content.is_emoji():
                        emoji_statistics.mface_count += 1
                elif content.type in (
                    MessageContentType.VOICE,
                    MessageContentType.VIDEO,
                ):
                    # 其他非文本类型统计（可选）
                    pass

        # 找出最活跃时段
        most_active_hour = (
            max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
        )
        most_active_period = (
            f"{most_active_hour:02d}:00-{(most_active_hour + 1) % 24:02d}:00"
        )

        # 图表直接使用统一消息，保留表情等结构化信息。
        activity_visualization = (
            self.activity_visualizer.generate_activity_visualization(messages)
        )

        return GroupStatistics(
            message_count=len(messages),
            total_characters=total_chars,
            participant_count=len(participants),
            most_active_period=most_active_period,
            golden_quotes=[],
            emoji_count=emoji_statistics.total_emoji_count,
            emoji_statistics=emoji_statistics,
            activity_visualization=activity_visualization,
            token_usage=TokenUsage(),
        )
