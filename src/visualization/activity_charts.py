"""
群聊活跃度可视化模块
参考 astrbot_plugin_github_analyzer 的实现方式
"""

from datetime import datetime
from collections import defaultdict
from ..models.data_models import ActivityVisualization


class ActivityVisualizer:
    """活跃度可视化器"""

    def __init__(self):
        pass

    def generate_activity_visualization(
        self, messages: list[dict]
    ) -> ActivityVisualization:
        """生成活跃度可视化数据 - 专注于小时级别分析"""
        hourly_activity = defaultdict(int)
        user_activity = defaultdict(int)
        emoji_activity = defaultdict(int)  # 每小时表情统计

        # 分析消息数据
        for msg in messages:
            # 时间分析 - 只关注小时
            msg_time = datetime.fromtimestamp(msg.get("time", 0))
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
            for content in msg.get("message", []):
                if content.get("type") in ["face", "mface", "bface", "sface"]:
                    emoji_activity[hour] += 1
                elif content.get("type") == "image":
                    data = content.get("data", {})
                    summary = data.get("summary", "")
                    if "动画表情" in summary or "表情" in summary:
                        emoji_activity[hour] += 1

        # 生成用户活跃度排行
        user_ranking = []
        for user_id, data in user_activity.items():
            user_ranking.append(
                {
                    "user_id": user_id,
                    "nickname": data["nickname"],
                    "message_count": data["count"],
                }
            )
        user_ranking.sort(key=lambda x: x["message_count"], reverse=True)

        # 找出高峰时段（活跃度最高的3个小时）
        peak_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)[
            :3
        ]
        peak_hours = [{"hour": hour, "count": count} for hour, count in peak_hours]

        return ActivityVisualization(
            hourly_activity=dict(hourly_activity),
            daily_activity={},  # 不使用日期分析
            user_activity_ranking=user_ranking[:10],  # 前10名
            peak_hours=peak_hours,
            activity_heatmap_data=self._generate_hourly_heatmap_data(
                hourly_activity, emoji_activity
            ),
        )

    def _generate_hourly_heatmap_data(
        self, hourly_activity: dict, emoji_activity: dict
    ) -> dict:
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

    def _calculate_activity_levels(self, hourly_activity: dict) -> dict:
        """计算活跃度等级"""
        if not hourly_activity:
            return {}

        max_count = max(hourly_activity.values())
        levels = {}

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

    def generate_hourly_chart_html(self, hourly_activity: dict) -> str:
        """生成每小时活动分布的HTML图表（手账风格）"""
        html_parts = []
        max_activity = max(hourly_activity.values()) if hourly_activity else 1

        # 定义颜色映射 - 根据活跃度等级使用不同颜色
        color_vars = {
            "high": "var(--accent-orange)",  # 高活跃度 - 橙色
            "medium": "var(--color-green)",  # 中活跃度 - 绿色
            "low": "var(--color-blue)",  # 低活跃度 - 蓝色
            "inactive": "var(--color-purple)",  # 无活动 - 紫色
        }

        for hour in range(24):
            count = hourly_activity.get(hour, 0)
            percentage = (count / max_activity) * 100 if max_activity > 0 else 0

            # 确定活跃度等级和颜色
            if count == 0:
                color = color_vars["inactive"]
                width = "2%"  # 无活动时显示很细的线，避免占满整行
            elif percentage >= 70:
                color = color_vars["high"]
                width = f"{percentage}%"
            elif percentage >= 30:
                color = color_vars["medium"]
                width = f"{percentage}%"
            else:
                color = color_vars["low"]
                width = f"{percentage}%"

            # 生成手账风格的图表行
            html_segment = f"""
            <div class="hand-chart-row">
                <div class="chart-label">{hour:02d}:00</div>
                <div class="chart-bar-box">
                    <div class="crayon-bar" style="width: {width}; background: {color};"></div>
                </div>
                <div style="margin-left: 10px; font-size: 0.7rem; font-family: var(--font-hand); color: var(--ink-secondary); min-width: 30px;">{count}</div>
            </div>
            """
            html_parts.append(html_segment)

        return "".join(html_parts)
