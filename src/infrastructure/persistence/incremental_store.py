"""
增量分析状态持久化存储 - 基础设施持久化层

负责增量分析状态的存储和读取。
使用 AstrBot 的 put_kv_data/get_kv_data 实现，
每个群聊每天对应一个独立的状态键。

键格式: incremental_state_{group_id}_{date_str}
"""

import datetime
from typing import Any

from ...domain.entities.incremental_state import IncrementalState
from ...utils.logger import logger


class IncrementalStore:
    """
    增量分析状态持久化仓储

    该类封装了增量分析状态在 KV 存储中的读写操作。
    每个群组每天的增量状态独立存储，支持创建、读取、更新和删除。

    使用方式与 HistoryManager 一致，依赖 star_instance 提供的
    put_kv_data / get_kv_data 异步接口。
    """

    # KV 存储键前缀
    KEY_PREFIX = "incremental_state"

    def __init__(self, star_instance: Any):
        """
        初始化增量状态仓储。

        Args:
            star_instance: Star 插件实例，用于访问底层 KV 存储引擎
        """
        self.plugin = star_instance

    def _build_key(self, group_id: str, date_str: str | None = None) -> str:
        """
        构建 KV 存储键。

        Args:
            group_id: 群组 ID
            date_str: 日期字符串 (YYYY-MM-DD)，缺省为当天

        Returns:
            str: 格式为 "incremental_state_{group_id}_{date_str}" 的键
        """
        if not date_str:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        return f"{self.KEY_PREFIX}_{group_id}_{date_str}"

    async def get_state(
        self, group_id: str, date_str: str | None = None
    ) -> IncrementalState | None:
        """
        读取指定群组在指定日期的增量分析状态。

        Args:
            group_id: 群组 ID
            date_str: 日期字符串 (YYYY-MM-DD)，缺省为当天

        Returns:
            IncrementalState | None: 状态实例，不存在则返回 None
        """
        if not date_str:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        key = self._build_key(group_id, date_str)

        try:
            data = await self.plugin.get_kv_data(key, None)
            if data is None:
                return None

            state = IncrementalState.from_dict(data)
            logger.debug(f"已读取群 {group_id} 在 {date_str} 的增量状态 (Key: {key})")
            return state
        except Exception as e:
            logger.error(f"读取增量状态失败 (Key: {key}): {e}", exc_info=True)
            return None

    async def save_state(self, state: IncrementalState) -> bool:
        """
        持久化增量分析状态。

        将状态序列化为字典后写入 KV 存储。
        如果已存在同键数据则覆盖更新。

        Args:
            state: 要保存的增量分析状态实例

        Returns:
            bool: 保存是否成功
        """
        key = self._build_key(state.group_id, state.date_str)

        try:
            data = state.to_dict()
            await self.plugin.put_kv_data(key, data)
            logger.debug(
                f"已保存群 {state.group_id} 在 {state.date_str} 的增量状态 "
                f"(Key: {key}, 批次数: {state.total_analysis_count})"
            )
            return True
        except Exception as e:
            logger.error(f"保存增量状态失败 (Key: {key}): {e}", exc_info=True)
            return False

    async def get_or_create_state(
        self, group_id: str, date_str: str | None = None
    ) -> IncrementalState:
        """
        获取或创建增量分析状态。

        如果指定群组在指定日期已有状态则返回现有状态，
        否则创建一个新的空白状态实例（不自动持久化）。

        Args:
            group_id: 群组 ID
            date_str: 日期字符串 (YYYY-MM-DD)，缺省为当天

        Returns:
            IncrementalState: 现有或新创建的状态实例
        """
        if not date_str:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        existing = await self.get_state(group_id, date_str)
        if existing is not None:
            return existing

        # 创建新的空白状态
        new_state = IncrementalState(
            group_id=group_id,
            date_str=date_str,
        )
        logger.info(f"为群 {group_id} 创建了 {date_str} 的新增量状态")
        return new_state

    async def delete_state(
        self, group_id: str, date_str: str | None = None
    ) -> bool:
        """
        删除指定群组在指定日期的增量分析状态。

        通过将键值设为 None 来实现删除效果。

        Args:
            group_id: 群组 ID
            date_str: 日期字符串 (YYYY-MM-DD)，缺省为当天

        Returns:
            bool: 删除是否成功
        """
        if not date_str:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        key = self._build_key(group_id, date_str)

        try:
            await self.plugin.put_kv_data(key, None)
            logger.info(f"已删除群 {group_id} 在 {date_str} 的增量状态 (Key: {key})")
            return True
        except Exception as e:
            logger.error(f"删除增量状态失败 (Key: {key}): {e}", exc_info=True)
            return False

    async def has_state(
        self, group_id: str, date_str: str | None = None
    ) -> bool:
        """
        判断指定群组在指定日期是否存在增量分析状态。

        Args:
            group_id: 群组 ID
            date_str: 日期字符串 (YYYY-MM-DD)，缺省为当天

        Returns:
            bool: 是否存在状态
        """
        state = await self.get_state(group_id, date_str)
        return state is not None
