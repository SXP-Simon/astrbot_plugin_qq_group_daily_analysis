"""
分析应用服务 - 应用层
实现"每日群聊分析并生成报告"及"增量分析"核心用例。
负责协调领域服务、基础设施适配器及持久化层。
"""

from __future__ import annotations

import asyncio
import datetime as dt
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
from ...utils.logger import logger


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
        max_concurrent = self.config_manager.get_llm_max_concurrent()
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

        async with self.group_lock(group_id, "daily"):
            logger.info(
                f"开始执行分析用例: 群 {group_id}, platform_id={platform_id or '默认'}, days={days or '默认'}"
            )

            # 1. 获取适配器
            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

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
            bot_self_ids = self.config_manager.get_bot_self_ids()

            # 对于自动任务，强制过滤指令；对于手动任务，也建议过滤以保持报告纯净
            unified_messages = cleaner.clean_messages(
                raw_messages, bot_self_ids=bot_self_ids, filter_commands=True
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
            statistics = await asyncio.to_thread(
                self.statistics_service.calculate_group_statistics, unified_messages
            )

            # 4. 用户分析 (Domain Service)
            bot_self_ids = self.config_manager.get_bot_self_ids()
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
            # LLMAnalyzer 内部可能已经处理了转换（见之前代码）
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

            # Note: LLMAnalyzer 目前可能只接收 legacy 格式或特定的 UnifiedMessage 适配
            # 暂时转换回 legacy 格式以确保稳定性，直到 LLMAnalyzer 被重构
            legacy_messages = self.statistics_service._convert_to_legacy_dict(
                unified_messages
            )

            unified_msg_origin = (
                f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
            )

            if (
                topic_enabled
                or user_title_enabled
                or golden_quote_enabled
                or chat_quality_enabled
            ):
                async with self.llm_semaphore:
                    logger.debug(f"[LLM] 已进入分析队列 (群: {group_id})")
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

    # ----------------------------------------------------------------
    # 增量分析用例
    # ----------------------------------------------------------------

    async def execute_incremental_analysis(
        self, group_id: str, platform_id: str | None = None
    ) -> dict[str, Any]:
        """
        执行一次增量分析用例（滑动窗口批次架构）。

        与每日分析不同，增量分析每次仅处理最近一段时间的消息，
        提取少量话题和金句，将结果作为独立批次存储到 KV。
        不生成用户称号（留到最终报告时再做），不生成报告。

        流程：
        1. 获取适配器
        2. 拉取消息（使用增量配置的 max_messages）
        3. 清理消息
        4. 按时间戳去重：过滤已分析过的消息
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
        async with self.group_lock(group_id, "incremental"):
            if not self.incremental_store:
                raise RuntimeError("增量分析未初始化：缺少 IncrementalStore")

            logger.info(
                f"开始增量分析用例: 群 {group_id}, 平台 {platform_id or '默认'}"
            )

            # 1. 获取适配器
            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            # 2. 拉取消息，获取进度并确定拉取量
            last_analyzed_ts = await self.incremental_store.get_last_analyzed_timestamp(
                group_id
            )
            days = self.config_manager.get_analysis_days()
            # 在增量模式下，拉取上限由安全限制 (Safe Count) 统一控制，确保能追平进度且不溢出
            max_count = self.config_manager.get_incremental_safe_limit()

            # 3. 拉取消息（优先从上次进度点开始回溯，确保不遗漏高活跃期间的 Gap）
            raw_messages = await adapter.fetch_messages(
                group_id=group_id,
                days=days,
                max_count=max_count,
                since_ts=last_analyzed_ts,
            )

            if not raw_messages:
                logger.warning(f"群 {group_id} 在最近 {days} 天内无消息或无法获取")
                return {"success": False, "reason": "no_messages"}

            # 3. 清理消息
            from ...domain.services.message_cleaner_service import MessageCleanerService

            cleaner = MessageCleanerService()
            bot_self_ids = self.config_manager.get_bot_self_ids()
            unified_messages = cleaner.clean_messages(
                raw_messages, bot_self_ids=bot_self_ids, filter_commands=True
            )

            # 5. 二次去重，确保只保留断点之后的真正新消息
            if last_analyzed_ts > 0:
                unified_messages = [
                    msg for msg in unified_messages if msg.timestamp > last_analyzed_ts
                ]

            # 5. 检查最小消息阈值
            min_messages = self.config_manager.get_incremental_min_messages()
            if len(unified_messages) < min_messages:
                logger.info(
                    f"群 {group_id} 增量分析：新消息数 ({len(unified_messages)}) "
                    f"未达到阈值 ({min_messages})，跳过本次分析"
                )
                return {"success": False, "reason": "below_threshold"}

            # 6. 计算基础统计
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
                async with self.llm_semaphore:
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
            batch = IncrementalBatch(
                group_id=group_id,
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
            await self.incremental_store.save_batch(batch)

            # 安全更新水位线：取消息最大时间戳，但不能超过当前时间+1分钟，防止未来时间戳毒化导致后续分析死锁
            import time

            safe_now = int(time.time()) + 60
            safe_ts = min(last_message_timestamp, safe_now)

            await self.incremental_store.update_last_analyzed_timestamp(
                group_id, safe_ts
            )

            logger.info(
                f"群 {group_id} 增量分析完成: "
                f"本批次消息={len(unified_messages)}, "
                f"新话题={len(new_topics)}, 新金句={len(new_quotes)}"
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
                    async with self.llm_semaphore:
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
                    async with self.llm_semaphore:
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
                f"群 {group_id} 增量最终报告完成: "
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
