"""
LLM分析器模块
负责协调各个分析器进行话题分析、用户称号分析和金句分析
"""

import asyncio
from typing import List, Dict, Tuple
from astrbot.api import logger
from ..models.data_models import SummaryTopic, UserTitle, GoldenQuote, TokenUsage
from .analyzers.topic_analyzer import TopicAnalyzer
from .analyzers.user_title_analyzer import UserTitleAnalyzer
from .analyzers.golden_quote_analyzer import GoldenQuoteAnalyzer
from .utils.llm_utils import call_provider_with_retry
from .utils.json_utils import fix_json


class LLMAnalyzer:
    """
    LLM分析器
    作为统一入口，协调各个专门的分析器进行不同类型的分析
    保持向后兼容性，提供原有的接口
    """

    def __init__(self, context, config_manager):
        """
        初始化LLM分析器

        Args:
            context: AstrBot上下文对象
            config_manager: 配置管理器
        """
        self.context = context
        self.config_manager = config_manager

        # 初始化各个专门的分析器
        self.topic_analyzer = TopicAnalyzer(context, config_manager)
        self.user_title_analyzer = UserTitleAnalyzer(context, config_manager)
        self.golden_quote_analyzer = GoldenQuoteAnalyzer(context, config_manager)

    async def analyze_topics(
        self, messages: List[Dict], umo: str = None
    ) -> Tuple[List[SummaryTopic], TokenUsage]:
        """
        使用LLM分析话题
        保持原有接口，委托给专门的TopicAnalyzer处理

        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符

        Returns:
            (话题列表, Token使用统计)
        """
        try:
            logger.info("开始话题分析")
            return await self.topic_analyzer.analyze_topics(messages, umo)
        except Exception as e:
            logger.error(f"话题分析失败: {e}")
            return [], TokenUsage()

    async def analyze_user_titles(
        self,
        messages: List[Dict],
        user_analysis: Dict,
        umo: str = None,
        top_users: List[Dict] = None,
    ) -> Tuple[List[UserTitle], TokenUsage]:
        """
        使用LLM分析用户称号
        保持原有接口，委托给专门的UserTitleAnalyzer处理

        Args:
            messages: 群聊消息列表
            user_analysis: 用户分析统计
            umo: 模型唯一标识符
            top_users: 活跃用户列表(可选)

        Returns:
            (用户称号列表, Token使用统计)
        """
        try:
            logger.info("开始用户称号分析")
            return await self.user_title_analyzer.analyze_user_titles(
                messages, user_analysis, umo, top_users
            )
        except Exception as e:
            logger.error(f"用户称号分析失败: {e}")
            return [], TokenUsage()

    async def analyze_golden_quotes(
        self, messages: List[Dict], umo: str = None
    ) -> Tuple[List[GoldenQuote], TokenUsage]:
        """
        使用LLM分析群聊金句
        保持原有接口，委托给专门的GoldenQuoteAnalyzer处理

        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符

        Returns:
            (金句列表, Token使用统计)
        """
        try:
            logger.info("开始金句分析")
            return await self.golden_quote_analyzer.analyze_golden_quotes(messages, umo)
        except Exception as e:
            logger.error(f"金句分析失败: {e}")
            return [], TokenUsage()

    async def analyze_all_concurrent(
        self,
        messages: List[Dict],
        user_analysis: Dict,
        umo: str = None,
        top_users: List[Dict] = None,
    ) -> Tuple[List[SummaryTopic], List[UserTitle], List[GoldenQuote], TokenUsage]:
        """
        并发执行所有分析任务（话题、用户称号、金句）

        Args:
            messages: 群聊消息列表
            user_analysis: 用户分析统计
            umo: 模型唯一标识符
            top_users: 活跃用户列表(可选)

        Returns:
            (话题列表, 用户称号列表, 金句列表, 总Token使用统计)
        """
        try:
            logger.info("开始并发执行所有分析任务")

            # 并发执行三个分析任务
            results = await asyncio.gather(
                self.topic_analyzer.analyze_topics(messages, umo),
                self.user_title_analyzer.analyze_user_titles(
                    messages, user_analysis, umo, top_users
                ),
                self.golden_quote_analyzer.analyze_golden_quotes(messages, umo),
                return_exceptions=True,
            )

            # 处理结果
            topics, topic_usage = [], TokenUsage()
            user_titles, title_usage = [], TokenUsage()
            golden_quotes, quote_usage = [], TokenUsage()

            # 话题分析结果
            if isinstance(results[0], Exception):
                logger.error(f"话题分析失败: {results[0]}")
            else:
                topics, topic_usage = results[0]

            # 用户称号分析结果
            if isinstance(results[1], Exception):
                logger.error(f"用户称号分析失败: {results[1]}")
            else:
                user_titles, title_usage = results[1]

            # 金句分析结果
            if isinstance(results[2], Exception):
                logger.error(f"金句分析失败: {results[2]}")
            else:
                golden_quotes, quote_usage = results[2]

            # 合并Token使用统计
            total_usage = TokenUsage(
                prompt_tokens=topic_usage.prompt_tokens
                + title_usage.prompt_tokens
                + quote_usage.prompt_tokens,
                completion_tokens=topic_usage.completion_tokens
                + title_usage.completion_tokens
                + quote_usage.completion_tokens,
                total_tokens=topic_usage.total_tokens
                + title_usage.total_tokens
                + quote_usage.total_tokens,
            )

            logger.info(
                f"并发分析完成 - 话题: {len(topics)}, 称号: {len(user_titles)}, 金句: {len(golden_quotes)}"
            )
            return topics, user_titles, golden_quotes, total_usage

        except Exception as e:
            logger.error(f"并发分析失败: {e}")
            return [], [], [], TokenUsage()

    # 向后兼容的方法，保持原有调用方式
    async def _call_provider_with_retry(
        self,
        provider,
        prompt: str,
        max_tokens: int,
        temperature: float,
        umo: str = None,
    ):
        """
        向后兼容的LLM调用方法
        现在委托给llm_utils模块处理

        Args:
            provider: LLM服务商实例或None
            prompt: 输入的提示语
            max_tokens: 最大生成token数
            temperature: 采样温度
            umo: 指定使用的模型唯一标识符

        Returns:
            LLM生成的结果
        """
        return await call_provider_with_retry(
            self.context, self.config_manager, prompt, max_tokens, temperature, umo
        )

    def _fix_json(self, text: str) -> str:
        """
        向后兼容的JSON修复方法
        现在委托给json_utils模块处理

        Args:
            text: 需要修复的JSON文本

        Returns:
            修复后的JSON文本
        """
        return fix_json(text)
