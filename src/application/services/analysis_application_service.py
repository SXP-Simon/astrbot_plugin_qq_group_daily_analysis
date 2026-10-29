"""分析应用服务 - 应用层

实现"每日群聊分析并生成报告"及"增量分析"核心用例，协调领域服务、基础设施适配器及持久化层。
"""

from __future__ import annotations

import asyncio
import datetime as dt
import time as time_mod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...domain.services.message_cleaner_service import MessageCleanerService
from ...domain.value_objects import (
    AnalysisResultPayload,
    DailyAnalysisExecutionResult,
    TokenUsage,
)
from ...shared.constants import AnalysisStage
from ...shared.report_language import apply_auto_language_detection
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
    from collections.abc import Awaitable, Callable, Mapping

    from ...domain.repositories.analysis_repository import IAnalysisProvider
    from ...domain.repositories.persistence_repository import (
        ICheckpointStore,
        IIncrementalStore,
    )
    from ...domain.repositories.platform_adapter_repository import (
        PlatformAdapterProtocol,
    )
    from ...domain.repositories.report_repository import IReportGenerator
    from ...domain.services.analysis_domain_service import (
        AnalysisDomainService,
        UserActivityStats,
    )
    from ...domain.services.incremental_merge_service import IncrementalMergeService
    from ...domain.services.statistics_service import StatisticsService
    from ...domain.value_objects.analysis_results import (
        GoldenQuote,
        GroupStatistics,
        QualityReview,
        SummaryTopic,
        UserTitle,
    )
    from ...domain.value_objects.unified_message import UnifiedMessage
    from ...infrastructure.config.config_manager import ConfigManager
    from ...infrastructure.persistence.history_manager import HistoryManager
    from ...infrastructure.platform.bot_manager import BotManager

__all__ = ["AnalysisApplicationService", "DuplicateGroupTaskError"]


@dataclass(frozen=True)
class AnalysisSections:
    """本次执行实际启用的 LLM 分析模块。"""

    topic: bool
    user_titles: bool
    golden_quotes: bool
    chat_quality: bool


@dataclass
class LLMAnalysisStageResult:
    """单次 LLM 阶段的结构化产物与失败标记。"""

    topics: list[SummaryTopic]
    user_titles: list[UserTitle]
    golden_quotes: list[GoldenQuote]
    chat_quality_review: QualityReview | None
    token_usage: TokenUsage
    failed: bool = False


@dataclass
class CleanedDailyMessages:
    """清洗阶段输出，供后续统计与 LLM 阶段共享。"""

    messages: list[UnifiedMessage]
    bot_self_ids: list[str]
    detected_language: str | None


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
    html_render: Callable[..., Awaitable[str | bytes | None]] | None
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
        html_render: Callable[..., Awaitable[str | bytes | None]] | None = None,
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

    def _resolve_daily_analysis_sections(
        self, requested_sections: list[str] | set[str] | None
    ) -> AnalysisSections:
        """合并调用方选择与配置开关，得到本次实际执行的 LLM 分析模块。

        Args:
            requested_sections: 调用方请求的分析模块；为空时按配置执行。

        Returns:
            AnalysisSections: 本次实际启用的 LLM 分析模块。
        """
        requested = set(requested_sections) if requested_sections is not None else None
        topic = self.config_manager.get_topic_analysis_enabled()
        if requested is not None:
            topic = topic and bool(requested.intersection({"topics", "话题", "topic"}))

        user_titles = self.config_manager.get_user_title_analysis_enabled()
        if requested is not None:
            user_titles = user_titles and bool(
                requested.intersection({"user_titles", "用户称号", "称号"})
            )

        golden_quotes = self.config_manager.get_golden_quote_analysis_enabled()
        if requested is not None:
            golden_quotes = golden_quotes and bool(
                requested.intersection({"golden_quotes", "金句", "quotes"})
            )

        chat_quality = self.config_manager.get_chat_quality_analysis_enabled()
        if requested is not None:
            chat_quality = chat_quality and bool(
                requested.intersection({"chat_quality_review", "聊天质量分析", "质量"})
            )

        return AnalysisSections(
            topic=topic,
            user_titles=user_titles,
            golden_quotes=golden_quotes,
            chat_quality=chat_quality,
        )

    async def execute_daily_analysis(
        self,
        group_id: str,
        platform_id: str | None = None,
        manual: bool = False,
        days: int | None = None,
        analysis_sections: list[str] | set[str] | None = None,
        checkpoint_stage_name: str | None = None,
    ) -> dict[str, object]:
        """执行每日全量或按需分析核心用例。

        Args:
            group_id: 群组 ID。
            platform_id: 平台实例标识。
            manual: 是否为手动触发。
            days: 分析回溯天数。
            analysis_sections: 指定本次需要执行的分析模块集合。为 None 时执行全量。
            checkpoint_stage_name: 持久化 Checkpoint 阶段名称（默认为 LLM_ANALYSIS，按需可传 ON_DEMAND_ANALYSIS）。


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
                self.bot_manager.get_adapter_platform_id(adapter)
                or adapter.platform_id
                or adapter.get_platform_name()
                or (platform_id or "")
            )
            if trace and actual_platform:
                trace.platform = str(actual_platform)

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

            raw_messages = await self._fetch_daily_messages(
                pipeline,
                adapter,
                group_id,
                days,
                max_count,
                str(actual_platform or platform_id or ""),
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

            cleaned_messages = await self._clean_daily_messages(
                pipeline,
                trace,
                adapter,
                raw_messages,
                group_id,
                actual_platform or platform_id or "unknown",
            )
            unified_messages = cleaned_messages.messages
            bot_self_ids = cleaned_messages.bot_self_ids

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

            statistics, user_activity = await self._calculate_daily_statistics(
                pipeline,
                unified_messages,
                bot_self_ids,
            )

            max_user_titles = self.config_manager.get_max_user_titles()
            top_users = self.analysis_domain_service.get_top_users(
                user_activity, limit=max_user_titles
            )

            await asyncio.to_thread(
                self._save_daily_analysis_checkpoint,
                group_id=group_id,
                platform_id=platform_id,
                date_str=date_str,
                trace_id=trace.trace_id if trace else "",
                statistics=statistics,
                user_activity=user_activity,
                top_users=top_users,
                unified_messages=unified_messages,
            )

            sections = self._resolve_daily_analysis_sections(analysis_sections)

            legacy_messages = self.statistics_service._convert_to_legacy_dict(
                unified_messages
            )

            unified_msg_origin = (
                f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
            )
            analysis_stage = "full_manual" if manual else "full_scheduled"

            llm_result = await self._run_llm_analysis_stage(
                pipeline,
                group_id,
                analysis_stage,
                legacy_messages,
                user_activity,
                top_users,
                unified_msg_origin,
                sections,
                trace,
            )
            if llm_result.failed:
                return {
                    "success": False,
                    "reason": "llm_analysis_failed",
                    "error": "大模型文本分析全部子任务失败，已中止后续报告生成与发送",
                }

            statistics.golden_quotes = llm_result.golden_quotes
            statistics.token_usage = llm_result.token_usage

            analysis_result = {
                "statistics": statistics,
                "topics": llm_result.topics,
                "user_titles": llm_result.user_titles,
                "user_analysis": user_activity,
                "chat_quality_review": llm_result.chat_quality_review,
            }

            await self._persist_daily_analysis_summary(
                pipeline=pipeline,
                group_id=group_id,
                date_str=date_str,
                trace_id=trace.trace_id if trace else "",
                checkpoint_stage_name=checkpoint_stage_name,
                analysis_result=analysis_result,
                topics_count=len(llm_result.topics),
                titles_count=len(llm_result.user_titles),
            )

            return {
                "success": True,
                "analysis_result": analysis_result,
                "messages_count": len(unified_messages),
                "adapter": adapter,
                "group_id": group_id,
                "platform_id": adapter.platform_id or platform_id,
            }

    def _save_daily_analysis_checkpoint(
        self,
        *,
        group_id: str,
        platform_id: str | None,
        date_str: str,
        trace_id: str,
        statistics: GroupStatistics,
        user_activity: dict[str, UserActivityStats],
        top_users: list[dict[str, object]],
        unified_messages: list[UnifiedMessage],
    ) -> None:
        """持久化统计阶段之后供恢复流程使用的清洗快照。

        Args:
            group_id: 目标群组 ID。
            platform_id: 实际请求的平台实例标识。
            date_str: 本次分析日期。
            trace_id: 当前 Trace 标识。
            statistics: 已计算的群聊统计结果。
            user_activity: 用户活跃度分析结果。
            top_users: 限定数量后的活跃用户。
            unified_messages: 清洗后的统一消息列表。
        """
        if self.checkpoint_store is None:
            return
        try:
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
                        self._to_json_friendly(message) for message in unified_messages
                    ],
                },
                trace_id=trace_id,
            )
        except Exception as e:
            logger.warning(f"保存前置 Checkpoint 失败: {e}")

    async def _persist_daily_analysis_summary(
        self,
        *,
        pipeline: PipelineContext,
        group_id: str,
        date_str: str,
        trace_id: str,
        checkpoint_stage_name: str | None,
        analysis_result: dict[str, object],
        topics_count: int,
        titles_count: int,
    ) -> None:
        """完成保存摘要阶段并持久化可续跑的最终分析产物。

        Args:
            pipeline: 当前分析的阶段与快照上下文。
            group_id: 目标群组 ID。
            date_str: 本次分析日期。
            trace_id: 当前 Trace 标识。
            checkpoint_stage_name: 本次调用指定的检查点阶段。
            analysis_result: 统计、话题、用户称号和聊天质量产物。
            topics_count: 本次产出的热门话题数量。
            titles_count: 本次产出的用户称号数量。
        """
        async with pipeline.step(
            AnalysisStage.SAVE_SUMMARY,
            save_checkpoint=True,
            serializer=self._serialize_analysis_result,
        ) as step:
            await self.history_manager.save_analysis(
                group_id, analysis_result, date_str=date_str
            )
            if self.checkpoint_store:
                try:
                    await asyncio.to_thread(
                        self.checkpoint_store.save_checkpoint,
                        group_id=group_id,
                        date_str=date_str,
                        stage_name=(
                            checkpoint_stage_name or AnalysisStage.LLM_ANALYSIS.value
                        ),
                        data=self._serialize_analysis_result(analysis_result),
                        trace_id=trace_id,
                    )
                except Exception as e:
                    logger.warning(f"保存分析 Checkpoint 失败: {e}")
            step.set_payload(
                date=date_str,
                topics_persisted=topics_count,
                titles_persisted=titles_count,
                checkpoint_saved=bool(self.checkpoint_store),
            )

    async def _fetch_daily_messages(
        self,
        pipeline: PipelineContext,
        adapter: PlatformAdapterProtocol,
        group_id: str,
        days: int,
        max_count: int,
        source_platform: str,
    ) -> list[UnifiedMessage]:
        """执行 Fetch 阶段并记录拉取数量与原始文本体积。

        Args:
            pipeline: 当前分析的阶段与快照上下文。
            adapter: 已解析的平台消息适配器。
            group_id: 目标群组 ID。
            days: 消息回溯天数。
            max_count: 最大拉取消息数。
            source_platform: 实际使用的平台标识。

        Returns:
            list[UnifiedMessage]: 平台返回的统一消息列表。
        """
        async with pipeline.step(
            AnalysisStage.FETCH_MESSAGES,
            initial_payload={"days": days, "max_count": max_count},
        ) as step:
            raw_messages = await adapter.fetch_messages(
                group_id=group_id, days=days, max_count=max_count
            )
            raw_data_size_kb = round(
                sum(
                    len(message.text_content.encode("utf-8", errors="replace"))
                    for message in raw_messages
                )
                / 1024,
                2,
            )
            step.set_payload(
                days=days,
                max_count=max_count,
                fetched_count=len(raw_messages),
                raw_data_size_kb=raw_data_size_kb,
                source=source_platform,
            )
        return raw_messages

    async def _clean_daily_messages(
        self,
        pipeline: PipelineContext,
        trace: TraceContext | None,
        adapter: PlatformAdapterProtocol,
        raw_messages: list[UnifiedMessage],
        group_id: str,
        actual_platform: str,
    ) -> CleanedDailyMessages:
        """执行 Clean 阶段并生成本次任务使用的报告语言线索。

        Args:
            pipeline: 当前分析的阶段与快照上下文。
            trace: 当前全链路追踪上下文。
            adapter: 已解析的平台消息适配器。
            raw_messages: Fetch 阶段取得的原始统一消息。
            group_id: 目标群组 ID。
            actual_platform: 实际使用的平台标识。

        Returns:
            CleanedDailyMessages: 清洗后的消息、机器人 ID 与识别语言。
        """
        bot_self_ids = list(self.config_manager.get_bot_self_ids() or [])
        for bot_id in adapter.bot_self_ids:
            if bot_id and bot_id not in bot_self_ids:
                bot_self_ids.append(bot_id)
        filter_bot_messages = self.config_manager.get_filter_bot_messages()
        if not filter_bot_messages:
            bot_self_ids = []
        logger.debug(
            "filter_bot_messages=%s, bot_self_ids=%s",
            filter_bot_messages,
            bot_self_ids,
        )

        async with pipeline.step(AnalysisStage.CLEAN_MESSAGES) as step:
            clean_start_ts = time_mod.perf_counter()
            unified_messages = MessageCleanerService().clean_messages(
                raw_messages, bot_self_ids=bot_self_ids, filter_commands=True
            )
            detected_language = apply_auto_language_detection(
                message.text_content for message in unified_messages
            )
            clean_duration_s = max(0.001, time_mod.perf_counter() - clean_start_ts)
            cleaned_data_size_kb = round(
                sum(
                    len(message.text_content.encode("utf-8", errors="replace"))
                    for message in unified_messages
                )
                / 1024,
                2,
            )
            dropped_count = max(len(raw_messages) - len(unified_messages), 0)
            retention = round(
                len(unified_messages) / max(len(raw_messages), 1) * 100,
                1,
            )
            cleaning_speed_mps = round(len(raw_messages) / clean_duration_s, 1)
            step.set_payload(
                raw_count=len(raw_messages),
                cleaned_count=len(unified_messages),
                dropped_count=dropped_count,
                retention_rate=retention,
                cleaned_data_size_kb=cleaned_data_size_kb,
                cleaning_speed_mps=cleaning_speed_mps,
                bot_filter_enabled=bool(filter_bot_messages),
            )

        if trace:
            trace.set_context_metrics(
                raw_message_count=len(raw_messages),
                cleaned_message_count=len(unified_messages),
            )
        logger.info(
            "消息清洗完成: group=%s, platform=%s, cleaned_count=%s, dropped=%s",
            group_id,
            actual_platform,
            len(unified_messages),
            max(len(raw_messages) - len(unified_messages), 0),
        )
        logger.info(
            "报告语言自动判断(auto): %s（按群聊正文投票，某语言占比 >70%% 才判；未命中则不干预）",
            detected_language or "未命中",
        )
        return CleanedDailyMessages(
            messages=unified_messages,
            bot_self_ids=bot_self_ids,
            detected_language=detected_language,
        )

    async def _calculate_daily_statistics(
        self,
        pipeline: PipelineContext,
        unified_messages: list[UnifiedMessage],
        bot_self_ids: list[str],
    ) -> tuple[GroupStatistics, dict[str, UserActivityStats]]:
        """执行 Stats 阶段并记录统计聚合的关键指标。

        Args:
            pipeline: 当前分析的阶段与快照上下文。
            unified_messages: Clean 阶段产出的有效消息。
            bot_self_ids: 当前平台与配置识别出的机器人 ID。

        Returns:
            tuple[GroupStatistics, dict[str, UserActivityStats]]: 群统计和用户活跃度。
        """
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
                message_count=statistics.message_count,
                character_count=statistics.total_characters,
                participant_count=statistics.participant_count,
                most_active_period=statistics.most_active_period,
                emoji_count=statistics.emoji_count,
                active_users_analyzed=len(user_activity) if user_activity else 0,
            )
        return statistics, user_activity

    async def _run_llm_analysis_stage(
        self,
        pipeline: PipelineContext,
        group_id: str,
        analysis_stage: str,
        legacy_messages: list[dict[str, object]],
        user_activity: dict[str, UserActivityStats],
        top_users: list[dict[str, object]],
        unified_msg_origin: str,
        sections: AnalysisSections,
        trace: TraceContext | None,
    ) -> LLMAnalysisStageResult:
        """执行已启用的 LLM 子分析，并集中收敛全失败与部分失败结果。

        Args:
            pipeline: 当前分析的阶段与快照上下文。
            group_id: 目标群组 ID。
            analysis_stage: LLM 并发槽位使用的任务类型。
            legacy_messages: 转换后的兼容消息结构。
            user_activity: Stats 阶段产出的用户活跃数据。
            top_users: 限定人数后的活跃用户列表。
            unified_msg_origin: LLM 分析所使用的平台消息源标识。
            sections: 本次实际启用的 LLM 子分析模块。
            trace: 当前全链路追踪上下文。

        Returns:
            LLMAnalysisStageResult: LLM 产物、Token 统计和全失败标记。
        """
        result = LLMAnalysisStageResult(
            topics=[],
            user_titles=[],
            golden_quotes=[],
            chat_quality_review=None,
            token_usage=TokenUsage(),
        )
        enabled_count = sum(
            (
                sections.topic,
                sections.user_titles,
                sections.golden_quotes,
                sections.chat_quality,
            )
        )
        if enabled_count == 0:
            return result

        async with pipeline.step(AnalysisStage.LLM_ANALYSIS) as step:
            async with self._llm_slot(group_id, analysis_stage):
                logger.debug(
                    f"[LLM] 已进入普通全量分析队列 (群: {group_id}, stage: {analysis_stage})"
                )
                (
                    result.topics,
                    result.user_titles,
                    result.golden_quotes,
                    result.token_usage,
                    result.chat_quality_review,
                ) = await self.llm_analyzer.analyze_all_concurrent(
                    legacy_messages,
                    user_activity,
                    umo=unified_msg_origin,
                    top_users=top_users,
                    topic_enabled=sections.topic,
                    user_title_enabled=sections.user_titles,
                    golden_quote_enabled=sections.golden_quotes,
                    chat_quality_enabled=sections.chat_quality,
                )

            success_count = sum(
                (
                    bool(result.topics) if sections.topic else False,
                    bool(result.user_titles) if sections.user_titles else False,
                    bool(result.golden_quotes) if sections.golden_quotes else False,
                    bool(result.chat_quality_review)
                    if sections.chat_quality
                    else False,
                )
            )
            if success_count == 0:
                step.mark_failed(
                    "大模型文本分析所有启用的子任务均调用失败或重试耗尽，已中断后续任务"
                )
                if trace:
                    trace.metadata["has_warnings"] = False
                    trace.metadata["failure_stage"] = AnalysisStage.LLM_ANALYSIS.value
                result.failed = True
            elif success_count < enabled_count:
                step.mark_warning(
                    f"大模型文本分析部分子任务未产出结果 ({success_count}/{enabled_count} 成功)"
                )
                if trace:
                    trace.metadata["has_warnings"] = True
        return result

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
        checkpoint_trace_id: str | None = None,
    ) -> dict[str, object]:
        """从上一次 Checkpoint 检查点执行幂等断点续跑（委托 AnalysisRecoveryService）。"""
        return await self._recovery_service.resume_analysis(
            trace_id=trace_id,
            group_id=group_id,
            platform_id=platform_id,
            date_str=date_str,
            template_name=template_name,
            checkpoint_trace_id=checkpoint_trace_id,
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
    ) -> DailyAnalysisExecutionResult | dict[str, object]:
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
    ) -> AnalysisResultPayload:
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
