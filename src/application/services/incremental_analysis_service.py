"""增量分析服务模块

负责执行基于滑动窗口批次的增量群聊消息分析及增量最终汇总报告生成用例。
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import time as time_mod
from typing import TYPE_CHECKING, Any

from ...domain.entities.incremental_state import IncrementalBatch
from ...domain.services.message_cleaner_service import MessageCleanerService
from ...domain.value_objects import TokenUsage
from ...shared.constants import AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from .incremental_batch_builder import (
    compute_hourly_counts,
    convert_user_activity_for_merge,
)
from .pipeline_context import PipelineContext

if TYPE_CHECKING:
    from ...domain.repositories.analysis_repository import IAnalysisProvider
    from ...domain.repositories.persistence_repository import (
        ICheckpointStore,
        IIncrementalStore,
    )
    from ...domain.services.analysis_domain_service import AnalysisDomainService
    from ...domain.services.incremental_merge_service import IncrementalMergeService
    from ...domain.services.statistics_service import StatisticsService
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.persistence.history_manager import HistoryManager
    from ...infrastructure.platform.bot_manager import BotManager
    from .task_guard import TaskGuard


class IncrementalAnalysisService:
    """增量分析服务 - 处理滑动窗口增量批次分析与最终合并报告生成。"""

    config_manager: ConfigManager
    bot_manager: BotManager
    history_manager: HistoryManager
    llm_analyzer: IAnalysisProvider
    statistics_service: StatisticsService
    analysis_domain_service: AnalysisDomainService
    task_guard: TaskGuard
    incremental_store: IIncrementalStore | None
    incremental_merge_service: IncrementalMergeService | None
    checkpoint_store: ICheckpointStore | None
    _message_cleaner: MessageCleanerService

    def __init__(
        self,
        config_manager: ConfigManager,
        bot_manager: BotManager,
        history_manager: HistoryManager,
        llm_analyzer: IAnalysisProvider,
        statistics_service: StatisticsService,
        analysis_domain_service: AnalysisDomainService,
        task_guard: TaskGuard,
        incremental_store: IIncrementalStore | None = None,
        incremental_merge_service: IncrementalMergeService | None = None,
        checkpoint_store: ICheckpointStore | None = None,
    ) -> None:
        """初始化增量分析服务。

        Args:
            config_manager: 配置提供者。
            bot_manager: 机器人多平台管理器。
            history_manager: 历史持久化管理器。
            llm_analyzer: LLM 语义分析器。
            statistics_service: 统计领域服务。
            analysis_domain_service: 分析领域服务。
            task_guard: 任务排他锁守卫。
            incremental_store: 增量存储仓储。
            incremental_merge_service: 增量合并领域服务。
            checkpoint_store: 检查点仓储。
        """
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.history_manager = history_manager
        self.llm_analyzer = llm_analyzer
        self.statistics_service = statistics_service
        self.analysis_domain_service = analysis_domain_service
        self.task_guard = task_guard
        self.incremental_store = incremental_store
        self.incremental_merge_service = incremental_merge_service
        self.checkpoint_store = checkpoint_store

    async def execute_incremental_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
    ) -> dict[str, Any]:
        """执行单次增量分析用例（滑动窗口批次架构）。

        Args:
            group_id: 群组 ID。
            platform_id: 平台实例标识。

        Returns:
            包含执行状态、批次摘要及消息计数的字典。

        Raises:
            RuntimeError: 当增量存储仓储未初始化时抛出。
            ValueError: 未找到平台适配器时抛出。
        """
        trace = TraceContext.current()
        if not trace:
            trace = TraceContext.get_or_create(
                group_id=str(group_id),
                platform=platform_id or "",
                trigger_type="incremental",
                auto_bind=True,
            )

        async with self.task_guard.group_lock(group_id, "incremental"):
            analysis_started_at = time_mod.monotonic()
            if not self.incremental_store:
                raise RuntimeError("增量分析未初始化：缺少 IncrementalStore")

            logger.debug(
                f"开始增量分析用例: 群 {group_id}, 平台 {platform_id or '默认'}"
            )

            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            if hasattr(adapter, "is_group_muted"):
                try:
                    if await adapter.is_group_muted(group_id):
                        logger.debug(
                            f"群 {group_id} 开启了全群禁言或对 Bot 禁言，跳过本次增量群分析"
                        )
                        return {"success": False, "reason": "muted"}
                except Exception as e:
                    logger.warning(f"检查群 {group_id} 禁言状态时出错: {e}")

            (
                last_analyzed_ts,
                last_analyzed_message_ids,
            ) = await self.incremental_store.get_last_analyzed_cursor(group_id)
            days = self.config_manager.get_analysis_days()
            days_lookback_ts = int(
                (dt.datetime.now() - dt.timedelta(days=days)).timestamp()
            )
            effective_since_ts = (
                max(last_analyzed_ts, days_lookback_ts)
                if last_analyzed_ts > 0
                else days_lookback_ts
            )

            min_messages = self.config_manager.get_incremental_min_messages()
            max_count = max(self.config_manager.get_max_messages(), min_messages)

            date_str = dt.datetime.now().strftime("%Y-%m-%d")
            pipeline = PipelineContext(
                trace=trace,
                checkpoint_store=self.checkpoint_store,
                group_id=group_id,
                date_str=date_str,
            )

            fetch_started_at = time_mod.monotonic()
            async with pipeline.step(
                AnalysisStage.FETCH_MESSAGES,
                initial_payload={"days": days, "max_count": max_count},
            ) as step:
                raw_messages = await adapter.fetch_messages(
                    group_id=group_id,
                    days=days,
                    max_count=max_count,
                    since_ts=effective_since_ts,
                )
                step.set_payload(
                    raw_count=len(raw_messages),
                    days=days,
                    max_count=max_count,
                )
            raw_count = len(raw_messages)
            fetch_duration = time_mod.monotonic() - fetch_started_at

            if not raw_messages:
                logger.warning(f"群 {group_id} 在最近 {days} 天内无消息或无法获取")
                return {"success": False, "reason": "no_messages", "messages_count": 0}

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
            async with pipeline.step(AnalysisStage.CLEAN_MESSAGES) as step:
                unified_messages = cleaner.clean_messages(
                    raw_messages, bot_self_ids=bot_self_ids, filter_commands=True
                )
                step.set_payload(
                    raw_count=raw_count,
                    cleaned_count=len(unified_messages),
                    dropped_count=max(raw_count - len(unified_messages), 0),
                )
            cleaned_count = len(unified_messages)
            if trace:
                trace.set_context_metrics(
                    raw_message_count=raw_count,
                    cleaned_message_count=cleaned_count,
                    incremental_batches=1,
                )

            unified_messages = [
                msg
                for msg in unified_messages
                if msg.timestamp >= days_lookback_ts
                and (
                    last_analyzed_ts <= 0
                    or msg.timestamp > last_analyzed_ts
                    or (
                        msg.timestamp == last_analyzed_ts
                        and msg.message_id not in last_analyzed_message_ids
                    )
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

            async with pipeline.step(AnalysisStage.STATS_ANALYSIS) as step:
                statistics = await asyncio.to_thread(
                    self.statistics_service.calculate_group_statistics, unified_messages
                )
                user_activity = await asyncio.to_thread(
                    self.analysis_domain_service.analyze_user_activity,
                    unified_messages,
                    bot_self_ids,
                )
                step.set_payload(
                    messages_analyzed=len(unified_messages),
                    participants=len(user_activity) if user_activity else 0,
                )

            hourly_msg_counts, hourly_char_counts = compute_hourly_counts(
                unified_messages
            )

            topics_per_batch = self.config_manager.get_incremental_topics_per_batch()
            quotes_per_batch = self.config_manager.get_incremental_quotes_per_batch()

            topic_enabled = self.config_manager.get_topic_analysis_enabled()
            golden_quote_enabled = (
                self.config_manager.get_golden_quote_analysis_enabled()
            )
            chat_quality_enabled = (
                self.config_manager.get_chat_quality_analysis_enabled()
            )

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
                async with pipeline.step(AnalysisStage.LLM_ANALYSIS) as step:
                    async with self.task_guard.llm_slot(group_id, "incremental"):
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
                    step.set_payload(
                        topics_count=len(topics),
                        quotes_count=len(golden_quotes),
                        prompt_tokens=getattr(token_usage, "prompt_tokens", 0),
                        completion_tokens=getattr(token_usage, "completion_tokens", 0),
                        total_tokens=getattr(token_usage, "total_tokens", 0),
                    )

            user_stats = convert_user_activity_for_merge(
                user_activity, unified_messages
            )
            emoji_stats = {
                "face_count": statistics.emoji_statistics.face_count,
                "mface_count": statistics.emoji_statistics.mface_count,
                "bface_count": statistics.emoji_statistics.bface_count,
                "sface_count": statistics.emoji_statistics.sface_count,
                "other_emoji_count": statistics.emoji_statistics.other_emoji_count,
                "face_details": statistics.emoji_statistics.face_details,
            }
            new_topics = [
                {
                    "topic": t.topic,
                    "contributors": t.contributors,
                    "detail": t.detail,
                    "contributor_ids": t.contributor_ids,
                }
                for t in topics
            ]
            new_quotes = [
                {
                    "content": q.content,
                    "sender": q.sender,
                    "reason": q.reason,
                    "user_id": q.user_id,
                }
                for q in golden_quotes
            ]
            token_usage_dict = {
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
            }

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

            participant_ids = list({msg.sender_id for msg in unified_messages})
            last_message_timestamp = max(
                (msg.timestamp for msg in unified_messages), default=0
            )
            characters_count = sum(msg.get_text_length() for msg in unified_messages)

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

            if not await self.incremental_store.save_batch(batch):
                return {
                    "success": False,
                    "reason": "batch_persistence_failed",
                    "messages_count": 0,
                }

            if self.checkpoint_store:
                try:
                    cur_trace_id = trace.trace_id if trace else ""
                    self.checkpoint_store.save_checkpoint(
                        group_id=group_id,
                        date_str=date_str,
                        stage_name=f"INCREMENTAL_BATCH_{batch.batch_id[:8]}",
                        data=batch.to_dict(),
                        trace_id=cur_trace_id,
                    )
                except Exception as e:
                    logger.warning(f"保存增量批次 Checkpoint 失败: {e}")

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
        """基于滑动窗口内的增量批次合并生成最终日报结果。

        Args:
            group_id: 群组 ID。
            platform_id: 平台实例标识。

        Returns:
            包含完整 analysis_result 的字典。

        Raises:
            RuntimeError: 当增量仓储或合并服务未初始化时抛出。
            ValueError: 未找到平台适配器时抛出。
        """
        async with self.task_guard.group_lock(group_id, "final"):
            if not self.incremental_store or not self.incremental_merge_service:
                raise RuntimeError(
                    "增量分析未初始化：缺少 IncrementalStore 或 IncrementalMergeService"
                )

            logger.info(
                f"开始增量最终报告: 群 {group_id}, 平台 {platform_id or '默认'}"
            )

            analysis_days = self.config_manager.get_analysis_days()
            window_end = time_mod.time()
            window_start = window_end - (analysis_days * 24 * 3600)

            batches = await self.incremental_store.query_batches(
                group_id, window_start, window_end
            )

            if not batches:
                logger.warning(
                    f"群 {group_id} 滑动窗口内无增量分析数据，无法生成最终报告"
                )
                return {"success": False, "reason": "no_incremental_data"}

            state = self.incremental_merge_service.merge_batches(
                batches, window_start, window_end
            )

            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            if hasattr(adapter, "is_group_muted"):
                try:
                    if await adapter.is_group_muted(group_id):
                        logger.info(
                            f"群 {group_id} 开启了全群禁言或对 Bot 禁言，跳过本次增量最终报告生成"
                        )
                        return {"success": False, "reason": "muted"}
                except Exception as e:
                    logger.warning(f"检查群 {group_id} 禁言状态时出错: {e}")

            user_titles = []
            user_title_enabled = self.config_manager.get_user_title_analysis_enabled()
            unified_msg_origin = (
                f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
            )

            if user_title_enabled and state.user_activities:
                max_user_titles = self.config_manager.get_max_user_titles()
                top_users = state.get_user_activity_ranking(max_user_titles)

                try:
                    async with self.task_guard.llm_slot(
                        group_id, "incremental_final_title"
                    ):
                        logger.debug(f"[LLM] 已进入称号分析队列 (群: {group_id})")
                        (
                            user_titles_result,
                            title_token_usage,
                        ) = await self.llm_analyzer.analyze_user_titles(
                            messages=[],
                            user_activity=state.user_activities,
                            umo=unified_msg_origin,
                            top_users=top_users,
                        )
                    user_titles = user_titles_result
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

            if (
                self.config_manager.get_chat_quality_analysis_enabled()
                and state.all_quality_reviews
            ):
                try:
                    async with self.task_guard.llm_slot(
                        group_id, "incremental_final_quality"
                    ):
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

            analysis_result = self.incremental_merge_service.build_analysis_result(
                state, user_titles
            )
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
