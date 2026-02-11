"""
增量合并领域服务

负责将 IncrementalBatch 列表合并为 IncrementalState，
以及将 IncrementalState 累积数据转换为现有实体类型，
以便复用现有的报告生成器和分发器。

核心职责：
- merge_batches: 将多个 IncrementalBatch 合并为一个 IncrementalState（滑动窗口聚合）
- IncrementalState → GroupStatistics（含 ActivityVisualization、EmojiStatistics）
- IncrementalState → list[SummaryTopic]
- IncrementalState → list[GoldenQuote]
"""

import time

from ...domain.entities.incremental_state import IncrementalBatch, IncrementalState
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

    将滑动窗口内的多个批次数据合并为报告所需的数据结构，
    确保增量模式下生成的最终报告与传统单次分析报告格式完全一致。
    """

    def merge_batches(
        self,
        batches: list[IncrementalBatch],
        window_start: float,
        window_end: float,
    ) -> IncrementalState:
        """
        从批次列表合并构建 IncrementalState。

        遍历所有批次，累加统计数据并对话题和金句执行去重，
        生成可用于报告的聚合视图。

        Args:
            batches: 时间窗口内的批次列表（按时间升序）
            window_start: 窗口起始时间戳（epoch）
            window_end: 窗口结束时间戳（epoch）

        Returns:
            IncrementalState: 合并后的聚合视图
        """
        state = IncrementalState(
            group_id=batches[0].group_id if batches else "",
            window_start=window_start,
            window_end=window_end,
            total_analysis_count=len(batches),
            created_at=window_start,
            updated_at=time.time(),
        )

        for batch in batches:
            # 累加消息和字符计数
            state.total_message_count += batch.messages_count
            state.total_character_count += batch.characters_count

            # 合并每小时消息分布（按键累加）
            for hour_key, count in batch.hourly_msg_counts.items():
                hour_str = str(hour_key)
                state.hourly_message_counts[hour_str] = (
                    state.hourly_message_counts.get(hour_str, 0) + count
                )

            # 合并每小时字符分布
            for hour_key, count in batch.hourly_char_counts.items():
                hour_str = str(hour_key)
                state.hourly_character_counts[hour_str] = (
                    state.hourly_character_counts.get(hour_str, 0) + count
                )

            # 合并用户统计（按用户累加消息数、字符数等）
            for user_id, stats in batch.user_stats.items():
                if user_id not in state.user_activities:
                    state.user_activities[user_id] = {
                        "nickname": stats.get("nickname", stats.get("name", user_id)),
                        "message_count": 0,
                        "char_count": 0,
                        "emoji_count": 0,
                        "reply_count": 0,
                        "hours": {},
                        "last_message_time": 0,
                    }
                existing = state.user_activities[user_id]
                existing["message_count"] += stats.get("message_count", 0)
                existing["char_count"] += stats.get("char_count", 0)
                existing["emoji_count"] += stats.get("emoji_count", 0)
                existing["reply_count"] += stats.get("reply_count", 0)

                # 合并每小时统计
                # 兼容旧版本 (active_hours 是 list) 和新版本 (hours 是 dict)
                batch_hours = stats.get("hours", {})
                if isinstance(batch_hours, dict):
                    # 现代 schema: hours 是 dict {hour: count}
                    for h_str, h_count in batch_hours.items():
                        h_int = int(h_str)
                        existing["hours"][h_int] = (
                            existing["hours"].get(h_int, 0) + h_count
                        )
                else:
                    # 兼容旧 schema: 只有 active_hours (list)
                    active_hours = stats.get("active_hours", [])
                    for h in active_hours:
                        h_int = int(h)
                        existing["hours"][h_int] = existing["hours"].get(h_int, 0) + 1

                # 取最后消息时间的较大值
                batch_last = stats.get("last_message_time", 0)
                if batch_last > existing.get("last_message_time", 0):
                    existing["last_message_time"] = batch_last

                # 更新昵称（使用最新批次的昵称）
                nickname = stats.get("nickname", stats.get("name", ""))
                if nickname:
                    existing["nickname"] = nickname

            # 合并表情统计（按键累加）
            for emoji_key, count in batch.emoji_stats.items():
                current_val = state.emoji_counts.get(emoji_key, 0)
                if isinstance(count, dict):
                    # 如果是嵌套字典（如 face_details），则合并内部计数
                    if not isinstance(current_val, dict):
                        current_val = {}

                    for sub_key, sub_count in count.items():
                        current_val[sub_key] = current_val.get(sub_key, 0) + sub_count

                    state.emoji_counts[emoji_key] = current_val
                else:
                    # 如果是数值，直接累加
                    if isinstance(current_val, dict):
                        # 异常情况：现有值是字典但新值是数字，通常不应发生，除非 schema 变更
                        # 此时保留字典，忽略数字或记录错误，这里选择保留字典
                        continue

                    state.emoji_counts[emoji_key] = current_val + count

            # 合并话题（去重）
            for topic in batch.topics:
                if not IncrementalState.is_duplicate_topic(topic, state.topics):
                    state.topics.append(topic)

            # 合并金句（去重）
            for quote in batch.golden_quotes:
                if not IncrementalState.is_duplicate_quote(quote, state.golden_quotes):
                    state.golden_quotes.append(quote)

            # 累加 token 消耗
            for token_key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                state.total_token_usage[token_key] = state.total_token_usage.get(
                    token_key, 0
                ) + batch.token_usage.get(token_key, 0)

            # 合并参与者 ID（取并集）
            state.all_participant_ids.update(batch.participant_ids)

            # 记录最后分析消息时间戳（取最大值）
            if batch.last_message_timestamp > state.last_analyzed_message_timestamp:
                state.last_analyzed_message_timestamp = batch.last_message_timestamp

        logger.info(
            f"合并批次完成: 群={state.group_id}, "
            f"窗口={state.get_window_date_str()}, "
            f"批次数={len(batches)}, "
            f"总消息={state.total_message_count}, "
            f"话题={len(state.topics)}, 金句={len(state.golden_quotes)}"
        )

        return state

    def build_final_statistics(self, state: IncrementalState) -> GroupStatistics:
        """
        从增量状态构建最终的群组统计数据。

        将 IncrementalState 中的累积数据映射到 GroupStatistics，
        包含完整的 24 小时活跃度分布、表情统计和 token 消耗。

        Args:
            state: 由 merge_batches 合并生成的增量分析状态

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
            daily_activity={state.get_window_date_str(): state.total_message_count},
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
            state: 由 merge_batches 合并生成的增量分析状态

        Returns:
            list[SummaryTopic]: 话题列表，格式与传统分析结果一致
        """
        topics = []
        for topic_dict in state.topics:
            topic = SummaryTopic(
                topic=topic_dict.get("topic", "未知话题"),
                contributors=topic_dict.get("contributors", []),
                detail=topic_dict.get("detail", ""),
                contributor_ids=topic_dict.get("contributor_ids", []),
            )
            topics.append(topic)

        logger.debug(f"从增量状态构建了 {len(topics)} 个话题")
        return topics

    def build_quotes_for_report(self, state: IncrementalState) -> list[GoldenQuote]:
        """
        从增量状态构建报告用的金句列表。

        将 IncrementalState 中累积的金句字典转换为 GoldenQuote 实例列表。

        Args:
            state: 由 merge_batches 合并生成的增量分析状态

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
            state: 由 merge_batches 合并生成的增量分析状态
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
            f"群={state.group_id}, 窗口={state.get_window_date_str()}, "
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
