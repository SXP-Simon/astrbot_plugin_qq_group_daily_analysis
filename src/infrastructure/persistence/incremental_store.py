"""
增量分析批次持久化存储 — 滑动窗口架构

基于 AstrBot 的 put_kv_data/get_kv_data 实现按批次独立存储，
支持按时间窗口查询批次、批次索引管理和过期批次清理。

KV 键设计：
- 批次索引: incr_batch_index_{group_id}
  值: [{"batch_id": "xxx", "timestamp": 1234567890.0}, ...]
- 批次数据: incr_batch_{group_id}_{batch_id}
  值: IncrementalBatch.to_dict()
- 最后分析消息时间戳: incr_last_ts_{group_id}
  值: int (epoch timestamp)
"""

import time
from typing import Any

from ...domain.entities.incremental_state import IncrementalBatch
from ...utils.logger import logger


class IncrementalStore:
    """
    增量分析批次持久化仓储

    核心职责：
    - save_batch: 保存单个批次数据并更新索引
    - query_batches: 按时间窗口查询批次列表
    - get_last_analyzed_timestamp / update_last_analyzed_timestamp: 跨批次去重
    - cleanup_old_batches: 清理过期批次
    - get_batch_count: 获取当前批次总数（状态查询用）
    """

    # KV 键前缀
    INDEX_PREFIX = "incr_batch_index"
    BATCH_PREFIX = "incr_batch"
    LAST_TS_PREFIX = "incr_last_ts"

    def __init__(self, star_instance: Any):
        """
        初始化批次持久化仓储。

        Args:
            star_instance: Star 插件实例，用于访问底层 KV 存储引擎
        """
        self.plugin = star_instance

    # ================================================================
    # 键构建
    # ================================================================

    def _index_key(self, group_id: str) -> str:
        """构建批次索引键"""
        return f"{self.INDEX_PREFIX}_{group_id}"

    def _batch_key(self, group_id: str, batch_id: str) -> str:
        """构建单个批次数据键"""
        return f"{self.BATCH_PREFIX}_{group_id}_{batch_id}"

    def _last_ts_key(self, group_id: str) -> str:
        """构建最后分析消息时间戳键"""
        return f"{self.LAST_TS_PREFIX}_{group_id}"

    # ================================================================
    # 批次索引操作
    # ================================================================

    async def _get_index(self, group_id: str) -> list[dict]:
        """
        获取指定群的批次索引列表。

        Args:
            group_id: 群组 ID

        Returns:
            list[dict]: 索引条目列表，每项包含 batch_id 和 timestamp
        """
        key = self._index_key(group_id)
        try:
            data = await self.plugin.get_kv_data(key, None)
            if data is None:
                return []
            if isinstance(data, list):
                return data
            logger.warning(f"批次索引数据格式异常 (Key: {key}): {type(data)}")
            return []
        except Exception as e:
            logger.error(f"读取批次索引失败 (Key: {key}): {e}", exc_info=True)
            return []

    async def _save_index(self, group_id: str, index: list[dict]) -> None:
        """
        保存批次索引列表。

        Args:
            group_id: 群组 ID
            index: 索引条目列表
        """
        key = self._index_key(group_id)
        try:
            await self.plugin.put_kv_data(key, index)
        except Exception as e:
            logger.error(f"保存批次索引失败 (Key: {key}): {e}", exc_info=True)
            raise

    # ================================================================
    # 批次数据操作
    # ================================================================

    async def save_batch(self, batch: IncrementalBatch) -> bool:
        """
        保存单个批次数据并更新索引。

        流程：
        1. 将批次数据写入独立 KV 键
        2. 将批次元数据（batch_id + timestamp）追加到索引

        Args:
            batch: 要保存的增量分析批次

        Returns:
            bool: 保存是否成功
        """
        group_id = batch.group_id
        batch_key = self._batch_key(group_id, batch.batch_id)

        try:
            # 1. 保存批次数据
            await self.plugin.put_kv_data(batch_key, batch.to_dict())

            # 2. 更新索引
            index = await self._get_index(group_id)
            index.append({
                "batch_id": batch.batch_id,
                "timestamp": batch.timestamp,
            })
            await self._save_index(group_id, index)

            logger.debug(
                f"已保存批次 {batch.batch_id[:8]}... "
                f"(群 {group_id}, 消息数={batch.messages_count})"
            )
            return True
        except Exception as e:
            logger.error(
                f"保存批次失败 (群 {group_id}, 批次 {batch.batch_id[:8]}...): {e}",
                exc_info=True,
            )
            return False

    async def query_batches(
        self,
        group_id: str,
        window_start: float,
        window_end: float,
    ) -> list[IncrementalBatch]:
        """
        按时间窗口查询批次列表。

        从索引中筛选时间戳落在 [window_start, window_end] 范围内的批次，
        逐个加载完整批次数据。

        Args:
            group_id: 群组 ID
            window_start: 窗口起始时间戳（epoch）
            window_end: 窗口结束时间戳（epoch）

        Returns:
            list[IncrementalBatch]: 符合窗口范围的批次列表，按时间戳升序
        """
        index = await self._get_index(group_id)

        # 筛选在窗口范围内的批次
        matching_entries = [
            entry for entry in index
            if window_start <= entry.get("timestamp", 0) <= window_end
        ]

        # 按时间戳升序排列
        matching_entries.sort(key=lambda x: x.get("timestamp", 0))

        batches: list[IncrementalBatch] = []
        for entry in matching_entries:
            batch_id = entry.get("batch_id", "")
            if not batch_id:
                continue

            batch_key = self._batch_key(group_id, batch_id)
            try:
                data = await self.plugin.get_kv_data(batch_key, None)
                if data is not None:
                    batch = IncrementalBatch.from_dict(data)
                    batches.append(batch)
                else:
                    logger.warning(
                        f"批次数据缺失 (群 {group_id}, 批次 {batch_id[:8]}...)"
                    )
            except Exception as e:
                logger.error(
                    f"加载批次数据失败 (群 {group_id}, 批次 {batch_id[:8]}...): {e}",
                    exc_info=True,
                )

        logger.debug(
            f"窗口查询完成: 群 {group_id}, "
            f"窗口 [{window_start:.0f}, {window_end:.0f}], "
            f"匹配 {len(batches)}/{len(index)} 个批次"
        )

        return batches

    # ================================================================
    # 最后分析消息时间戳（跨批次去重用）
    # ================================================================

    async def get_last_analyzed_timestamp(self, group_id: str) -> int:
        """
        获取指定群的最后分析消息时间戳。

        用于增量分析时过滤已分析过的消息。

        Args:
            group_id: 群组 ID

        Returns:
            int: 最后分析消息的 epoch 时间戳，不存在则返回 0
        """
        key = self._last_ts_key(group_id)
        try:
            data = await self.plugin.get_kv_data(key, 0)
            return int(data) if data else 0
        except Exception as e:
            logger.error(f"读取最后分析时间戳失败 (Key: {key}): {e}", exc_info=True)
            return 0

    async def update_last_analyzed_timestamp(
        self, group_id: str, timestamp: int
    ) -> None:
        """
        更新指定群的最后分析消息时间戳。

        Args:
            group_id: 群组 ID
            timestamp: 最后分析消息的 epoch 时间戳
        """
        key = self._last_ts_key(group_id)
        try:
            await self.plugin.put_kv_data(key, timestamp)
            logger.debug(
                f"更新最后分析时间戳: 群 {group_id}, ts={timestamp}"
            )
        except Exception as e:
            logger.error(
                f"更新最后分析时间戳失败 (Key: {key}): {e}", exc_info=True
            )
            raise

    # ================================================================
    # 过期批次清理
    # ================================================================

    async def cleanup_old_batches(
        self, group_id: str, before_timestamp: float
    ) -> int:
        """
        清理指定群中早于给定时间戳的所有批次。

        流程：
        1. 从索引中分离出过期条目和保留条目
        2. 逐个删除过期批次的 KV 数据
        3. 用保留条目覆盖索引

        Args:
            group_id: 群组 ID
            before_timestamp: 清理此时间戳之前的所有批次

        Returns:
            int: 已清理的批次数量
        """
        index = await self._get_index(group_id)
        if not index:
            return 0

        # 分离过期和保留
        expired = []
        retained = []
        for entry in index:
            if entry.get("timestamp", 0) < before_timestamp:
                expired.append(entry)
            else:
                retained.append(entry)

        if not expired:
            return 0

        # 删除过期批次数据
        deleted_count = 0
        for entry in expired:
            batch_id = entry.get("batch_id", "")
            if not batch_id:
                continue
            batch_key = self._batch_key(group_id, batch_id)
            try:
                await self.plugin.put_kv_data(batch_key, None)
                deleted_count += 1
            except Exception as e:
                logger.error(
                    f"删除过期批次失败 (群 {group_id}, 批次 {batch_id[:8]}...): {e}",
                    exc_info=True,
                )

        # 更新索引（仅保留未过期条目）
        await self._save_index(group_id, retained)

        logger.info(
            f"清理过期批次: 群 {group_id}, "
            f"删除 {deleted_count} 个, 保留 {len(retained)} 个"
        )

        return deleted_count

    # ================================================================
    # 状态查询
    # ================================================================

    async def get_batch_count(self, group_id: str) -> int:
        """
        获取指定群的当前批次总数。

        Args:
            group_id: 群组 ID

        Returns:
            int: 批次总数
        """
        index = await self._get_index(group_id)
        return len(index)

    async def get_all_batch_summaries(
        self, group_id: str
    ) -> list[dict]:
        """
        获取指定群所有批次的摘要信息（不加载完整数据）。

        用于状态查询命令展示批次概览。

        Args:
            group_id: 群组 ID

        Returns:
            list[dict]: 批次摘要列表，按时间升序
        """
        index = await self._get_index(group_id)
        # 按时间戳升序排列
        index.sort(key=lambda x: x.get("timestamp", 0))
        return index

    # ================================================================
    # 旧版兼容（迁移期间使用）
    # ================================================================

    async def migrate_legacy_state(
        self, group_id: str, date_str: str
    ) -> bool:
        """
        尝试迁移旧版按天存储的 IncrementalState 到新批次架构。

        检查旧键 incremental_state_{group_id}_{date_str} 是否存在，
        如果存在则将其数据转换为一个 IncrementalBatch 并保存，
        然后删除旧键。

        Args:
            group_id: 群组 ID
            date_str: 日期字符串 (YYYY-MM-DD)

        Returns:
            bool: 是否成功迁移（True=迁移了数据，False=无需迁移或失败）
        """
        old_key = f"incremental_state_{group_id}_{date_str}"

        try:
            old_data = await self.plugin.get_kv_data(old_key, None)
            if old_data is None:
                return False

            logger.info(
                f"发现旧版增量状态 (群 {group_id}, 日期 {date_str})，开始迁移"
            )

            # 从旧数据中提取信息构建一个聚合批次
            batch = IncrementalBatch(
                group_id=group_id,
                timestamp=old_data.get("created_at", time.time()),
                messages_count=old_data.get("total_message_count", 0),
                characters_count=old_data.get("total_character_count", 0),
                hourly_msg_counts=old_data.get("hourly_message_counts", {}),
                hourly_char_counts=old_data.get("hourly_character_counts", {}),
                user_stats=old_data.get("user_activities", {}),
                emoji_stats=old_data.get("emoji_counts", {}),
                topics=old_data.get("topics", []),
                golden_quotes=old_data.get("golden_quotes", []),
                token_usage=old_data.get("total_token_usage", {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }),
                last_message_timestamp=old_data.get(
                    "last_analyzed_message_timestamp", 0
                ),
                participant_ids=list(
                    old_data.get("all_participant_ids", [])
                ),
            )

            # 保存为新批次
            saved = await self.save_batch(batch)
            if not saved:
                logger.error(f"旧版数据迁移保存失败 (群 {group_id})")
                return False

            # 迁移最后分析时间戳
            last_ts = old_data.get("last_analyzed_message_timestamp", 0)
            if last_ts > 0:
                await self.update_last_analyzed_timestamp(group_id, last_ts)

            # 删除旧键
            await self.plugin.put_kv_data(old_key, None)

            logger.info(
                f"旧版增量状态迁移完成 (群 {group_id}, 日期 {date_str}), "
                f"消息数={batch.messages_count}"
            )
            return True

        except Exception as e:
            logger.error(
                f"旧版增量状态迁移失败 (群 {group_id}): {e}", exc_info=True
            )
            return False
