"""
通用工具函数模块
包含消息分析和其他通用功能
"""

from typing import List, Dict
from ...src.models.data_models import GroupStatistics, SummaryTopic, UserTitle, GoldenQuote, TokenUsage
from ...src.core.message_handler import MessageHandler
from ...src.analysis.llm_analyzer import LLMAnalyzer
from ...src.analysis.statistics import UserAnalyzer


class MessageAnalyzer:
    """消息分析器 - 整合所有分析功能"""

    def __init__(self, context, config_manager):
        self.context = context
        self.config_manager = config_manager
        self.message_handler = MessageHandler(config_manager)
        self.llm_analyzer = LLMAnalyzer(context, config_manager)
        self.user_analyzer = UserAnalyzer(config_manager)

    async def set_bot_instance(self, bot_instance):
        """设置bot实例"""
        await self.message_handler.set_bot_qq_id(bot_instance)

    async def analyze_messages(self, messages: List[Dict], group_id: str) -> Dict:
        """完整的消息分析流程"""
        try:
            # 基础统计
            statistics = self.message_handler.calculate_statistics(messages)

            # 用户分析
            user_analysis = self.user_analyzer.analyze_users(messages)

            # LLM分析
            topics = []
            user_titles = []
            golden_quotes = []
            total_token_usage = TokenUsage()

            # 话题分析
            if self.config_manager.get_topic_analysis_enabled():
                topics, topic_tokens = await self.llm_analyzer.analyze_topics(messages)
                total_token_usage.prompt_tokens += topic_tokens.prompt_tokens
                total_token_usage.completion_tokens += topic_tokens.completion_tokens
                total_token_usage.total_tokens += topic_tokens.total_tokens

            # 用户称号分析
            if self.config_manager.get_user_title_analysis_enabled():
                user_titles, title_tokens = await self.llm_analyzer.analyze_user_titles(messages, user_analysis)
                total_token_usage.prompt_tokens += title_tokens.prompt_tokens
                total_token_usage.completion_tokens += title_tokens.completion_tokens
                total_token_usage.total_tokens += title_tokens.total_tokens

            # 金句分析
            golden_quotes, quote_tokens = await self.llm_analyzer.analyze_golden_quotes(messages)
            total_token_usage.prompt_tokens += quote_tokens.prompt_tokens
            total_token_usage.completion_tokens += quote_tokens.completion_tokens
            total_token_usage.total_tokens += quote_tokens.total_tokens

            # 更新统计数据
            statistics.golden_quotes = golden_quotes
            statistics.token_usage = total_token_usage

            return {
                "statistics": statistics,
                "topics": topics,
                "user_titles": user_titles,
                "user_analysis": user_analysis
            }

        except Exception as e:
            from astrbot.api import logger
            logger.error(f"消息分析失败: {e}")
            return None