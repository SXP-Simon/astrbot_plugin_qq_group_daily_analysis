"""
分析应用服务 - 应用层
实现“每日群聊分析并生成报告”的核心用例。
负责协调领域服务、基础设施适配器及持久化层。
"""

import asyncio
from typing import Any

from ...domain.models.data_models import TokenUsage
from ...domain.repositories.analysis_repository import IAnalysisProvider
from ...domain.repositories.report_repository import IReportGenerator
from ...domain.services.analysis_domain_service import AnalysisDomainService
from ...domain.services.statistics_service import StatisticsService
from ...utils.logger import logger


class AnalysisApplicationService:
    """分析应用服务 - 协调业务流程"""

    def __init__(
        self,
        config_manager: Any,
        bot_manager: Any,
        history_manager: Any,
        report_generator: IReportGenerator,
        llm_analyzer: IAnalysisProvider,
        statistics_service: StatisticsService,
        analysis_domain_service: AnalysisDomainService,
    ):
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.history_manager = history_manager
        self.report_generator = report_generator
        self.llm_analyzer = llm_analyzer
        self.statistics_service = statistics_service
        self.analysis_domain_service = analysis_domain_service

    async def execute_daily_analysis(
        self, group_id: str, platform_id: str | None = None, manual: bool = False
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
        logger.info(f"开始执行分析用例: 群 {group_id}, 平台 {platform_id or '默认'}")

        # 1. 获取适配器
        adapter = self.bot_manager.get_adapter(platform_id)
        if not adapter:
            raise ValueError(f"未找到平台 {platform_id} 的适配器")

        # 2. 拉取消息
        days = self.config_manager.get_analysis_days()
        max_count = self.config_manager.get_max_messages()

        unified_messages = await adapter.fetch_messages(
            group_id=group_id, days=days, max_count=max_count
        )

        if not unified_messages:
            logger.warning(f"群 {group_id} 在最近 {days} 天内无消息或无法获取")
            return {"success": False, "reason": "no_messages"}

        # 检查最小消息阈值
        if (
            len(unified_messages) < self.config_manager.get_min_messages_threshold()
            and not manual
        ):
            logger.info(
                f"群 {group_id} 消息数 ({len(unified_messages)}) 未达到自动分析阈值"
            )
            return {"success": False, "reason": "below_threshold"}

        # 3. 基础统计 (Domain Service)
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
        golden_quote_enabled = self.config_manager.get_golden_quote_analysis_enabled()

        topics = []
        user_titles = []
        golden_quotes = []
        total_token_usage = TokenUsage()

        # Note: LLMAnalyzer 目前可能只接收 legacy 格式或特定的 UnifiedMessage 适配
        # 暂时转换回 legacy 格式以确保稳定性，直到 LLMAnalyzer 被重构
        legacy_messages = self.statistics_service._convert_to_legacy_dict(
            unified_messages
        )

        unified_msg_origin = (
            f"{platform_id}:GroupMessage:{group_id}" if platform_id else group_id
        )

        if topic_enabled and user_title_enabled and golden_quote_enabled:
            (
                topics,
                user_titles,
                golden_quotes,
                total_token_usage,
            ) = await self.llm_analyzer.analyze_all_concurrent(
                legacy_messages,
                user_activity,
                umo=unified_msg_origin,
                top_users=top_users,
            )
        else:
            # 按需串行执行 (略，实际实现可补全或合并)
            pass

        # 回填结果
        statistics.golden_quotes = golden_quotes
        statistics.token_usage = total_token_usage

        analysis_result = {
            "statistics": statistics,
            "topics": topics,
            "user_titles": user_titles,
            "user_analysis": user_activity,
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
        }
