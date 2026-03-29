"""
历史记录管理器模块 - 基础设施持久化层
负责存储和查询群聊分析报告的摘要信息
使用 AstrBot 的 put_kv_data/get_kv_data 实现
"""

import datetime
from collections.abc import Mapping
from typing import Protocol, cast

from astrbot.core.utils.plugin_kv_store import SUPPORTED_VALUE_TYPES

from ...utils.logger import logger


class _KVStoreLike(Protocol):
    async def get_kv_data(self, key: str, default: object) -> object: ...
    async def put_kv_data(self, key: str, value: SUPPORTED_VALUE_TYPES) -> None: ...


class _StatsLike(Protocol):
    message_count: int
    participant_count: int


class _TopicLike(Protocol):
    topic: str
    detail: str


class HistoryManager:
    """
    核心组件：历史分析存档管理器

    该类负责将每日生成的群消息分析报告摘要持久化存储，并提供查询接口。
    底层基于 AstrBot 提供的 KV 存储能力（put_kv_data/get_kv_data），
    确保即使在 Bot 重启后也能回溯历史数据。
    """

    def __init__(self, star_instance: _KVStoreLike):
        """
        初始化历史记录管理器。

        Args:
            star_instance (object): Star 插件实例，用于访问底层持久化引擎
        """
        self.plugin: _KVStoreLike = star_instance

    async def save_analysis(
        self,
        group_id: str,
        analysis_result: Mapping[str, object],
        date_str: str | None = None,
        time_str: str | None = None,
    ) -> bool:
        """
        序列化并存储一份分析报告摘要。

        摘要包含：发言总量、人数、提取的主题摘要及生成时间，不包含完整的原始消息流。

        Args:
            group_id (str): 群组 ID
            analysis_result (Mapping[str, object]): 包含 statistics, topics, user_titles 的完整分析对象
            date_str (str, optional): 归档日期 (YYYY-MM-DD)，缺省为当天
            time_str (str, optional): 归档时间点 (HH-MM)，缺省为当前时刻

        Returns:
            bool: 存储是否成功
        """
        try:
            now = datetime.datetime.now()
            if not date_str:
                date_str = now.strftime("%Y-%m-%d")
            if not time_str:
                time_str = now.strftime("%H-%M")

            # 消解非法字符，确保 Key 兼容性
            time_str = time_str.replace(":", "-")

            # 从分析结果中剥离非持久化字段，提取核心统计元数据
            stats = analysis_result.get("statistics")
            topics_raw = analysis_result.get("topics")
            topics: list[object] = (
                list(topics_raw) if isinstance(topics_raw, list) else []
            )
            user_titles_raw = analysis_result.get("user_titles")
            user_titles: list[object] = (
                list(user_titles_raw) if isinstance(user_titles_raw, list) else []
            )
            typed_stats = cast(_StatsLike, stats) if stats is not None else None

            topics_summary: list[dict[str, object]] = []
            for topic in topics:
                if not hasattr(topic, "topic") or not hasattr(topic, "detail"):
                    continue
                topic_obj = cast(_TopicLike, topic)
                topics_summary.append(
                    {"topic": topic_obj.topic, "detail": topic_obj.detail}
                )

            summary: dict[str, object] = {
                "message_count": typed_stats.message_count if typed_stats else 0,
                "participant_count": typed_stats.participant_count
                if typed_stats
                else 0,
                "topics": topics_summary,
                "user_titles_count": len(user_titles),
                "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
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
    ) -> dict[str, object] | None:
        """
        根据群组、日期和时间点检索一份历史摘要。
        """
        time_str = time_str.replace(":", "-")
        key = f"analysis_{group_id}_{date_str}_{time_str}"
        history = await self.plugin.get_kv_data(key, None)
        return history if isinstance(history, dict) else None

    async def has_history(self, group_id: str, date_str: str, time_str: str) -> bool:
        """
        快速判定是否存在指定时间点的历史分析记录。
        """
        history = await self.get_history(group_id, date_str, time_str)
        return history is not None
