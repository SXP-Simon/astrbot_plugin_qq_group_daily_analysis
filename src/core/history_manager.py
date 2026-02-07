"""
历史记录管理器模块
负责存储和查询群聊分析报告的摘要信息
使用 AstrBot 的 put_kv_data/get_kv_data 实现
"""

import datetime
from typing import Any

from astrbot.api import logger


class HistoryManager:
    """历史分析记录管理器"""

    def __init__(self, star_instance):
        """
        初始化历史记录管理器

        Args:
            star_instance: Star 插件实例，用于访问 put_kv_data/get_kv_data
        """
        self.plugin = star_instance

    async def save_analysis(
        self,
        group_id: str,
        analysis_result: dict[str, Any],
        date_str: str | None = None,
        time_str: str | None = None,
    ) -> bool:
        """
        保存分析结果摘要到历史记录

        Args:
            group_id: 群组ID
            analysis_result: 分析结果对象
            date_str: 日期字符串 (格式: YYYY-MM-DD)，如果不提供则使用当前日期
            time_str: 时间字符串 (格式: HH-MM)，如果不提供则使用当前时间
        """
        try:
            now = datetime.datetime.now()
            if not date_str:
                date_str = now.strftime("%Y-%m-%d")
            if not time_str:
                time_str = now.strftime("%H-%M")

            # 格式化 time_str，确保文件名/Key 安全 (替换 : 为 -)
            time_str = time_str.replace(":", "-")

            # 提取摘要数据
            stats = analysis_result.get("statistics")
            topics = analysis_result.get("topics", [])
            user_titles = analysis_result.get("user_titles", [])

            summary = {
                "message_count": getattr(stats, "message_count", 0) if stats else 0,
                "participant_count": getattr(stats, "participant_count", 0)
                if stats
                else 0,
                "topics": [{"topic": t.topic, "detail": t.detail} for t in topics],
                "user_titles_count": len(user_titles),
                "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            key = f"analysis_{group_id}_{date_str}_{time_str}"
            await self.plugin.put_kv_data(key, summary)

            logger.info(
                f"已保存群 {group_id} 在 {date_str} {time_str} 的分析摘要到历史记录 (Key: {key})"
            )
            return True
        except Exception as e:
            logger.error(f"保存历史分析记录失败: {e}", exc_info=True)
            return False

    async def get_history(
        self, group_id: str, date_str: str, time_str: str
    ) -> dict[str, Any] | None:
        """
        获取指定日期、时间点和群组的分析摘要

        Args:
            group_id: 群组ID
            date_str: 日期字符串 (YYYY-MM-DD)
            time_str: 时间字符串 (HH-MM)
        """
        # 确保格式统一
        time_str = time_str.replace(":", "-")
        key = f"analysis_{group_id}_{date_str}_{time_str}"
        return await self.plugin.get_kv_data(key, None)

    async def has_history(self, group_id: str, date_str: str, time_str: str) -> bool:
        """
        检查指定日期、时间点和群组是否已有分析记录

        Args:
            group_id: 群组ID
            date_str: 日期字符串 (YYYY-MM-DD)
            time_str: 时间字符串 (HH-MM)
        """
        history = await self.get_history(group_id, date_str, time_str)
        return history is not None
