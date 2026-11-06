from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import TYPE_CHECKING

from ...infrastructure.persistence.astrbot_history_writer import AstrBotHistoryWriter
from ...infrastructure.platform.astrbot_event_reader import AstrBotEventReader
from ...utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from astrbot.api.star import Context

    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.persistence.event_deduplication_store import (
        EventDeduplicationStore,
    )
    from ...infrastructure.persistence.platform_group_registry import (
        PlatformGroupRegistry,
    )


class MessageProcessingService:
    """消息处理服务。

    委托接入层解析群消息事件并持久化历史记录，
    维护事件驱动平台（Telegram、Satori、QQ 官方等）的群组注册表，
    并提供跨平台两阶段预占锁与持久化缓存的事件幂等去重防线。

    职责：
    1. 调用事件接入器获取明确消息字段
    2. 检查群聊持久化范围
    3. 存储消息历史（统一携带原生 message_id）
    4. 维护群组注册表，供调度器做群组发现（Telegram、QQ 官方等事件驱动平台）
    5. 多平台事件消息两阶段去重（按 platform_id:group_id:message_id 预占 + 确认机制 + 本地持久化预热）
    """

    group_registry: PlatformGroupRegistry
    dedup_store: EventDeduplicationStore | None
    config_manager: ConfigManager | None
    _seen_event_ids: OrderedDict[str, None]
    _inflight_event_ids: set[str]
    _seen_event_ids_limit: int

    def __init__(
        self,
        context: Context,
        group_registry: PlatformGroupRegistry,
        dedup_store: EventDeduplicationStore | None = None,
        config_manager: ConfigManager | None = None,
    ) -> None:
        """初始化消息处理服务。

        Args:
            context: AstrBot 核心上下文对象。
            group_registry: 事件驱动平台群组注册表。
            dedup_store: 可选的本地持久化事件去重仓储（用于重启记忆恢复）。
            config_manager: 可选的配置管理器（用于动态获取保留消息上限）。
        """
        self.history_writer = AstrBotHistoryWriter(context, config_manager)
        self.event_reader = AstrBotEventReader()
        self.group_registry = group_registry
        self.dedup_store = dedup_store
        self.config_manager = config_manager
        self._seen_event_ids = OrderedDict()
        self._inflight_event_ids = set()
        self._seen_event_ids_limit = 4096
        if self.dedup_store is not None:
            for key in self.dedup_store.load_recent_keys(self._seen_event_ids_limit):
                self._seen_event_ids[key] = None

    async def process_message(self, event: AstrMessageEvent) -> bool:
        """处理并在历史记录中存储消息。

        被 main.py 的 Satori、Telegram 与 QQ 官方消息拦截器共同调用。

        Args:
            event: AstrBot 消息事件

        Returns:
            bool: 若成功存储返回 True；若为重复消息跳过存储则返回 False。

        Raises:
            ValueError: 当群组 ID、发送者 ID 或平台 ID 无法获取时。
            RuntimeError: 当解析出的消息内容为空时。
        """
        incoming = self.event_reader.read(event)
        group_id, platform_id = incoming.group_id, incoming.platform_id
        sender_id, sender_name = incoming.sender_id, incoming.sender_name
        event_message_id, platform_name = incoming.message_id, incoming.platform_name
        if (
            self.config_manager is not None
            and self.config_manager.get_persist_only_allowed_groups()
            and not self.config_manager.is_group_allowed(incoming.umo)
        ):
            logger.debug("[%s] 群 %s 未启用分析，跳过消息存储", platform_id, group_id)
            return False
        if not incoming.has_content:
            raise RuntimeError(
                f"群 {group_id}: 消息内容为空 (sender={sender_name})，拒绝存储"
            )

        reserved_event_id = False
        dedup_key = ""
        if event_message_id:
            dedup_key = (
                f"{len(platform_id)}:{platform_id}|"
                f"{len(group_id)}:{group_id}|"
                f"{len(event_message_id)}:{event_message_id}"
            )
            reserved_event_id = await self._reserve_event_id(dedup_key)
            if not reserved_event_id:
                logger.debug(
                    "[%s] 跳过重复消息事件: group=%s, id=%s",
                    platform_name or platform_id,
                    group_id,
                    event_message_id,
                )
                return False
        # 7. 存储到数据库
        try:
            await self.history_writer.insert(
                platform_id=platform_id,
                group_id=group_id,
                content=incoming.content,
                sender_id=sender_id,
                sender_name=sender_name,
            )
        except BaseException:
            if reserved_event_id and dedup_key:
                await self._release_event_id(dedup_key)
            raise
        else:
            if reserved_event_id and dedup_key:
                await self._commit_event_id(dedup_key)

        # 注册群组，以便调度器能自动发现未提供群列表 API 的平台（如 Telegram、QQ 官方等）。
        try:
            await self.group_registry.upsert(
                platform_id=platform_id,
                group_id=group_id,
                sender_id=sender_id,
                sender_name=sender_name,
                event_message_id=event_message_id,
            )
        except Exception as e:
            logger.warning(
                "[GroupRegistry] 更新群注册表失败: "
                f"platform_id={platform_id} group_id={group_id} error={e}"
            )

        logger.debug(
            f"[{platform_id}] 已缓存群 {group_id} 的消息 (发送者: {sender_name})"
        )
        return True

    async def _reserve_event_id(self, dedup_key: str) -> bool:
        """预占事件消息 ID：在历史记录持久化期间防止重复入库。

        Args:
            dedup_key: 平台群组事件消息的唯一幂等标识键。

        Returns:
            bool: 若预占成功返回 True；若已存在处理中或已处理记录则返回 False。
        """
        if dedup_key in self._inflight_event_ids or dedup_key in self._seen_event_ids:
            if dedup_key in self._seen_event_ids:
                self._seen_event_ids.move_to_end(dedup_key)
            return False

        # 在任何异步等待让渡控制权前，同步原子预占 in-flight 状态，杜绝并发穿透
        self._inflight_event_ids.add(dedup_key)

        if self.dedup_store is not None:
            # 在 SQLite 中原子执行 claim 预占（基于唯一主键冲突拦截，杜绝竞态）
            is_claimed = await asyncio.to_thread(self.dedup_store.try_claim, dedup_key)
            if not is_claimed:
                self._inflight_event_ids.discard(dedup_key)
                self._seen_event_ids[dedup_key] = None
                if len(self._seen_event_ids) > self._seen_event_ids_limit:
                    self._seen_event_ids.popitem(last=False)
                return False

        return True

    async def _commit_event_id(self, dedup_key: str) -> None:
        """确认事件消息 ID：标记为已持久化，纳入后续去重。

        Args:
            dedup_key: 平台群组事件消息的唯一幂等标识键。
        """
        self._inflight_event_ids.discard(dedup_key)
        if dedup_key in self._seen_event_ids:
            self._seen_event_ids.move_to_end(dedup_key)
        else:
            self._seen_event_ids[dedup_key] = None
        if len(self._seen_event_ids) > self._seen_event_ids_limit:
            self._seen_event_ids.popitem(last=False)

    async def _release_event_id(self, dedup_key: str) -> None:
        """释放事件消息 ID：持久化失败或取消时清理预占状态。

        Args:
            dedup_key: 平台群组事件消息的唯一幂等标识键。
        """
        self._inflight_event_ids.discard(dedup_key)
        if self.dedup_store is not None:
            await asyncio.to_thread(self.dedup_store.release, dedup_key)
