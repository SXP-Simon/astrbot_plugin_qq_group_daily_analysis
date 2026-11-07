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

from __future__ import annotations

import asyncio
import base64
import json
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast

from ...domain.entities.incremental_state import (
    IncrementalBatch,
    IncrementalBatchPage,
    IncrementalBatchPayload,
)
from ...domain.repositories.persistence_repository import IIncrementalStore
from ...domain.value_objects.group_session import GroupSession
from ...shared.type_guards import is_object_list, is_string_mapping
from ...utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.star import Star

    from .kv_contracts import KeyValueWriter


class BatchIndexEntry(TypedDict):
    """持久化批次索引条目，读取时验证身份和时间戳。"""

    batch_id: str
    timestamp: float
    last_message_timestamp: NotRequired[int]


class IncrementalStore(IIncrementalStore):
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

    plugin: Star

    def __init__(
        self,
        star_instance: Star,
        *,
        _scope: GroupSession | None = None,
        _root: IncrementalStore | None = None,
    ) -> None:
        """
        初始化批次持久化仓储。

        Args:
            star_instance: Star 插件实例，用于访问底层 KV 存储引擎。
            _scope: 仅由 for_session 创建的会话身份。
            _root: 共享注册表锁和迁移锁的根仓储。
        """
        self.plugin = star_instance
        self._scope = _scope
        self._root = _root or self
        self._migration_locks: dict[str, asyncio.Lock] = (
            _root._migration_locks if _root else {}
        )
        self._registry_lock = _root._registry_lock if _root else asyncio.Lock()

    async def _register_group(self, group_id: str) -> bool:
        """在同一仓储实例的并发任务间完整更新注册表。

        Args:
            group_id: 当前会话中的群号。

        Returns:
            注册成功返回真，失败时由调用方决定是否中止迁移。
        """
        try:
            async with self._registry_lock:
                key = (
                    "incr_tracked_sessions_v2"
                    if self._scope
                    else self.GROUPS_REGISTRY_KEY
                )
                raw = await self.plugin.get_kv_data(key, [])
                if self._scope:
                    sessions: set[GroupSession] = set()
                    for item in raw if is_object_list(raw) else []:
                        if (
                            is_string_mapping(item)
                            and isinstance(item.get("group_id"), str)
                            and isinstance(item.get("platform_id"), str)
                        ):
                            sessions.add(
                                GroupSession(
                                    str(item["platform_id"]), str(item["group_id"])
                                )
                            )
                    if self._scope in sessions:
                        return True
                    sessions.add(self._scope)
                    await cast("KeyValueWriter", self.plugin).put_kv_data(
                        key,
                        [
                            {"group_id": item.group_id, "platform_id": item.platform_id}
                            for item in sorted(sessions)
                        ],
                    )
                else:
                    groups = (
                        {str(item) for item in raw}
                        if is_object_list(raw)
                        else set[str]()
                    )
                    if group_id in groups:
                        return True
                    groups.add(group_id)
                    await cast("KeyValueWriter", self.plugin).put_kv_data(
                        key, sorted(groups)
                    )
            return True
        except Exception as exc:
            logger.debug(f"注册增量会话记录失败: {exc}")
            return False

    def _legacy_owner_key(self, group_id: str) -> str:
        """构造旧数据一次归属标记，编码防止任意群号混淆键空间。"""
        return (
            "incr_legacy_owner_" + base64.urlsafe_b64encode(group_id.encode()).decode()
        )

    def _group_namespace(self, group_id: str) -> str:
        """会话字段分别编码，避免拼接分隔符导致碰撞。"""
        if self._scope is None:
            return group_id
        if self._scope.group_id != group_id:
            raise ValueError("增量仓储会话与目标群号不一致")
        encoded = json.dumps(
            [self._scope.platform_id, group_id],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(encoded).decode()

    async def _assert_scope(self, group_id: str) -> None:
        """已归属的数据不能继续通过未指定平台的旧入口访问。"""
        if self._scope:
            self._group_namespace(group_id)
        elif await self.plugin.get_kv_data(self._legacy_owner_key(group_id), None):
            raise ValueError("该群的增量数据已按平台隔离，请指定平台会话")

    async def for_session(self, group_id: str, platform_id: str) -> IIncrementalStore:
        """绑定会话并一次接管旧数据，原始键保留为迁移备份。

        Args:
            group_id: 平台内原始群号。
            platform_id: AstrBot 平台实例标识，空值仅访问尚未归属的旧数据。

        Returns:
            只能操作指定群号的会话仓储，或未归属旧数据仓储。

        Raises:
            ValueError: 群号为空、旧批次身份错误或数据缺失。
            RuntimeError: 会话目录注册失败，可重试修复目录。
        """
        root = self._root
        if not group_id:
            raise ValueError("增量会话缺少群号")
        if not platform_id:
            await root._assert_scope(group_id)
            return root
        scoped = IncrementalStore(
            root.plugin, _scope=GroupSession(platform_id, group_id), _root=root
        )
        async with root._migration_locks.setdefault(group_id, asyncio.Lock()):
            owner = cast(
                "object",
                await root.plugin.get_kv_data(root._legacy_owner_key(group_id), None),
            )
            if not owner:
                index = await root._get_index(group_id, strict=True)
                # 复制完整后提交归属；后续注册失败可重试，但其他平台不能再次领取旧数据。
                for entry in index:
                    raw = await root.plugin.get_kv_data(
                        root._batch_key(group_id, entry["batch_id"]), None
                    )
                    if raw is None:
                        raise ValueError("旧增量批次缺失，迁移未完成，请检查原始数据")
                    batch = IncrementalBatch.from_dict(raw)
                    if (
                        batch.group_id != group_id
                        or batch.batch_id != entry["batch_id"]
                    ):
                        raise ValueError("旧增量批次身份不一致，迁移未完成")
                    await cast("KeyValueWriter", root.plugin).put_kv_data(
                        scoped._batch_key(group_id, batch.batch_id), batch.to_dict()
                    )
                await scoped._save_index(group_id, index)
                cursor = await root.plugin.get_kv_data(root._last_ts_key(group_id), 0)
                await cast("KeyValueWriter", root.plugin).put_kv_data(
                    scoped._last_ts_key(group_id), cursor
                )
            if not owner:
                await cast("KeyValueWriter", root.plugin).put_kv_data(
                    root._legacy_owner_key(group_id), platform_id
                )
            if not await scoped._register_group(group_id):
                raise RuntimeError("增量会话目录暂时无法保存，请重试；已复制的数据保留")
        return scoped

    async def get_tracked_sessions(self) -> list[GroupSession]:
        """列出新会话及尚未归属的旧群号。

        Returns:
            去重会话身份列表，不将同号的多个平台合并。
        """
        sessions: set[GroupSession] = set()
        raw = await self.plugin.get_kv_data("incr_tracked_sessions_v2", [])
        for item in raw if is_object_list(raw) else []:
            if (
                is_string_mapping(item)
                and isinstance(item.get("group_id"), str)
                and isinstance(item.get("platform_id"), str)
            ):
                sessions.add(
                    GroupSession(str(item["platform_id"]), str(item["group_id"]))
                )
        for group_id in await self.get_tracked_groups():
            owner = cast(
                "object",
                await self.plugin.get_kv_data(self._legacy_owner_key(group_id), None),
            )
            sessions.add(
                GroupSession(owner if isinstance(owner, str) else "", group_id)
            )
        return sorted(sessions)

    async def get_tracked_groups(self) -> list[str]:
        """获取所有记录过增量状态/批次的群号列表"""
        try:
            groups_data = await self.plugin.get_kv_data(self.GROUPS_REGISTRY_KEY, [])
            return (
                sorted({str(g) for g in groups_data})
                if is_object_list(groups_data)
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
        return f"{'v2_' if self._scope else ''}{self.INDEX_PREFIX}_{self._group_namespace(group_id)}"

    def _batch_key(self, group_id: str, batch_id: str) -> str:
        """构建单个批次数据键"""
        return f"{'v2_' if self._scope else ''}{self.BATCH_PREFIX}_{self._group_namespace(group_id)}_{batch_id}"

    def _last_ts_key(self, group_id: str) -> str:
        """构建最后分析消息时间戳键"""
        return f"{'v2_' if self._scope else ''}{self.LAST_TS_PREFIX}_{self._group_namespace(group_id)}"

    # ================================================================
    # 批次索引操作
    # ================================================================

    async def _get_index(
        self, group_id: str, *, strict: bool = False
    ) -> list[BatchIndexEntry]:
        """
        获取指定群的批次索引列表。

        Args:
            group_id: 群组 ID。
            strict: 迁移时拒绝读失败或不完整索引，避免误把旧数据当成空数据。

        Returns:
            list[BatchIndexEntry]: 索引条目列表，每项包含 batch_id 和 timestamp
        """
        await self._assert_scope(group_id)
        key = self._index_key(group_id)
        try:
            data = await self.plugin.get_kv_data(key, default=[])
            if strict and not is_object_list(data):
                raise ValueError("旧增量索引格式错误，迁移未完成")
            entries: list[BatchIndexEntry] = []
            for item in data if is_object_list(data) else []:
                if not is_string_mapping(item):
                    if strict:
                        raise ValueError("旧增量索引条目格式错误，迁移未完成")
                    continue
                batch_id, timestamp = item.get("batch_id"), item.get("timestamp", 0)
                if isinstance(batch_id, str) and isinstance(timestamp, (int, float)):
                    entries.append(
                        {"batch_id": batch_id, "timestamp": float(timestamp)}
                    )
                    last_message = item.get("last_message_timestamp")
                    if isinstance(last_message, int) and not isinstance(
                        last_message, bool
                    ):
                        entries[-1]["last_message_timestamp"] = last_message
                elif strict:
                    raise ValueError("旧增量索引条目缺少批次身份，迁移未完成")
            return entries
        except Exception as e:
            if strict:
                raise
            logger.error(f"读取批次索引失败 (Key: {key}): {e}", exc_info=True)
            return []

    async def _save_index(self, group_id: str, index: list[BatchIndexEntry]) -> None:
        """
        保存批次索引列表。

        Args:
            group_id: 群组 ID
            index: 索引条目列表
        """
        key = self._index_key(group_id)
        try:
            await cast("KeyValueWriter", self.plugin).put_kv_data(key, index)
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
        await self._assert_scope(group_id)
        batch_key = self._batch_key(group_id, batch.batch_id)

        try:
            # 1. 保存批次数据
            await cast("KeyValueWriter", self.plugin).put_kv_data(
                batch_key, batch.to_dict()
            )

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
                        "last_message_timestamp": batch.last_message_timestamp,
                    }
                )
            else:
                existing_entry["timestamp"] = batch.timestamp
                existing_entry["last_message_timestamp"] = batch.last_message_timestamp
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
            最后分析时间戳及边界消息 ID；未保存过游标时返回零和空集合。

        Raises:
            RuntimeError: 游标存储读取失败或数据损坏，停止分析以免重算历史消息。
        """
        await self._assert_scope(group_id)
        key = self._last_ts_key(group_id)
        try:
            data = await self.plugin.get_kv_data(key, 0)
            message_ids: set[str] = set()
            if is_string_mapping(data):
                raw_timestamp = data.get("timestamp")
                raw_ids = data.get("message_ids")
                if not is_object_list(raw_ids):
                    raise ValueError("增量游标缺少有效的边界消息 ID 列表")
                for item in raw_ids:
                    if (
                        isinstance(item, bool)
                        or not isinstance(item, (str, int))
                        or not str(item).strip()
                    ):
                        raise ValueError("增量游标包含无效的边界消息 ID")
                    message_ids.add(str(item))
            else:
                raw_timestamp = data
            if isinstance(raw_timestamp, bool) or not isinstance(
                raw_timestamp, (str, int, float)
            ):
                raise ValueError("增量游标时间戳必须是非负整数")
            timestamp = int(raw_timestamp)
            if timestamp < 0 or (
                isinstance(raw_timestamp, float) and not raw_timestamp.is_integer()
            ):
                raise ValueError("增量游标时间戳必须是非负整数")
            return timestamp, message_ids
        except Exception as e:
            logger.error(f"读取最后分析游标失败 (Key: {key}): {e}", exc_info=True)
            raise RuntimeError(
                "无法读取增量分析进度，本次分析已停止。请检查存储或游标数据后重试。"
            ) from e

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
        await self._assert_scope(group_id)
        key = self._last_ts_key(group_id)
        try:
            await cast("KeyValueWriter", self.plugin).put_kv_data(
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
        await self._assert_scope(group_id)
        batch_key = self._batch_key(group_id, batch_id)
        try:
            data = await self.plugin.get_kv_data(batch_key, default=None)
            if is_string_mapping(data) and data:
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
            await cast("KeyValueWriter", self.plugin).put_kv_data(batch_key, None)
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
                    await cast("KeyValueWriter", self.plugin).put_kv_data(
                        self._batch_key(group_id, b_id), None
                    )

            # 清空索引与游标
            await self._save_index(group_id, [])
            await cast("KeyValueWriter", self.plugin).put_kv_data(
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
        expired: list[BatchIndexEntry] = []
        retained: list[BatchIndexEntry] = []
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
                await cast("KeyValueWriter", self.plugin).put_kv_data(batch_key, None)
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

    async def get_all_batch_summaries(self, group_id: str) -> list[BatchIndexEntry]:
        """
        获取指定群所有批次的摘要信息（不加载完整数据）。

        用于状态查询命令展示批次概览。

        Args:
            group_id: 群组 ID。
            strict: 迁移时拒绝读失败或不完整索引，避免误把旧数据当成空数据。

        Returns:
            list[BatchIndexEntry]: 批次摘要列表，按时间升序
        """
        index = await self._get_index(group_id)
        # 按时间戳升序排列
        index.sort(key=lambda x: x.get("timestamp", 0))
        return index

    async def list_batch_page(
        self, group_id: str, page: int = 1, page_size: int = 20
    ) -> IncrementalBatchPage:
        """按索引分页后读取内容，不加载其他页的完整批次。

        Args:
            group_id: 群组 ID。
            page: 从 1 开始的页码，越界时收敛到最后一页。
            page_size: 每页数量，限制在 1 至 100。

        Returns:
            当前页与索引总数。旧索引缺少消息时间时返回未知，不全量读取补算。
        """
        page_size = min(100, max(1, page_size))
        index = await self._get_index(group_id)
        index.sort(
            key=lambda entry: (entry["timestamp"], entry["batch_id"]), reverse=True
        )
        total = len(index)
        page = min(max(1, page), max(1, (total + page_size - 1) // page_size))
        items: list[IncrementalBatchPayload] = []
        for entry in index[(page - 1) * page_size : page * page_size]:
            batch = await self.get_batch_detail(group_id, entry["batch_id"])
            if batch is None:
                # 并发删除或失效索引不能冒充完整的一页。
                raise ValueError("批次记录已变化或缺失，请刷新后重试")
            items.append(
                {
                    "batch_id": batch.batch_id,
                    "group_id": batch.group_id,
                    "timestamp": batch.timestamp,
                    "last_message_timestamp": batch.last_message_timestamp,
                    "messages_count": batch.messages_count,
                    "characters_count": batch.characters_count,
                    "topics": [
                        {"topic": topic.get("topic", "")} for topic in batch.topics
                    ],
                    "token_usage": batch.token_usage,
                }
            )
        latest = (
            max((entry.get("last_message_timestamp", 0) for entry in index), default=0)
            if all("last_message_timestamp" in entry for entry in index)
            else None
        )
        return IncrementalBatchPage(items, total, page, page_size, latest)
