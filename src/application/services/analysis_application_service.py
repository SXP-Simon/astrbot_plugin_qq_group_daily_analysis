"""分析应用服务 - 应用层

实现"每日群聊分析并生成报告"及"增量分析"核心用例，协调领域服务、基础设施适配器及持久化层。
"""

from __future__ import annotations

import asyncio
import datetime as dt
import time as time_mod
from typing import TYPE_CHECKING

from ...domain.services.message_cleaner_service import MessageCleanerService
from ...domain.value_objects import TokenUsage
from ...shared.constants import AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from .analysis_recovery_service import AnalysisRecoveryService
from .analysis_serializer import AnalysisResultSerializer
from .incremental_analysis_service import IncrementalAnalysisService
from .incremental_batch_builder import (
    compute_hourly_counts,
    convert_user_activity_for_merge,
)
from .pipeline_context import PipelineContext
from .task_guard import DuplicateGroupTaskError, TaskGuard

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from ...domain.repositories.analysis_repository import IAnalysisProvider
    from ...domain.repositories.persistence_repository import (
        ICheckpointStore,
        IIncrementalStore,
    )
    from ...domain.repositories.report_repository import IReportGenerator
    from ...domain.services.analysis_domain_service import (
        AnalysisDomainService,
        UserActivityStats,
    )
    from ...domain.services.incremental_merge_service import IncrementalMergeService
    from ...domain.services.statistics_service import StatisticsService
    from ...domain.value_objects.unified_message import UnifiedMessage
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.persistence.history_manager import HistoryManager
    from ...infrastructure.platform.bot_manager import BotManager

__all__ = ["AnalysisApplicationService", "DuplicateGroupTaskError"]


class AnalysisApplicationService:
    """分析应用服务 - 协调业务流程（每日分析 + 增量分析 + 断点续跑）。"""

    config_manager: ConfigManager
    bot_manager: BotManager
    history_manager: HistoryManager
    report_generator: IReportGenerator
    llm_analyzer: IAnalysisProvider
    statistics_service: StatisticsService
    analysis_domain_service: AnalysisDomainService
    incremental_store: IIncrementalStore | None
    incremental_merge_service: IncrementalMergeService | None
    checkpoint_store: ICheckpointStore | None
    html_render: Callable[..., object] | None
    _task_guard: TaskGuard
    llm_semaphore: asyncio.Semaphore
    _incremental_service: IncrementalAnalysisService
    _recovery_service: AnalysisRecoveryService

    def __init__(
        self,
        config_manager: ConfigManager,
        bot_manager: BotManager,
        history_manager: HistoryManager,
        report_generator: IReportGenerator,
        llm_analyzer: IAnalysisProvider,
        statistics_service: StatisticsService,
        analysis_domain_service: AnalysisDomainService,
        incremental_store: IIncrementalStore | None = None,
        incremental_merge_service: IncrementalMergeService | None = None,
        checkpoint_store: ICheckpointStore | None = None,
        html_render: Callable[..., object] | None = None,
    ) -> None:
        """初始化分析应用服务。

        Args:
            config_manager: 配置提供者。
            bot_manager: 平台适配器管理器。
            history_manager: 历史持久化管理器。
            report_generator: 报表生成器。
            llm_analyzer: LLM 语义分析提供者。
            statistics_service: 统计领域服务。
            analysis_domain_service: 分析领域服务。
            incremental_store: 增量存储仓储。
            incremental_merge_service: 增量合并领域服务。
            checkpoint_store: 检查点持久化仓储。
            html_render: HTML 渲染函数。
        """
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.history_manager = history_manager
        self.report_generator = report_generator
        self.llm_analyzer = llm_analyzer
        self.statistics_service = statistics_service
        self.analysis_domain_service = analysis_domain_service
        self.incremental_store = incremental_store
        self.incremental_merge_service = incremental_merge_service
        self.checkpoint_store = checkpoint_store
        self.html_render = html_render

        max_concurrent = max(1, int(self.config_manager.get_llm_max_concurrent()))
        self._task_guard = TaskGuard(max_concurrent)
        self.llm_semaphore = self._task_guard.llm_semaphore

        self._incremental_service = IncrementalAnalysisService(
            config_manager=self.config_manager,
            bot_manager=self.bot_manager,
            history_manager=self.history_manager,
            llm_analyzer=self.llm_analyzer,
            statistics_service=self.statistics_service,
            analysis_domain_service=self.analysis_domain_service,
            task_guard=self._task_guard,
            incremental_store=self.incremental_store,
            incremental_merge_service=self.incremental_merge_service,
            checkpoint_store=self.checkpoint_store,
        )

        self._recovery_service = AnalysisRecoveryService(
            config_manager=self.config_manager,
            bot_manager=self.bot_manager,
            history_manager=self.history_manager,
            report_generator=self.report_generator,
            llm_analyzer=self.llm_analyzer,
            statistics_service=self.statistics_service,
            task_guard=self._task_guard,
            checkpoint_store=self.checkpoint_store,
            html_render=self.html_render,
        )

    @property
    def _active_tasks(self):
        """兼容层：活跃任务集合。"""
        return self._task_guard._active_tasks

    @property
    def _locks(self):
        """兼容层：任务锁字典。"""
        return self._task_guard._locks

    def is_group_running(self, group_id: str, task_type: str = "daily") -> bool:
        """检查指定群的特定任务是否正在执行中。

        Args:
            group_id: 群号。
            task_type: 任务类型（默认为 'daily' 分析任务）。

        Returns:
            bool: 是否正在运行。
        """
        return self._task_guard.is_group_running(group_id, task_type)

    def group_lock(self, group_id: str, task_type: str = "analysis"):
        """获取群组排他锁上下文管理器。"""
        return self._task_guard.group_lock(group_id, task_type)

    def _llm_slot(self, group_id: str, stage: str):
        """观察并占用一次 LLM 分析槽位。"""
        return self._task_guard.llm_slot(group_id, stage)

    async def execute_daily_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
        manual: bool = False,
        days: int | None = None,
    ) -> dict[str, object]:
        """执行每日全量分析核心用例。

        Args:
            group_id: 群组 ID。
            platform_id: 平台实例标识。
            manual: 是否为手动触发。
            days: 分析回溯天数。

        Returns:
            包含执行状态与 analysis_result 产物的字典。

        Raises:
            ValueError: 未找到平台适配器时抛出。
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

            adapter = self.bot_manager.get_adapter(platform_id)
            if not adapter:
                raise ValueError(f"未找到平台 {platform_id} 的适配器")

            actual_platform = (
                (
                    self.bot_manager.get_adapter_platform_id(adapter)
                    if hasattr(self.bot_manager, "get_adapter_platform_id")
                    else ""
                )
                or getattr(adapter, "platform_id", "")
                or getattr(adapter, "platform_name", "")
                or (platform_id or "")
            )
            if trace and actual_platform:
                trace.platform = str(actual_platform)

            if hasattr(adapter, "is_group_muted"):
                try:
                    if await adapter.is_group_muted(group_id):
                        logger.info(
                            f"群 {group_id} 开启了全群禁言或对 Bot 禁言，跳过本次群分析"
                        )
                        return {"success": False, "reason": "muted"}
                except Exception as e:
                    logger.warning(f"检查群 {group_id} 禁言状态时出错: {e}")

            date_str = dt.datetime.now().strftime("%Y-%m-%d")
            pipeline = PipelineContext(
                trace=trace,
                checkpoint_store=self.checkpoint_store,
                group_id=group_id,
                date_str=date_str,
            )

            if days is None:
                days = int(self.config_manager.get_analysis_days() or 1)
            else:
                days = int(days)
            max_count = self.config_manager.get_max_messages()

            async with pipeline.step(
                AnalysisStage.FETCH_MESSAGES,
                initial_payload={"days": days, "max_count": max_count},
            ) as step:
                raw_messages = await adapter.fetch_messages(
                    group_id=group_id, days=days, max_count=max_count
                )
                raw_data_size_kb = round(
                    sum(
                        len(
                            (getattr(m, "text_content", "") or "").encode(
                                "utf-8", errors="replace"
                            )
                        )
                        for m in raw_messages
                    )
                    / 1024,
                    2,
                )
                step.set_payload(
                    days=days,
                    max_count=max_count,
                    fetched_count=len(raw_messages),
                    raw_data_size_kb=raw_data_size_kb,
                    source=str(actual_platform or platform_id or ""),
                )
            logger.info(
                "消息拉取完成: group=%s, platform=%s, raw_count=%s, days=%s, max_count=%s",
                group_id,
                actual_platform or platform_id or "unknown",
                len(raw_messages),
                days,
                max_count,
            )

            if not raw_messages:
                skip_msg = f"在最近 {days} 天的时间窗口内未拉取到群聊聊天记录，已安全跳过本次分析"
                logger.warning(f"群 {group_id} 在最近 {days} 天内无消息或无法获取")
                return {
                    "success": False,
                    "reason": "no_messages",
                    "error": skip_msg,
                    "message": skip_msg,
                }

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

            async with pipeline.step(AnalysisStage.CLEAN_MESSAGES) as step:
                clean_start_ts = time_mod.perf_counter()
                unified_messages = cleaner.clean_messages(
                    raw_messages, bot_self_ids=bot_self_ids, filter_commands=True
                )
                clean_duration_s = max(0.001, time_mod.perf_counter() - clean_start_ts)
                cleaned_data_size_kb = round(
                    sum(
                        len(
                            (getattr(m, "text_content", "") or "").encode(
                                "utf-8", errors="replace"
                            )
                        )
                        for m in unified_messages
                    )
                    / 1024,
                    2,
                )
                dropped_cnt = max(len(raw_messages) - len(unified_messages), 0)
                retention = round(
                    len(unified_messages) / max(len(raw_messages), 1) * 100,
                    1,
                )
                cleaning_speed_mps = round(len(raw_messages) / clean_duration_s, 1)
                step.set_payload(
                    raw_count=len(raw_messages),
                    cleaned_count=len(unified_messages),
                    dropped_count=dropped_cnt,
                    retention_rate=retention,
                    cleaned_data_size_kb=cleaned_data_size_kb,
                    cleaning_speed_mps=cleaning_speed_mps,
                    bot_filter_enabled=bool(
                        self.config_manager.get_filter_bot_messages()
                    ),
                )
            if trace:
                trace.set_context_metrics(
                    raw_message_count=len(raw_messages),
                    cleaned_message_count=len(unified_messages),
                )
            logger.info(
                "消息清洗完成: group=%s, platform=%s, cleaned_count=%s, dropped=%s",
                group_id,
                actual_platform or platform_id or "unknown",
                len(unified_messages),
                max(len(raw_messages) - len(unified_messages), 0),
            )

            threshold = self.config_manager.get_min_messages_threshold()
            if len(unified_messages) < threshold and not manual:
                skip_msg = f"群聊有效发言数（{len(unified_messages)} 条）未达到设定的自动分析阈值（{threshold} 条），已安全跳过本次日报生成"
                logger.info(
                    f"群 {group_id} 有效消息数 ({len(unified_messages)}) 未达到自动分析阈值 ({threshold})"
                )
                return {
                    "success": False,
                    "reason": "below_threshold",
                    "error": skip_msg,
                    "message": skip_msg,
                    "cleaned_count": len(unified_messages),
                    "threshold": threshold,
                }

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
                    message_count=getattr(
                        statistics,
                        "message_count",
                        len(unified_messages),
                    ),
                    character_count=getattr(statistics, "total_characters", 0),
                    participant_count=getattr(statistics, "participant_count", 0),
                    most_active_period=getattr(statistics, "most_active_period", ""),
                    emoji_count=getattr(statistics, "emoji_count", 0),
                    active_users_analyzed=len(user_activity) if user_activity else 0,
                )

            max_user_titles = self.config_manager.get_max_user_titles()
            top_users = self.analysis_domain_service.get_top_users(
                user_activity, limit=max_user_titles
            )

            if self.checkpoint_store:
                try:
                    cur_trace_id = trace.trace_id if trace else ""
                    self.checkpoint_store.save_checkpoint(
                        group_id=group_id,
                        date_str=date_str,
                        stage_name=AnalysisStage.CLEAN_MESSAGES.value,
                        data={
                            "group_id": group_id,
                            "platform_id": platform_id,
                            "date_str": date_str,
                            "statistics": self._to_json_friendly(statistics),
                            "user_activity": self._to_json_friendly(user_activity),
                            "top_users": self._to_json_friendly(top_users),
                            "unified_messages": [
                                self._to_json_friendly(m) for m in unified_messages
                            ],
                        },
                        trace_id=cur_trace_id,
                    )
                except Exception as e:
                    logger.warning(f"保存前置 Checkpoint 失败: {e}")

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
                async with pipeline.step(AnalysisStage.LLM_ANALYSIS) as step:
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

                    enabled_count = sum(
                        [
                            bool(topic_enabled),
                            bool(user_title_enabled),
                            bool(golden_quote_enabled),
                            bool(chat_quality_enabled),
                        ]
                    )
                    success_count = sum(
                        [
                            bool(topics) if topic_enabled else False,
                            bool(user_titles) if user_title_enabled else False,
                            bool(golden_quotes) if golden_quote_enabled else False,
                            bool(chat_quality_review)
                            if chat_quality_enabled
                            else False,
                        ]
                    )

                    if enabled_count > 0 and success_count == 0:
                        step.mark_failed(
                            "大模型文本分析所有启用的子任务均调用失败或重试耗尽，已中断后续任务"
                        )
                        if trace:
                            trace.metadata["has_warnings"] = False
                            trace.metadata["failure_stage"] = (
                                AnalysisStage.LLM_ANALYSIS.value
                            )
                        return {
                            "success": False,
                            "reason": "llm_analysis_failed",
                            "error": "大模型文本分析全部子任务失败，已中止后续报告生成与发送",
                        }
                    if enabled_count > 0 and success_count < enabled_count:
                        step.mark_warning(
                            f"大模型文本分析部分子任务未产出结果 ({success_count}/{enabled_count} 成功)"
                        )
                        if trace:
                            trace.metadata["has_warnings"] = True

            statistics.golden_quotes = golden_quotes
            statistics.token_usage = total_token_usage

            analysis_result = {
                "statistics": statistics,
                "topics": topics,
                "user_titles": user_titles,
                "user_analysis": user_activity,
                "chat_quality_review": chat_quality_review,
            }

            async with pipeline.step(
                AnalysisStage.SAVE_SUMMARY,
                save_checkpoint=True,
                serializer=self._serialize_analysis_result,
            ) as step:
                await self.history_manager.save_analysis(group_id, analysis_result)
                if self.checkpoint_store:
                    try:
                        cur_trace_id = trace.trace_id if trace else ""
                        self.checkpoint_store.save_checkpoint(
                            group_id=group_id,
                            date_str=date_str,
                            stage_name=AnalysisStage.LLM_ANALYSIS.value,
                            data=self._serialize_analysis_result(analysis_result),
                            trace_id=cur_trace_id,
                        )
                    except Exception as e:
                        logger.warning(f"保存分析 Checkpoint 失败: {e}")
                step.set_payload(
                    date=date_str,
                    topics_persisted=len(topics),
                    titles_persisted=len(user_titles),
                    checkpoint_saved=bool(self.checkpoint_store),
                )

            return {
                "success": True,
                "analysis_result": analysis_result,
                "messages_count": len(unified_messages),
                "adapter": adapter,
                "group_id": group_id,
                "platform_id": getattr(adapter, "platform_id", platform_id),
            }

    async def rerender_report(
        self,
        group_id: str,
        date_str: str,
        template_name: str,
        platform_id: str | None = None,
        render_format: str = "image",
        trace_id: str | None = None,
    ) -> dict[str, object]:
        """重新渲染历史报告（委托 AnalysisRecoveryService）。"""
        return await self._recovery_service.rerender_report(
            group_id=group_id,
            date_str=date_str,
            template_name=template_name,
            platform_id=platform_id,
            render_format=render_format,
            trace_id=trace_id,
        )

    async def resume_analysis(
        self,
        trace_id: str,
        group_id: str,
        platform_id: str | None = None,
        date_str: str | None = None,
        template_name: str | None = None,
    ) -> dict[str, object]:
        """从上一次 Checkpoint 检查点执行幂等断点续跑（委托 AnalysisRecoveryService）。"""
        return await self._recovery_service.resume_analysis(
            trace_id=trace_id,
            group_id=group_id,
            platform_id=platform_id,
            date_str=date_str,
            template_name=template_name,
            fallback_daily_func=self.execute_daily_analysis,
        )

    async def execute_comic_topic_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
        days: int | None = None,
    ) -> dict[str, object]:
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
                days = int(self.config_manager.get_analysis_days() or 1)
            else:
                days = int(days)
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

    async def execute_incremental_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
    ) -> dict[str, object]:
        """执行单次增量分析（委托 IncrementalAnalysisService）。"""
        return await self._incremental_service.execute_incremental_analysis(
            group_id=group_id,
            platform_id=platform_id,
        )

    async def execute_incremental_final_report(
        self, group_id: str, platform_id: str | None = None
    ) -> dict[str, object]:
        """合并增量批次生成最终报告（委托 IncrementalAnalysisService）。"""
        return await self._incremental_service.execute_incremental_final_report(
            group_id=group_id,
            platform_id=platform_id,
        )

    def _to_json_friendly(self, obj: object) -> object:
        """递归将领域模型转换为 JSON 兼容结构。"""
        return AnalysisResultSerializer.to_json_friendly(obj)

    def _serialize_analysis_result(
        self, analysis_result: dict[str, object]
    ) -> dict[str, object]:
        """序列化领域模型字典为 JSON 友好结构。"""
        return AnalysisResultSerializer.serialize(analysis_result)

    def _deserialize_analysis_result(
        self, data: dict[str, object]
    ) -> dict[str, object]:
        """反序列化 JSON 结构为领域模型字典。"""
        return AnalysisResultSerializer.deserialize(data)

    @staticmethod
    def _compute_hourly_counts(
        messages: list[UnifiedMessage],
    ) -> tuple[dict[int, int], dict[int, int]]:
        """计算小时分布统计。"""
        return compute_hourly_counts(messages)

    @staticmethod
    def _convert_user_activity_for_merge(
        user_activity: Mapping[str, UserActivityStats],
        messages: list[UnifiedMessage],
    ) -> dict[str, dict]:
        """转换用户活跃数据为增量批次结构。"""
        return convert_user_activity_for_merge(user_activity, messages)
