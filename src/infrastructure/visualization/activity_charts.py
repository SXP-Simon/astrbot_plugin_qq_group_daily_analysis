"""
群聊活跃度可视化模块
参考 astrbot_plugin_github_analyzer 的实现方式
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime

from ...domain.models.data_models import ActivityVisualization


class ActivityVisualizer:
    """活跃度可视化器"""

    def __init__(self) -> None:
        pass

    def generate_activity_visualization(
        self, messages: Sequence[Mapping[str, object]]
    ) -> ActivityVisualization:
        """生成活跃度可视化数据 - 专注于小时级别分析"""
        hourly_activity: defaultdict[int, int] = defaultdict(int)
        user_activity: dict[str, dict[str, object]] = {}
        emoji_activity: defaultdict[int, int] = defaultdict(int)  # 每小时表情统计

        # 分析消息数据
        for msg in messages:
            # 时间分析 - 只关注小时
            msg_time = datetime.fromtimestamp(self._to_int(msg.get("time", 0)))
            hour = msg_time.hour

            # # 用户分析
            # sender = msg.get("sender", {})
            # user_id = str(sender.get("user_id", ""))
            # nickname = InfoUtils.get_user_nickname(self.config_manager, sender)

            # 统计每小时消息数
            hourly_activity[hour] += 1

            # # 统计用户活跃度
            # user_activity[user_id] = {
            #     "nickname": nickname,
            #     "count": user_activity.get(user_id, {}).get("count", 0) + 1
            # }

            # 统计每小时表情数
            raw_message = msg.get("message", [])
            if not isinstance(raw_message, list):
                continue
            for content in raw_message:
                if not isinstance(content, Mapping):
                    continue
                if str(content.get("type", "")) in ["face", "mface", "bface", "sface"]:
                    emoji_activity[hour] += 1
                elif str(content.get("type", "")) == "image":
                    raw_data = content.get("data")
                    if not isinstance(raw_data, Mapping):
                        continue
                    summary = str(raw_data.get("summary", ""))
                    if "动画表情" in summary or "表情" in summary:
                        emoji_activity[hour] += 1

        # 生成用户活跃度排行
        user_ranking: list[dict[str, object]] = []
        for user_id, data in user_activity.items():
            user_ranking.append(
                {
                    "user_id": user_id,
                    "nickname": str(data.get("nickname", "")),
                    "message_count": self._to_int(data.get("count", 0)),
                }
            )
        user_ranking.sort(key=self._user_ranking_key, reverse=True)

        # 找出高峰时段（活跃度最高的3个小时）
        peak_hours = [
            hour
            for hour, _count in sorted(
                hourly_activity.items(),
                key=self._hourly_count_sort_key,
                reverse=True,
            )[:3]
        ]

        return ActivityVisualization(
            hourly_activity=dict(hourly_activity),
            daily_activity={},  # 不使用日期分析
            user_activity_ranking=user_ranking[:10],  # 前10名
            peak_hours=peak_hours,
            activity_heatmap_data=self._generate_hourly_heatmap_data(
                hourly_activity, emoji_activity
            ),
        )

    @staticmethod
    def _to_int(value: object) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                return 0
        return 0

    def _user_ranking_key(self, item: Mapping[str, object]) -> int:
        return self._to_int(item.get("message_count", 0))

    @staticmethod
    def _hourly_count_sort_key(item: tuple[int, int]) -> int:
        return item[1]

    def _generate_hourly_heatmap_data(
        self, hourly_activity: Mapping[int, int], emoji_activity: Mapping[int, int]
    ) -> dict[str, object]:
        """生成小时级热力图数据"""
        # 计算活跃度等级
        max_hourly = max(hourly_activity.values()) if hourly_activity else 1
        max_emoji = max(emoji_activity.values()) if emoji_activity else 1

        return {
            "hourly_max": max_hourly,
            "emoji_max": max_emoji,
            "hourly_normalized": {
                hour: (count / max_hourly) * 100
                for hour, count in hourly_activity.items()
            },
            "emoji_normalized": {
                hour: (emoji_activity.get(hour, 0) / max_emoji) * 100
                for hour in range(24)
            },
            "activity_levels": self._calculate_activity_levels(hourly_activity),
        }

    def _calculate_activity_levels(
        self, hourly_activity: Mapping[int, int]
    ) -> dict[int, str]:
        """计算活跃度等级"""
        if not hourly_activity:
            return {}

        max_count = max(hourly_activity.values())
        levels: dict[int, str] = {}

        for hour in range(24):
            count = hourly_activity.get(hour, 0)
            if count == 0:
                level = "inactive"
            elif count <= max_count * 0.3:
                level = "low"
            elif count <= max_count * 0.7:
                level = "medium"
            else:
                level = "high"
            levels[hour] = level

        return levels

    def get_hourly_chart_data(
        self, hourly_activity: Mapping[int, int]
    ) -> list[dict[str, int | float]]:
        """生成每小时活动分布的数据"""
        chart_data: list[dict[str, int | float]] = []
        max_activity = max(hourly_activity.values()) if hourly_activity else 1

        for hour in range(24):
            count = hourly_activity.get(hour, 0)
            percentage = (count / max_activity) * 100 if max_activity > 0 else 0

            chart_data.append(
                {"hour": hour, "count": count, "percentage": round(percentage, 1)}
            )

        return chart_data
