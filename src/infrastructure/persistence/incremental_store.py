"""
增量分析批次持久化存储 — 滑动窗口架构

基于 AstrBot 的 put_kv_data/get_kv_data 实现按批次独立存储，
支持按时间窗口查询批次、批次索引管理和过期批次清理。

KV 键设计：
- 批次索引: incr_batch_index_{group_id}
  值: [{"batch_id": "xxx", "timestamp": 1234567890.0}, ...]
- 批次数据: incr_batch_{group_id}_{batch_id}
  值: IncrementalBatch.to_dict()
- 最后分析消息游标: incr_last_ts_{group_id}
  值: {"timestamp": 1234567890, "message_ids": ["..."]}
"""

from typing import Any

from ...domain.entities.incremental_state import IncrementalBatch
from ...utils.logger import logger


class IncrementalStore:
    """
    增量分析批次持久化仓储

    核心职责：
    - save_batch: 保存单个批次数据并更新索引
    - query_batches: 按时间窗口查询批次列表
    - get_last_analyzed_cursor / update_last_analyzed_cursor: 跨批次去重
    - cleanup_old_batches: 清理过期批次
    - get_batch_count: 获取当前批次总数（状态查询用）
    """

    # KV 键前缀
    INDEX_PREFIX = "incr_batch_index"
    BATCH_PREFIX = "incr_batch"
    LAST_TS_PREFIX = "incr_last_ts"
    GROUPS_REGISTRY_KEY = "incr_tracked_groups"

    def __init__(self, star_instance: Any):
        """
        初始化批次持久化仓储。

        Args:
            star_instance: Star 插件实例，用于访问底层 KV 存储引擎
        """
        self.plugin = star_instance

    async def _register_group(self, group_id: str) -> None:
        """记录拥有增量数据的群号到全局注册表"""
        try:
            groups_data = await self.plugin.get_kv_data(self.GROUPS_REGISTRY_KEY, [])
            current_groups = (
                set(groups_data) if isinstance(groups_data, list) else set()
            )
            if group_id not in current_groups:
                current_groups.add(str(group_id))
                await self.plugin.put_kv_data(
                    self.GROUPS_REGISTRY_KEY, sorted(current_groups)
                )
        except Exception as e:
            logger.debug(f"注册增量群组记录异常: {e}")

    async def get_tracked_groups(self) -> list[str]:
        """获取所有记录过增量状态/批次的群号列表"""
        try:
            groups_data = await self.plugin.get_kv_data(self.GROUPS_REGISTRY_KEY, [])
            return (
                sorted({str(g) for g in groups_data})
                if isinstance(groups_data, list)
                else []
            )
        except Exception as e:
            logger.error(f"读取增量群组注册表失败: {e}")
            return []

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
            existing_entry = next(
                (entry for entry in index if entry.get("batch_id") == batch.batch_id),
                None,
            )
            if existing_entry is None:
                index.append(
                    {
                        "batch_id": batch.batch_id,
                        "timestamp": batch.timestamp,
                    }
                )
            else:
                existing_entry["timestamp"] = batch.timestamp
            await self._save_index(group_id, index)
            await self._register_group(group_id)

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
            entry
            for entry in index
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
    # 最后分析消息游标（跨批次去重用）
    # ================================================================

    async def get_last_analyzed_cursor(self, group_id: str) -> tuple[int, set[str]]:
        """获取指定群的最后分析消息游标。

        旧版本仅保存整数时间戳，此处会将其兼容为不含消息 ID 的游标。

        Args:
            group_id: 群组 ID。

        Returns:
            最后分析时间戳，以及该时间戳下已经处理的消息 ID 集合。
        """
        key = self._last_ts_key(group_id)
        try:
            data = await self.plugin.get_kv_data(key, 0)
            if isinstance(data, dict):
                timestamp = max(0, int(data.get("timestamp", 0)))
                message_ids = data.get("message_ids", [])
                if not isinstance(message_ids, list):
                    message_ids = []
                return timestamp, {str(item) for item in message_ids if str(item)}
            return (int(data) if data else 0), set()
        except Exception as e:
            logger.error(f"读取最后分析游标失败 (Key: {key}): {e}", exc_info=True)
            return 0, set()

    async def update_last_analyzed_cursor(
        self,
        group_id: str,
        timestamp: int,
        message_ids: set[str],
    ) -> None:
        """更新指定群的最后分析消息游标。

        Args:
            group_id: 群组 ID。
            timestamp: 最后分析消息的 epoch 时间戳。
            message_ids: 该时间戳下已经处理的消息 ID。
        """
        key = self._last_ts_key(group_id)
        try:
            await self.plugin.put_kv_data(
                key,
                {
                    "timestamp": max(0, int(timestamp)),
                    "message_ids": sorted(
                        str(item) for item in message_ids if str(item)
                    ),
                },
            )
            await self._register_group(group_id)
            logger.debug(f"更新最后分析游标: 群 {group_id}, ts={timestamp}")
        except Exception as e:
            logger.error(f"更新最后分析游标失败 (Key: {key}): {e}", exc_info=True)
            raise

    # ================================================================
    # 过期批次清理与单点删除 / 重置
    # ================================================================

    async def get_batch_detail(
        self, group_id: str, batch_id: str
    ) -> IncrementalBatch | None:
        """读取单条增量批次完整数据。

        Args:
            group_id: 群组 ID。
            batch_id: 批次唯一 ID。

        Returns:
            IncrementalBatch | None: 完整批次实体，不存在时返回 None。
        """
        batch_key = self._batch_key(group_id, batch_id)
        try:
            data = await self.plugin.get_kv_data(batch_key, None)
            if data is not None and isinstance(data, dict):
                return IncrementalBatch.from_dict(data)
            return None
        except Exception as e:
            logger.error(
                f"加载批次详情失败 (群 {group_id}, 批次 {batch_id[:8]}...): {e}",
                exc_info=True,
            )
            return None

    async def delete_batch(self, group_id: str, batch_id: str) -> bool:
        """单点删除指定增量批次并更新索引。

        Args:
            group_id: 群组 ID。
            batch_id: 批次唯一 ID。

        Returns:
            bool: 是否成功删除。
        """
        try:
            index = await self._get_index(group_id)
            retained = [e for e in index if e.get("batch_id") != batch_id]
            if len(retained) == len(index):
                return False

            await self._save_index(group_id, retained)
            batch_key = self._batch_key(group_id, batch_id)
            await self.plugin.put_kv_data(batch_key, None)
            logger.info(f"已删除增量批次: 群 {group_id}, 批次 {batch_id}")
            return True
        except Exception as e:
            logger.error(
                f"删除批次失败 (群 {group_id}, 批次 {batch_id}): {e}", exc_info=True
            )
            return False

    async def reset_group(self, group_id: str) -> int:
        """一键清空指定群的所有增量批次数据并将分析游标归零。

        Args:
            group_id: 群组 ID。

        Returns:
            int: 已删除的批次总数。
        """
        try:
            index = await self._get_index(group_id)
            count = len(index)
            for entry in index:
                b_id = entry.get("batch_id")
                if b_id:
                    await self.plugin.put_kv_data(self._batch_key(group_id, b_id), None)

            # 清空索引与游标
            await self._save_index(group_id, [])
            await self.plugin.put_kv_data(
                self._last_ts_key(group_id),
                {"timestamp": 0, "message_ids": []},
            )
            logger.info(
                f"已重置群 {group_id} 的全部增量批次数据与游标 (共清理 {count} 条批次)"
            )
            return count
        except Exception as e:
            logger.error(f"重置群增量数据失败 (群 {group_id}): {e}", exc_info=True)
            return 0

    async def cleanup_old_batches(self, group_id: str, before_timestamp: float) -> int:
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

        logger.debug(
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

    async def get_all_batch_summaries(self, group_id: str) -> list[dict]:
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

    async def get_all_batches_with_details(self, group_id: str) -> list[dict[str, Any]]:
        """获取指定群所有批次的概览详情列表（包含话题标签与基本指标）。

        Args:
            group_id: 群组 ID。

        Returns:
            list[dict[str, Any]]: 批次卡片展示用字典列表。
        """
        index = await self._get_index(group_id)
        index.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        results: list[dict[str, Any]] = []
        for entry in index:
            batch_id = entry.get("batch_id")
            if not batch_id:
                continue
            batch = await self.get_batch_detail(group_id, batch_id)
            if batch:
                topics_summary = []
                for t in batch.topics:
                    if isinstance(t, dict):
                        topics_summary.append(
                            {
                                "topic": t.get("topic", ""),
                                "contributors": t.get("contributors", []),
                            }
                        )
                    else:
                        topics_summary.append(
                            {
                                "topic": getattr(t, "topic", ""),
                                "contributors": getattr(t, "contributors", []),
                            }
                        )

                token_dict = (
                    batch.token_usage
                    if isinstance(batch.token_usage, dict)
                    else {
                        "prompt_tokens": getattr(batch.token_usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(
                            batch.token_usage, "completion_tokens", 0
                        ),
                        "total_tokens": getattr(batch.token_usage, "total_tokens", 0),
                    }
                )

                participants_cnt = (
                    len(batch.participant_ids)
                    if batch.participant_ids
                    else len(batch.user_stats)
                )

                results.append(
                    {
                        "batch_id": batch.batch_id,
                        "group_id": batch.group_id,
                        "timestamp": batch.timestamp,
                        "messages_count": batch.messages_count,
                        "characters_count": batch.characters_count,
                        "topics": topics_summary,
                        "participants_count": participants_cnt,
                        "token_usage": token_dict,
                    }
                )
            else:
                results.append(
                    {
                        "batch_id": batch_id,
                        "group_id": group_id,
                        "timestamp": entry.get("timestamp", 0),
                        "messages_count": 0,
                        "characters_count": 0,
                        "topics": [],
                        "participants_count": 0,
                        "token_usage": {"total_tokens": 0},
                    }
                )
        return results
