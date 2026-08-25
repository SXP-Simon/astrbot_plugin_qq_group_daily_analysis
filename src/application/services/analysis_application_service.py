"""
分析应用服务 - 应用层
实现"每日群聊分析并生成报告"及"增量分析"核心用例。
负责协调领域服务、基础设施适配器及持久化层。
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import time as time_mod
import weakref
from collections import defaultdict
from collections.abc import Mapping
from contextlib import asynccontextmanager
from typing import Any

from ...domain.entities.incremental_state import IncrementalBatch
from ...domain.models.data_models import TokenUsage
from ...domain.repositories.analysis_repository import IAnalysisProvider
from ...domain.repositories.report_repository import IReportGenerator
from ...domain.services.analysis_domain_service import (
    AnalysisDomainService,
    UserActivityStats,
)
from ...domain.services.incremental_merge_service import IncrementalMergeService
from ...domain.services.statistics_service import StatisticsService
from ...domain.value_objects.unified_message import UnifiedMessage
from ...infrastructure.persistence.incremental_store import IncrementalStore
from ...shared.trace_context import TraceContext
from ...utils.logger import logger

_LLM_SEMAPHORE_INFO_SECONDS = 1.0
_LLM_SEMAPHORE_WARN_SECONDS = 15.0


class DuplicateGroupTaskError(Exception):
    """当同一个群组在同一时间尝试启动相同类型的重复分析任务时抛出。"""

    pass


class AnalysisApplicationService:
    """分析应用服务 - 协调业务流程（每日分析 + 增量分析）"""

    def __init__(
        self,
        config_manager: Any,
        bot_manager: Any,
        history_manager: Any,
        report_generator: IReportGenerator,
        llm_analyzer: IAnalysisProvider,
        statistics_service: StatisticsService,
        analysis_domain_service: AnalysisDomainService,
        incremental_store: IncrementalStore | None = None,
        incremental_merge_service: IncrementalMergeService | None = None,
    ):
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.history_manager = history_manager
        self.report_generator = report_generator
        self.llm_analyzer = llm_analyzer
        self.statistics_service = statistics_service
        self.analysis_domain_service = analysis_domain_service
        self.incremental_store = incremental_store
        self.incremental_merge_service = incremental_merge_service
        self._locks = weakref.WeakValueDictionary()
        # 全局 LLM 分析信号量，控制对外 API 的并发压力
        # 使用专用的 LLM 并发配置项
        max_concurrent = max(1, int(self.config_manager.get_llm_max_concurrent()))
        self._llm_max_concurrent = max_concurrent
        self.llm_semaphore = asyncio.Semaphore(max_concurrent)
        # 用于追踪当前正在执行的任务，实现原子的“检查并设置”逻辑，避免 locked() 竞态
        self._active_tasks = set()

    @asynccontextmanager
    async def group_lock(self, group_id: str, task_type: str = "analysis"):
        """
        同一时间、同一个群、同一种任务只能有一个在执行
        锁将在退出上下文时自动释放。
        """
        lock_key = f"{task_type}:{group_id}"

        # 获取或创建该群组特有的锁（保留锁作为第二道资源限流防线）
        lock = self._locks.get(lock_key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[lock_key] = lock

        # 使用同步集合实现原子化的“运行中”检查
        # 在 asyncio 的单线程循环中，同步代码段不会被中断，因此这是原子操作
        if lock_key in self._active_tasks:
            logger.warning(f"群 {group_id} 的 {task_type} 任务已在运行，跳过本次请求")
            raise DuplicateGroupTaskError(f"Duplicate task for {lock_key}")

        # 占位：标记任务开始
        self._active_tasks.add(lock_key)

        try:
            async with lock:
                logger.debug(f"[Lock] 已获取群 {group_id} 的 {task_type} 排他锁")
                yield
        finally:
            # 释放：标记任务结束
            self._active_tasks.discard(lock_key)
            logger.debug(f"[Lock] 已释放群 {group_id} 的 {task_type} 排他锁")

    @asynccontextmanager
    async def _llm_slot(self, group_id: str, stage: str):
        """观察并占用一次 LLM 分析槽位。

        Args:
            group_id: 当前分析任务所属群号。
            stage: 分析阶段名称，用于区分全量、增量、最终报告等入口。

        Yields:
            None: 成功进入 LLM 分析槽位后交还给调用方执行实际分析。

        Raises:
            asyncio.CancelledError: 调用方任务被取消时原样抛出。
        """
        trace = TraceContext.current()
        missing_marker = object()
        previous_stage = missing_marker
        previous_group_id = missing_marker
        if trace:
            # 将外层分析阶段写入 Trace 元数据，供更底层的 Provider 调用日志读取。
            previous_stage = trace.metadata.get("llm_stage", missing_marker)
            previous_group_id = trace.metadata.get("llm_group_id", missing_marker)
            trace.metadata["llm_stage"] = stage
            trace.metadata["llm_group_id"] = group_id

        wait_started_at = time_mod.monotonic()
        logger.debug(
            f"[LLM 队列观测] 等待分析槽位: group={group_id}, stage={stage}, "
            f"available={getattr(self.llm_semaphore, '_value', None)}/"
            f"{self._llm_max_concurrent}, active={len(self._active_tasks)}"
        )
        while True:
            try:
                await asyncio.wait_for(
                    self.llm_semaphore.acquire(), timeout=_LLM_SEMAPHORE_WARN_SECONDS
                )
                break
            except TimeoutError:
                logger.warning(
                    f"[LLM 队列观测] 等待分析槽位超过 "
                    f"{time_mod.monotonic() - wait_started_at:.0f}s: "
                    f"group={group_id}, stage={stage}, "
                    f"available={getattr(self.llm_semaphore, '_value', None)}/"
                    f"{self._llm_max_concurrent}, active={len(self._active_tasks)}"
                )

        waited_seconds = time_mod.monotonic() - wait_started_at
        log_method = (
            logger.info
            if waited_seconds >= _LLM_SEMAPHORE_INFO_SECONDS
            else logger.debug
        )
        log_method(
            f"[LLM 队列观测] 已进入分析槽位: group={group_id}, stage={stage}, "
            f"wait={waited_seconds:.2f}s, "
            f"available={getattr(self.llm_semaphore, '_value', None)}/"
            f"{self._llm_max_concurrent}, active={len(self._active_tasks)}"
        )
        run_started_at = time_mod.monotonic()
        try:
            yield
        finally:
            self.llm_semaphore.release()
            logger.debug(
                f"[LLM 队列观测] 已释放分析槽位: group={group_id}, stage={stage}, "
                f"duration={time_mod.monotonic() - run_started_at:.2f}s, "
                f"available={getattr(self.llm_semaphore, '_value', None)}/"
                f"{self._llm_max_concurrent}, active={len(self._active_tasks)}"
            )
            if trace:
                # 恢复原有 Trace 元数据，避免嵌套或后续任务误读上一段分析阶段。
                if previous_stage is missing_marker:
                    trace.metadata.pop("llm_stage", None)
                else:
                    trace.metadata["llm_stage"] = previous_stage
                if previous_group_id is missing_marker:
                    trace.metadata.pop("llm_group_id", None)
                else:
                    trace.metadata["llm_group_id"] = previous_group_id

    async def execute_daily_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
        manual: bool = False,
        days: int | None = None,
    ) -> dict[str, Any]:
        """
        执行每日分析用例。

        流程：
        1. 获取适配器
        2. 拉取消息 (Infrastructure)
        3. 基础统计 (Domain Service)
        4. 用户分析 (Domain Service)
        5. LLM 语义分析 (Infrastructure/Analysis Bridge)
        6. 生成报告 (Visualization/Infrastructure)
        7. 持久化摘要 (Persistence)
        8. 返回结果
        """

        trace = TraceContext.current()
        if not trace:
            trace = TraceContext.get_or_create(
                group_id=str(group_id),
                platform=platform_id or "",
                trigger_type="manual" if manual else "auto",
                auto_bind=True,
            )
        else:
            if not trace.group_id:
                trace.group_id = str(group_id)
            if not trace.platform and platform_id:
                trace.platform = platform_id
            trace.trigger_type = "manual" if manual else "auto"

        async with self.group_lock(group_id, "daily"):
            logger.info(
                f"开始执行分析用例: 群 {group_id}, platform_id={platform_id or '默认'}, days={days or '默认'}"
            )

            # 1. 获取适配器
            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            # 确立并回填实际运行的真实平台标识 (Real Platform Identity: 优先使用具体平台实例 ID 如 nuits)
            actual_platform = (
                (
                    self.bot_manager.get_adapter_platform_id(adapter)
                    if hasattr(self.bot_manager, "get_adapter_platform_id")
                    else ""
                )
                or getattr(adapter, "platform_id", "")
                or getattr(adapter, "platform_name", "")
                or (
                    platform_id
                    if platform_id and platform_id not in ("auto", "default", "all")
                    else ""
                )
            )
            if trace and actual_platform:
                trace.platform = str(actual_platform)

            # 检查群聊是否被禁言（包括全体禁言或对 Bot 自身禁言）
            if hasattr(adapter, "is_group_muted"):
                try:
                    if await adapter.is_group_muted(group_id):
                        logger.info(
                            f"群 {group_id} 开启了全群禁言或对 Bot 禁言，跳过本次群分析"
                        )
                        return {"success": False, "reason": "muted"}
                except Exception as e:
                    logger.warning(f"检查群 {group_id} 禁言状态时出错: {e}")

            # 飞书平台在分析前进行一次性权限与成员头像预热，避免报告阶段出现大面积默认头像。
            if hasattr(adapter, "prepare_group_member_cache"):
                try:
                    logger.info(
                        "执行平台成员预检查: group=%s, platform=%s",
                        group_id,
                        platform_id or "default",
                    )
                    ok, err = await adapter.prepare_group_member_cache(group_id)  # type: ignore[attr-defined]
                    if not ok and err:
                        raise ValueError(err)
                    logger.info(
                        "平台成员预检查通过: group=%s, platform=%s",
                        group_id,
                        platform_id or "default",
                    )
                except Exception as e:
                    raise ValueError(
                        f"飞书成员信息预检查失败，请先完成应用权限授权：{e}"
                    ) from e

            # 2. 拉取消息
            if days is None:
                days = self.config_manager.get_analysis_days()
            max_count = self.config_manager.get_max_messages()

            with trace.span("FETCH_MESSAGES", {"days": days, "max_count": max_count}):
                raw_messages = await adapter.fetch_messages(
                    group_id=group_id, days=days, max_count=max_count
                )
            logger.info(
                "消息拉取完成: group=%s, platform=%s, raw_count=%s, days=%s, max_count=%s",
                group_id,
                platform_id or "default",
                len(raw_messages),
                days,
                max_count,
            )

            if not raw_messages:
                logger.warning(f"群 {group_id} 在最近 {days} 天内无消息或无法获取")
                return {"success": False, "reason": "no_messages"}

            # 3. 清理消息 (Filter commands, bot messages, noise)
            from ...domain.services.message_cleaner_service import MessageCleanerService

            cleaner = MessageCleanerService()
            bot_self_ids = list(self.config_manager.get_bot_self_ids() or [])
            if hasattr(adapter, "bot_self_ids") and adapter.bot_self_ids:
                for b_id in adapter.bot_self_ids:
                    if b_id and str(b_id) not in bot_self_ids:
                        bot_self_ids.append(str(b_id))
            if not self.config_manager.get_filter_bot_messages():
                bot_self_ids = []
            logger.debug(
                "filter_bot_messages=%s, bot_self_ids=%s",
                self.config_manager.get_filter_bot_messages(),
                bot_self_ids,
            )

            # 对于自动任务，强制过滤指令；对于手动任务，也建议过滤以保持报告纯净
            with trace.span("CLEAN_MESSAGES"):
                unified_messages = cleaner.clean_messages(
                    raw_messages, bot_self_ids=bot_self_ids, filter_commands=True
                )
            trace.set_context_metrics(
                raw_message_count=len(raw_messages),
                cleaned_message_count=len(unified_messages),
            )
            logger.info(
                "消息清洗完成: group=%s, platform=%s, cleaned_count=%s, dropped=%s",
                group_id,
                platform_id or "default",
                len(unified_messages),
                max(len(raw_messages) - len(unified_messages), 0),
            )

            # 4. 检查最小消息阈值 (在清理后进行)
            threshold = self.config_manager.get_min_messages_threshold()
            if len(unified_messages) < threshold and not manual:
                logger.info(
                    f"群 {group_id} 有效消息数 ({len(unified_messages)}) 未达到自动分析阈值 ({threshold})"
                )
                return {"success": False, "reason": "below_threshold"}

            # 5. 基础统计 (Domain Service)
            with trace.span("STATS_ANALYSIS"):
                statistics = await asyncio.to_thread(
                    self.statistics_service.calculate_group_statistics, unified_messages
                )
                user_activity = await asyncio.to_thread(
                    self.analysis_domain_service.analyze_user_activity,
                    unified_messages,
                    bot_self_ids,
                )

            max_user_titles = self.config_manager.get_max_user_titles()
            top_users = self.analysis_domain_service.get_top_users(
                user_activity, limit=max_user_titles
            )

            # 5. LLM 语义分析 (为了保持兼容，目前直接传 UnifiedMessage，后续如需传 raw dict 再加转换)
            topic_enabled = self.config_manager.get_topic_analysis_enabled()
            user_title_enabled = self.config_manager.get_user_title_analysis_enabled()
            golden_quote_enabled = (
                self.config_manager.get_golden_quote_analysis_enabled()
            )
            chat_quality_enabled = (
                self.config_manager.get_chat_quality_analysis_enabled()
            )

            topics = []
            user_titles = []
            golden_quotes = []
            chat_quality_review = None
            total_token_usage = TokenUsage()

            legacy_messages = self.statistics_service._convert_to_legacy_dict(
                unified_messages
            )

            unified_msg_origin = (
                f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
            )
            analysis_stage = "full_manual" if manual else "full_scheduled"

            if (
                topic_enabled
                or user_title_enabled
                or golden_quote_enabled
                or chat_quality_enabled
            ):
                with trace.span("LLM_ANALYSIS"):
                    async with self._llm_slot(group_id, analysis_stage):
                        logger.debug(
                            f"[LLM] 已进入普通全量分析队列 "
                            f"(群: {group_id}, stage: {analysis_stage})"
                        )
                        (
                            topics,
                            user_titles,
                            golden_quotes,
                            total_token_usage,
                            chat_quality_review,
                        ) = await self.llm_analyzer.analyze_all_concurrent(
                            legacy_messages,
                            user_activity,
                            umo=unified_msg_origin,
                            top_users=top_users,
                            topic_enabled=topic_enabled,
                            user_title_enabled=user_title_enabled,
                            golden_quote_enabled=golden_quote_enabled,
                            chat_quality_enabled=chat_quality_enabled,
                        )

            # 回填结果
            statistics.golden_quotes = golden_quotes
            statistics.token_usage = total_token_usage

            analysis_result = {
                "statistics": statistics,
                "topics": topics,
                "user_titles": user_titles,
                "user_analysis": user_activity,
                "chat_quality_review": chat_quality_review,
            }

            # 6. 持久化摘要 (Persistence)
            with trace.span("SAVE_SUMMARY"):
                await self.history_manager.save_analysis(group_id, analysis_result)

            # 7. 生成报告并发送 (应用层编排发送动作)
            # 这里由调用方处理发送，本服务只返回分析结果和可能的视觉产物
            return {
                "success": True,
                "analysis_result": analysis_result,
                "messages_count": len(unified_messages),
                "adapter": adapter,
                "group_id": group_id,
                "platform_id": getattr(adapter, "platform_id", platform_id),
            }

    async def execute_comic_topic_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
        days: int | None = None,
    ) -> dict[str, Any]:
        """为独立漫画命令提取话题。

        Args:
            group_id: 目标群 ID。
            platform_id: 平台适配器 ID。为空时使用默认适配器。
            days: 可选消息回溯天数。为空时使用普通分析的默认天数。

        Returns:
            成功时返回提取到的话题和适配器信息；失败时返回 no_messages、
            muted 或 no_topics 等原因。

        Raises:
            ValueError: 找不到对应平台适配器时抛出。
        """
        async with self.group_lock(group_id, "comic"):
            logger.info(
                "开始执行手动漫画话题分析: group=%s, platform=%s, days=%s",
                group_id,
                platform_id or "default",
                days or "default",
            )

            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            if hasattr(adapter, "is_group_muted"):
                try:
                    if await adapter.is_group_muted(group_id):
                        logger.info(
                            "群 %s 开启了禁言，跳过本次手动漫画话题分析",
                            group_id,
                        )
                        return {"success": False, "reason": "muted"}
                except Exception as e:
                    logger.warning(
                        "检查群 %s 禁言状态时出错: %s",
                        group_id,
                        e,
                    )

            if days is None:
                days = self.config_manager.get_analysis_days()
            max_count = self.config_manager.get_max_messages()

            raw_messages = await adapter.fetch_messages(
                group_id=group_id, days=days, max_count=max_count
            )
            logger.info(
                "手动漫画消息拉取完成: group=%s, platform=%s, raw_count=%s, days=%s, max_count=%s",
                group_id,
                platform_id or "default",
                len(raw_messages),
                days,
                max_count,
            )
            if not raw_messages:
                return {"success": False, "reason": "no_messages"}

            from ...domain.services.message_cleaner_service import MessageCleanerService

            cleaner = MessageCleanerService()
            bot_self_ids = self.config_manager.get_bot_self_ids()
            if not self.config_manager.get_filter_bot_messages():
                bot_self_ids = []
            unified_messages = cleaner.clean_messages(
                raw_messages, bot_self_ids=bot_self_ids, filter_commands=True
            )
            logger.info(
                "手动漫画消息清洗完成: group=%s, platform=%s, cleaned_count=%s, dropped=%s",
                group_id,
                platform_id or "default",
                len(unified_messages),
                max(len(raw_messages) - len(unified_messages), 0),
            )
            if not unified_messages:
                return {"success": False, "reason": "no_messages"}

            legacy_messages = self.statistics_service._convert_to_legacy_dict(
                unified_messages
            )
            unified_msg_origin = (
                f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
            )

            async with self._llm_slot(group_id, "comic_manual"):
                topics, token_usage = await self.llm_analyzer.analyze_topics(
                    legacy_messages, unified_msg_origin
                )

            if not topics:
                return {"success": False, "reason": "no_topics"}

            return {
                "success": True,
                "topics": topics,
                "token_usage": token_usage,
                "messages_count": len(unified_messages),
                "adapter": adapter,
                "group_id": group_id,
                "platform_id": getattr(adapter, "platform_id", platform_id),
            }

    # ----------------------------------------------------------------
    # 增量分析用例
    # ----------------------------------------------------------------

    async def execute_incremental_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
    ) -> dict[str, Any]:
        """
        执行一次增量分析用例（滑动窗口批次架构）。

        与每日分析不同，增量分析每次仅处理消息阈值规定的固定批次，
        提取少量话题和金句，将结果作为独立批次存储到 KV。
        不生成用户称号（留到最终报告时再做），不生成报告。

        流程：
        1. 获取适配器
        2. 拉取消息（使用增量配置的 max_messages）
        3. 清理消息
        4. 按时间戳和消息 ID 去重：过滤已分析过的消息
        5. 检查最小消息阈值
        6. 计算基础统计（小时分布、用户活跃、表情）
        7. LLM 增量分析（仅话题 + 金句）
        8. 构建 IncrementalBatch 并保存
        9. 更新最后分析消息时间戳
        10. 返回批次结果

        Args:
            group_id: 群组 ID
            platform_id: 平台标识，缺省为默认

        Returns:
            dict: 包含 success、batch_summary 等信息
        """
        trace = TraceContext.current()
        if not trace:
            trace = TraceContext.get_or_create(
                group_id=str(group_id),
                platform=platform_id or "",
                trigger_type="incremental",
                auto_bind=True,
            )

        async with self.group_lock(group_id, "incremental"):
            analysis_started_at = time_mod.monotonic()
            if not self.incremental_store:
                raise RuntimeError("增量分析未初始化：缺少 IncrementalStore")

            logger.debug(
                f"开始增量分析用例: 群 {group_id}, 平台 {platform_id or '默认'}"
            )

            # 1. 获取适配器
            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            # 检查群聊是否被禁言（包括全体禁言或对 Bot 自身禁言）
            if hasattr(adapter, "is_group_muted"):
                try:
                    if await adapter.is_group_muted(group_id):
                        logger.debug(
                            f"群 {group_id} 开启了全群禁言或对 Bot 禁言，跳过本次增量群分析"
                        )
                        return {"success": False, "reason": "muted"}
                except Exception as e:
                    logger.warning(f"检查群 {group_id} 禁言状态时出错: {e}")

            # 2. 拉取消息，获取进度并确定拉取量
            (
                last_analyzed_ts,
                last_analyzed_message_ids,
            ) = await self.incremental_store.get_last_analyzed_cursor(group_id)
            days = self.config_manager.get_analysis_days()
            # 复用基础拉取上限，同时保证至少能拉取一个完整增量批次。
            min_messages = self.config_manager.get_incremental_min_messages()
            max_count = max(self.config_manager.get_max_messages(), min_messages)

            # 3. 拉取消息（优先从上次进度点开始回溯，确保不遗漏高活跃期间的 Gap）
            fetch_started_at = time_mod.monotonic()
            with trace.span("FETCH_MESSAGES", {"days": days, "max_count": max_count}):
                raw_messages = await adapter.fetch_messages(
                    group_id=group_id,
                    days=days,
                    max_count=max_count,
                    since_ts=last_analyzed_ts,
                )
            raw_count = len(raw_messages)
            fetch_duration = time_mod.monotonic() - fetch_started_at

            if not raw_messages:
                logger.warning(f"群 {group_id} 在最近 {days} 天内无消息或无法获取")
                return {"success": False, "reason": "no_messages", "messages_count": 0}

            # 3. 清理消息
            from ...domain.services.message_cleaner_service import MessageCleanerService

            cleaner = MessageCleanerService()
            bot_self_ids = self.config_manager.get_bot_self_ids()
            if not self.config_manager.get_filter_bot_messages():
                bot_self_ids = []
            logger.debug(
                "增量消息清洗配置: group=%s, filter_bot_messages=%s, bot_self_id_count=%s",
                group_id,
                self.config_manager.get_filter_bot_messages(),
                len(bot_self_ids),
            )
            with trace.span("CLEAN_MESSAGES"):
                unified_messages = cleaner.clean_messages(
                    raw_messages, bot_self_ids=bot_self_ids, filter_commands=True
                )
            cleaned_count = len(unified_messages)
            trace.set_context_metrics(
                raw_message_count=raw_count,
                cleaned_message_count=cleaned_count,
                incremental_batches=1,
            )

            # 5. 复合游标去重，避免同一秒内分批时遗漏消息。
            if last_analyzed_ts > 0:
                unified_messages = [
                    msg
                    for msg in unified_messages
                    if msg.timestamp > last_analyzed_ts
                    or (
                        msg.timestamp == last_analyzed_ts
                        and msg.message_id not in last_analyzed_message_ids
                    )
                ]

            eligible_count = len(unified_messages)
            logger.debug(
                "增量消息筛选完成: platform=%s, group=%s, raw=%s, cleaned=%s, "
                "eligible=%s, threshold=%s, fetch_limit=%s, fetch_limit_reached=%s, "
                "fetch_duration=%.2fs, cursor_ts=%s, cursor_ids=%s",
                platform_id or "default",
                group_id,
                raw_count,
                cleaned_count,
                eligible_count,
                min_messages,
                max_count,
                raw_count >= max_count,
                fetch_duration,
                last_analyzed_ts,
                len(last_analyzed_message_ids),
            )

            # 固定每批消息规模，待处理消息达到多个批次时连续处理，避免 LLM 负载波动。
            if len(unified_messages) < min_messages:
                logger.debug(
                    f"群 {group_id} 增量分析：新消息数 ({len(unified_messages)}) "
                    f"未达到阈值 ({min_messages})，跳过本次分析"
                )
                return {
                    "success": False,
                    "reason": "below_threshold",
                    "messages_count": len(unified_messages),
                }
            unified_messages.sort(key=lambda msg: (msg.timestamp, msg.message_id))
            if len(unified_messages) > min_messages:
                unified_messages = unified_messages[:min_messages]
            logger.debug(
                "增量批次已选定: platform=%s, group=%s, eligible=%s, selected=%s",
                platform_id or "default",
                group_id,
                eligible_count,
                len(unified_messages),
            )

            # 6. 计算基础统计
            with trace.span("STATS_ANALYSIS"):
                statistics = await asyncio.to_thread(
                    self.statistics_service.calculate_group_statistics, unified_messages
                )
                user_activity = await asyncio.to_thread(
                    self.analysis_domain_service.analyze_user_activity,
                    unified_messages,
                    bot_self_ids,
                )

            # 计算本批次的小时分布
            hourly_msg_counts, hourly_char_counts = self._compute_hourly_counts(
                unified_messages
            )

            # 7. LLM 增量分析（仅话题 + 金句）
            topics_per_batch = self.config_manager.get_incremental_topics_per_batch()
            quotes_per_batch = self.config_manager.get_incremental_quotes_per_batch()

            # 获取功能开关状态
            topic_enabled = self.config_manager.get_topic_analysis_enabled()
            golden_quote_enabled = (
                self.config_manager.get_golden_quote_analysis_enabled()
            )
            chat_quality_enabled = (
                self.config_manager.get_chat_quality_analysis_enabled()
            )

            # 需要将 UnifiedMessage 转换为 legacy 格式供 LLM 分析器使用
            legacy_messages = self.statistics_service._convert_to_legacy_dict(
                unified_messages
            )
            unified_msg_origin = (
                f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
            )

            topics = []
            golden_quotes = []
            token_usage = TokenUsage()
            chat_quality_review = None

            if topic_enabled or golden_quote_enabled or chat_quality_enabled:
                with trace.span("LLM_ANALYSIS"):
                    async with self._llm_slot(group_id, "incremental"):
                        logger.debug(f"[LLM] 已进入增量分析队列 (群: {group_id})")
                        (
                            topics,
                            golden_quotes,
                            token_usage,
                            chat_quality_review,
                        ) = await self.llm_analyzer.analyze_incremental_concurrent(
                            legacy_messages,
                            umo=unified_msg_origin,
                            topics_per_batch=topics_per_batch,
                            quotes_per_batch=quotes_per_batch,
                            topic_enabled=topic_enabled,
                            golden_quote_enabled=golden_quote_enabled,
                            chat_quality_enabled=chat_quality_enabled,
                        )

            # 8. 构建 IncrementalBatch
            # 8a. 转换话题: SummaryTopic -> dict
            new_topics = [
                {
                    "topic": t.topic,
                    "contributors": t.contributors,
                    "detail": t.detail,
                    "contributor_ids": t.contributor_ids,
                }
                for t in topics
            ]

            # 8b. 转换金句: GoldenQuote -> dict
            new_quotes = [
                {
                    "content": q.content,
                    "sender": q.sender,
                    "reason": q.reason,
                    "user_id": q.user_id,
                }
                for q in golden_quotes
            ]

            # 8c. 转换 token 消耗: TokenUsage -> dict
            token_usage_dict = {
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
            }

            # 8d. 转换用户统计: AnalysisDomainService 格式 -> IncrementalBatch 格式
            user_stats = self._convert_user_activity_for_merge(
                user_activity, unified_messages
            )

            # 8e. 转换表情统计: EmojiStatistics -> dict
            emoji_stats = {
                "face_count": statistics.emoji_statistics.face_count,
                "mface_count": statistics.emoji_statistics.mface_count,
                "bface_count": statistics.emoji_statistics.bface_count,
                "sface_count": statistics.emoji_statistics.sface_count,
                "other_emoji_count": statistics.emoji_statistics.other_emoji_count,
                "face_details": statistics.emoji_statistics.face_details,
            }

            # 8f. 转换聊天质量锐评: QualityReview -> dict
            chat_quality_dict = None
            if chat_quality_review:
                chat_quality_dict = {
                    "title": chat_quality_review.title,
                    "subtitle": chat_quality_review.subtitle,
                    "dimensions": [
                        {
                            "name": d.name,
                            "percentage": d.percentage,
                            "comment": d.comment,
                            "color": d.color,
                        }
                        for d in chat_quality_review.dimensions
                    ],
                    "summary": chat_quality_review.summary,
                }

            # 8g. 获取参与者 ID 和最后消息时间戳
            participant_ids = list({msg.sender_id for msg in unified_messages})
            last_message_timestamp = max(
                (msg.timestamp for msg in unified_messages), default=0
            )

            # 8g. 计算本批次总字符数
            characters_count = sum(msg.get_text_length() for msg in unified_messages)

            # 构建批次对象
            batch_identity = "\n".join(
                f"{msg.timestamp}:{msg.message_id}" for msg in unified_messages
            )
            batch = IncrementalBatch(
                group_id=group_id,
                batch_id=hashlib.sha256(
                    f"{platform_id or 'default'}:{group_id}:{batch_identity}".encode()
                ).hexdigest(),
                timestamp=time_mod.time(),
                messages_count=len(unified_messages),
                characters_count=characters_count,
                hourly_msg_counts={str(k): v for k, v in hourly_msg_counts.items()},
                hourly_char_counts={str(k): v for k, v in hourly_char_counts.items()},
                user_stats=user_stats,
                emoji_stats=emoji_stats,
                topics=new_topics,
                golden_quotes=new_quotes,
                token_usage=token_usage_dict,
                chat_quality_review=chat_quality_dict,
                last_message_timestamp=last_message_timestamp,
                participant_ids=participant_ids,
            )

            # 9. 保存批次并更新最后分析时间戳
            if not await self.incremental_store.save_batch(batch):
                return {
                    "success": False,
                    "reason": "batch_persistence_failed",
                    "messages_count": 0,
                }

            # 安全更新水位线：取消息最大时间戳，但不能超过当前时间+1分钟，防止未来时间戳毒化导致后续分析死锁
            import time

            safe_now = int(time.time()) + 60
            safe_ts = min(last_message_timestamp, safe_now)

            analyzed_ids_at_boundary = {
                msg.message_id
                for msg in unified_messages
                if msg.timestamp == last_message_timestamp and msg.message_id
            }
            if last_message_timestamp == last_analyzed_ts:
                analyzed_ids_at_boundary.update(last_analyzed_message_ids)
            if safe_ts != last_message_timestamp:
                analyzed_ids_at_boundary.clear()

            await self.incremental_store.update_last_analyzed_cursor(
                group_id,
                safe_ts,
                analyzed_ids_at_boundary,
            )

            logger.debug(
                f"群 {group_id} 增量批次完成: "
                f"platform={getattr(adapter, 'platform_id', platform_id) or 'default'}, "
                f"batch={batch.batch_id[:8]}, 消息={len(unified_messages)}, "
                f"raw={raw_count}, cleaned={cleaned_count}, eligible={eligible_count}, "
                f"cursor={last_analyzed_ts}->{safe_ts}, "
                f"新话题={len(new_topics)}, 新金句={len(new_quotes)}, "
                f"tokens={token_usage.total_tokens}, "
                f"duration={time_mod.monotonic() - analysis_started_at:.2f}s"
            )

            return {
                "success": True,
                "batch_summary": batch.get_summary(),
                "messages_count": len(unified_messages),
                "group_id": group_id,
                "platform_id": getattr(adapter, "platform_id", platform_id),
            }

    async def execute_incremental_final_report(
        self, group_id: str, platform_id: str | None = None
    ) -> dict[str, Any]:
        """
        基于滑动窗口内的增量批次生成最终报告。

        按 analysis_days × 24h 的时间窗口查询所有批次，
        合并为 IncrementalState，额外执行用户称号分析，
        然后生成与传统每日分析格式完全一致的 analysis_result。

        流程：
        1. 计算滑动窗口范围
        2. 查询窗口内的所有批次
        3. 检查批次有效性
        4. 合并批次为 IncrementalState
        5. 执行用户称号 LLM 分析（基于合并后的累积数据）
        6. 使用 IncrementalMergeService 构建 analysis_result
        7. 持久化到 history_manager
        8. 返回结果

        Args:
            group_id: 群组 ID
            platform_id: 平台标识，缺省为默认

        Returns:
            dict: 包含 success、analysis_result、adapter 等信息
        """
        async with self.group_lock(group_id, "final"):
            if not self.incremental_store or not self.incremental_merge_service:
                raise RuntimeError(
                    "增量分析未初始化：缺少 IncrementalStore 或 IncrementalMergeService"
                )

            logger.info(
                f"开始增量最终报告: 群 {group_id}, 平台 {platform_id or '默认'}"
            )

            # 1. 计算滑动窗口范围
            analysis_days = self.config_manager.get_analysis_days()
            window_end = time_mod.time()
            window_start = window_end - (analysis_days * 24 * 3600)

            # 2. 查询窗口内的所有批次
            batches = await self.incremental_store.query_batches(
                group_id, window_start, window_end
            )

            # 3. 检查批次有效性
            if not batches:
                logger.warning(
                    f"群 {group_id} 滑动窗口内无增量分析数据，无法生成最终报告"
                )
                return {"success": False, "reason": "no_incremental_data"}

            # 4. 合并批次为 IncrementalState
            state = self.incremental_merge_service.merge_batches(
                batches, window_start, window_end
            )

            # 5. 获取适配器（报告发送需要）
            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            # 检查群聊是否被禁言（包括全体禁言或对 Bot 自身禁言）
            if hasattr(adapter, "is_group_muted"):
                try:
                    if await adapter.is_group_muted(group_id):
                        logger.info(
                            f"群 {group_id} 开启了全群禁言或对 Bot 禁言，跳过本次增量最终报告生成"
                        )
                        return {"success": False, "reason": "muted"}
                except Exception as e:
                    logger.warning(f"检查群 {group_id} 禁言状态时出错: {e}")

            # 6. 执行分析相关的变量准备
            user_titles = []
            user_title_enabled = self.config_manager.get_user_title_analysis_enabled()
            unified_msg_origin = (
                f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
            )

            if user_title_enabled and state.user_activities:
                max_user_titles = self.config_manager.get_max_user_titles()
                # 从合并后的 user_activities 中取出 top 用户
                top_users = state.get_user_activity_ranking(max_user_titles)

                try:
                    async with self._llm_slot(group_id, "incremental_final_title"):
                        logger.debug(f"[LLM] 已进入称号分析队列 (群: {group_id})")
                        (
                            user_titles_result,
                            title_token_usage,
                        ) = await self.llm_analyzer.analyze_user_titles(
                            messages=[],  # 增量模式下不传原始消息
                            user_activity=state.user_activities,
                            umo=unified_msg_origin,
                            top_users=top_users,
                        )
                    user_titles = user_titles_result

                    # 将称号分析的 token 消耗追加到状态中
                    state.total_token_usage["prompt_tokens"] = (
                        state.total_token_usage.get("prompt_tokens", 0)
                        + title_token_usage.prompt_tokens
                    )
                    state.total_token_usage["completion_tokens"] = (
                        state.total_token_usage.get("completion_tokens", 0)
                        + title_token_usage.completion_tokens
                    )
                    state.total_token_usage["total_tokens"] = (
                        state.total_token_usage.get("total_tokens", 0)
                        + title_token_usage.total_tokens
                    )
                except Exception as e:
                    logger.error(f"增量最终报告用户称号分析失败: {e}", exc_info=True)

            # 6.5 执行聊天质量汇总分析 (如果有多个批次的质量报告)
            if (
                self.config_manager.get_chat_quality_analysis_enabled()
                and state.all_quality_reviews
            ):
                try:
                    async with self._llm_slot(group_id, "incremental_final_quality"):
                        logger.debug(
                            f"[LLM] 已进入聊天质量汇总分析队列 (群: {group_id})"
                        )
                        (
                            summarized_review,
                            quality_token_usage,
                        ) = await self.llm_analyzer.summarize_quality_reviews(
                            batch_reviews=state.all_quality_reviews,
                            umo=unified_msg_origin,
                        )
                    if summarized_review:
                        # 更新 state 中的 review 为汇总后的结果
                        # 这里我们需要将 QualityReview 对象存回 dict 或直接在后续处理中使用
                        # build_analysis_result 会使用 state.chat_quality_review
                        state.chat_quality_review = {
                            "title": summarized_review.title,
                            "subtitle": summarized_review.subtitle,
                            "dimensions": [
                                {
                                    "name": d.name,
                                    "percentage": d.percentage,
                                    "comment": d.comment,
                                    "color": d.color,
                                }
                                for d in summarized_review.dimensions
                            ],
                            "summary": summarized_review.summary,
                        }

                        # 累加 Token
                        state.total_token_usage["prompt_tokens"] = (
                            state.total_token_usage.get("prompt_tokens", 0)
                            + quality_token_usage.prompt_tokens
                        )
                        state.total_token_usage["completion_tokens"] = (
                            state.total_token_usage.get("completion_tokens", 0)
                            + quality_token_usage.completion_tokens
                        )
                        state.total_token_usage["total_tokens"] = (
                            state.total_token_usage.get("total_tokens", 0)
                            + quality_token_usage.total_tokens
                        )
                except Exception as e:
                    logger.error(f"增量最终报告聊天质量汇总失败: {e}", exc_info=True)

            # 7. 构建 analysis_result
            analysis_result = self.incremental_merge_service.build_analysis_result(
                state, user_titles
            )

            # 8. 持久化到 history_manager
            await self.history_manager.save_analysis(group_id, analysis_result)

            logger.info(
                f"群 {group_id} 增量最终报告内容生成并保存完成，等待发送: "
                f"窗口={state.get_window_date_str()}, "
                f"累计消息={state.total_message_count}, "
                f"话题={len(state.topics)}, 金句={len(state.golden_quotes)}, "
                f"批次={state.total_analysis_count}"
            )

            return {
                "success": True,
                "analysis_result": analysis_result,
                "messages_count": state.total_message_count,
                "adapter": adapter,
                "group_id": group_id,
                "platform_id": getattr(adapter, "platform_id", platform_id),
            }

    # ----------------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------------

    @staticmethod
    def _compute_hourly_counts(
        messages: list[UnifiedMessage],
    ) -> tuple[dict[int, int], dict[int, int]]:
        """
        从消息列表计算按小时的消息数和字符数分布。

        Args:
            messages: 统一格式的消息列表

        Returns:
            tuple: (每小时消息计数, 每小时字符计数)
        """
        hourly_msg: dict[int, int] = defaultdict(int)
        hourly_char: dict[int, int] = defaultdict(int)

        for msg in messages:
            hour = dt.datetime.fromtimestamp(msg.timestamp).hour
            hourly_msg[hour] += 1
            hourly_char[hour] += msg.get_text_length()

        return dict(hourly_msg), dict(hourly_char)

    @staticmethod
    def _convert_user_activity_for_merge(
        user_activity: Mapping[str, UserActivityStats],
        messages: list[UnifiedMessage],
    ) -> dict[str, dict]:
        """
        将 AnalysisDomainService.analyze_user_activity() 的返回格式
        转换为 IncrementalBatch 所需的 user_stats 格式。

        转换映射：
        - nickname -> name
        - hours (defaultdict) -> active_hours (list)
        - 新增 last_message_time（从消息时间戳中提取）

        Args:
            user_activity: AnalysisDomainService 返回的用户活跃数据
            messages: 本批次的消息列表（用于提取每个用户的最后发言时间）

        Returns:
            dict: IncrementalBatch 所需的 user_stats 格式
        """
        # 预先计算每个用户的最后消息时间戳
        user_last_time: dict[str, int] = {}
        for msg in messages:
            current = user_last_time.get(msg.sender_id, 0)
            if msg.timestamp > current:
                user_last_time[msg.sender_id] = msg.timestamp

        result: dict[str, dict] = {}
        for user_id, stats in user_activity.items():
            result[user_id] = {
                "nickname": stats.get("nickname", user_id),
                "message_count": stats.get("message_count", 0),
                "char_count": stats.get("char_count", 0),
                "emoji_count": stats.get("emoji_count", 0),
                "reply_count": stats.get("reply_count", 0),
                "hours": dict(
                    stats.get("hours", {})
                ),  # 这里的 hours 是 defaultdict(int)，转为 dict
                "last_message_time": user_last_time.get(user_id, 0),
            }

        return result
