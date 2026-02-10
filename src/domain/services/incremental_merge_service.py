"""
增量合并领域服务

负责将 IncrementalState 累积数据转换为现有实体类型，
以便复用现有的报告生成器和分发器。

核心职责：
- IncrementalState → GroupStatistics（含 ActivityVisualization、EmojiStatistics）
- IncrementalState → list[SummaryTopic]
- IncrementalState → list[GoldenQuote]
"""

from ...domain.entities.incremental_state import IncrementalState
from ...domain.models.data_models import (
    ActivityVisualization,
    EmojiStatistics,
    GoldenQuote,
    GroupStatistics,
    SummaryTopic,
    TokenUsage,
)
from ...utils.logger import logger


class IncrementalMergeService:
    """
    增量合并服务

    将一天内累积的增量分析状态转换为现有报告系统所需的数据结构，
    确保增量模式下生成的最终报告与传统单次分析报告格式完全一致。
    """

    def build_final_statistics(self, state: IncrementalState) -> GroupStatistics:
        """
        从增量状态构建最终的群组统计数据。

        将 IncrementalState 中的累积数据映射到 GroupStatistics，
        包含完整的 24 小时活跃度分布、表情统计和 token 消耗。

        Args:
            state: 当天的增量分析状态

        Returns:
            GroupStatistics: 与传统分析格式一致的统计数据
        """
        # 构建 24 小时活跃度分布
        hourly_activity = {}
        for hour in range(24):
            hour_key = str(hour)
            hourly_activity[hour] = state.hourly_message_counts.get(hour_key, 0)

        # 获取高峰时段
        peak_hours = state.get_peak_hours(3)

        # 构建用户活跃排名
        user_ranking = state.get_user_activity_ranking(10)

        # 构建活跃度可视化数据
        activity_visualization = ActivityVisualization(
            hourly_activity=hourly_activity,
            daily_activity={state.date_str: state.total_message_count},
            user_activity_ranking=user_ranking,
            peak_hours=peak_hours,
            activity_heatmap_data={},
        )

        # 构建表情统计
        emoji_statistics = self._build_emoji_statistics(state)

        # 构建 token 消耗
        token_usage = TokenUsage(
            prompt_tokens=state.total_token_usage.get("prompt_tokens", 0),
            completion_tokens=state.total_token_usage.get("completion_tokens", 0),
            total_tokens=state.total_token_usage.get("total_tokens", 0),
        )

        # 获取最活跃时段描述
        most_active_period = state.get_most_active_period()

        statistics = GroupStatistics(
            message_count=state.total_message_count,
            total_characters=state.total_character_count,
            participant_count=len(state.all_participant_ids),
            most_active_period=most_active_period,
            golden_quotes=[],  # 金句通过 build_quotes_for_report 单独构建
            emoji_count=emoji_statistics.total_emoji_count,
            emoji_statistics=emoji_statistics,
            activity_visualization=activity_visualization,
            token_usage=token_usage,
        )

        logger.debug(
            f"从增量状态构建统计: "
            f"消息数={state.total_message_count}, "
            f"参与人数={len(state.all_participant_ids)}, "
            f"话题数={len(state.topics)}, "
            f"金句数={len(state.golden_quotes)}"
        )

        return statistics

    def build_topics_for_report(self, state: IncrementalState) -> list[SummaryTopic]:
        """
        从增量状态构建报告用的话题列表。

        将 IncrementalState 中累积的话题字典转换为 SummaryTopic 实例列表。

        Args:
            state: 当天的增量分析状态

        Returns:
            list[SummaryTopic]: 话题列表，格式与传统分析结果一致
        """
        topics = []
        for topic_dict in state.topics:
            topic = SummaryTopic(
                topic=topic_dict.get("topic", "未知话题"),
                contributors=topic_dict.get("contributors", []),
                detail=topic_dict.get("detail", ""),
            )
            topics.append(topic)

        logger.debug(f"从增量状态构建了 {len(topics)} 个话题")
        return topics

    def build_quotes_for_report(self, state: IncrementalState) -> list[GoldenQuote]:
        """
        从增量状态构建报告用的金句列表。

        将 IncrementalState 中累积的金句字典转换为 GoldenQuote 实例列表。

        Args:
            state: 当天的增量分析状态

        Returns:
            list[GoldenQuote]: 金句列表，格式与传统分析结果一致
        """
        quotes = []
        for quote_dict in state.golden_quotes:
            quote = GoldenQuote(
                content=quote_dict.get("content", ""),
                sender=quote_dict.get("sender", ""),
                reason=quote_dict.get("reason", ""),
                user_id=str(quote_dict.get("user_id", "")),
            )
            quotes.append(quote)

        logger.debug(f"从增量状态构建了 {len(quotes)} 条金句")
        return quotes

    def build_analysis_result(
        self,
        state: IncrementalState,
        user_titles: list | None = None,
    ) -> dict:
        """
        从增量状态构建完整的 analysis_result 字典。

        该字典格式与 AnalysisApplicationService.execute_daily_analysis()
        返回的 analysis_result 完全一致，可直接传入 ReportDispatcher。

        Args:
            state: 当天的增量分析状态
            user_titles: 用户称号列表（由最终报告时 LLM 分析生成）

        Returns:
            dict: 包含 statistics、topics、user_titles、user_analysis 的结果字典
        """
        statistics = self.build_final_statistics(state)
        topics = self.build_topics_for_report(state)
        golden_quotes = self.build_quotes_for_report(state)

        # 将金句回填到 statistics 中（与传统流程一致）
        statistics.golden_quotes = golden_quotes

        analysis_result = {
            "statistics": statistics,
            "topics": topics,
            "user_titles": user_titles or [],
            "user_analysis": state.user_activities,
        }

        logger.info(
            f"从增量状态构建完整分析结果: "
            f"群={state.group_id}, 日期={state.date_str}, "
            f"消息={state.total_message_count}, "
            f"话题={len(topics)}, "
            f"金句={len(golden_quotes)}, "
            f"批次={state.total_analysis_count}"
        )

        return analysis_result

    def _build_emoji_statistics(self, state: IncrementalState) -> EmojiStatistics:
        """
        从增量状态构建表情统计。

        将 IncrementalState 中的 emoji_counts 字典映射到 EmojiStatistics 字段。

        Args:
            state: 增量分析状态

        Returns:
            EmojiStatistics: 表情统计实例
        """
        emoji_counts = state.emoji_counts
        return EmojiStatistics(
            face_count=emoji_counts.get("face_count", 0),
            mface_count=emoji_counts.get("mface_count", 0),
            bface_count=emoji_counts.get("bface_count", 0),
            sface_count=emoji_counts.get("sface_count", 0),
            other_emoji_count=emoji_counts.get("other_emoji_count", 0),
            face_details=emoji_counts.get("face_details", {}),
        )
