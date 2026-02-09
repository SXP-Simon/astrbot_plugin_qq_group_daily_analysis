"""
统计领域服务 - 领域层
负责核心统计逻辑的计算，不依赖于具体的平台或基础设施。
"""

from collections import defaultdict
from datetime import datetime

from ...infrastructure.visualization.activity_charts import ActivityVisualizer
from ..models.data_models import EmojiStatistics, GroupStatistics, TokenUsage
from ..value_objects.unified_message import MessageContentType, UnifiedMessage


class StatisticsService:
    """统计服务 - 处理群聊数据的聚合统计"""

    def __init__(self):
        self.activity_visualizer = ActivityVisualizer()

    def calculate_group_statistics(
        self, messages: list[UnifiedMessage]
    ) -> GroupStatistics:
        """
        计算群组基础统计数据。

        基于统一消息格式(UnifiedMessage)进行计算，确保跨平台一致性。
        """
        total_chars = 0
        participants = set()
        hour_counts = defaultdict(int)
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
                    # 检查是否是动画表情（通过raw_data判断，如果适配器提供了）
                    if content.raw_data and (
                        "动画表情" in str(content.raw_data)
                        or "表情" in str(content.raw_data)
                    ):
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

        # 生成活跃度可视化数据
        # 注意：ActivityVisualizer 可能需要迁移以支持 UnifiedMessage
        # 目前先转换回 dict 以保持兼容性，或者之后重构它
        raw_msgs = self._convert_to_legacy_dict(messages)
        activity_visualization = (
            self.activity_visualizer.generate_activity_visualization(raw_msgs)
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

    def _convert_to_legacy_dict(self, messages: list[UnifiedMessage]) -> list[dict]:
        """内部辅助：将 UnifiedMessage 转换为 Legacy Dict 格式，用于兼容可视化组件"""
        legacy_list = []
        for msg in messages:
            legacy_list.append(
                {
                    "time": msg.timestamp,
                    "sender": {"user_id": msg.sender_id},
                    "message": [
                        {"type": "text", "data": {"text": msg.text_content or ""}}
                    ],
                }
            )
        return legacy_list
