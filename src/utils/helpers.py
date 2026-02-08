"""
通用工具函数模块
包含消息分析和其他通用功能
"""

import asyncio
from typing import Any

from ..analysis.llm_analyzer import LLMAnalyzer
from ..analysis.statistics import UserAnalyzer
from ..core.message_handler import MessageHandler
from ..models.data_models import TokenUsage
from .logger import logger


class MessageAnalyzer:
    """
    业务逻辑：消息分析整合器

    该类作为一个门面（Facade），将消息存储、统计计算、LLM 智能分析以及用户画像分析
    等多个底层组件整合在一起，提供统一的消息分析流程接口。

    Attributes:
        context (Any): AstrBot 上下文环境
        config_manager (Any): 配置管理者实例
        bot_manager (Any, optional): 机器人多实例管理者
        message_handler (MessageHandler): 负责消息过滤和基础统计
        llm_analyzer (LLMAnalyzer): 负责调用大模型进行语义分析
        user_analyzer (UserAnalyzer): 负责用户活跃度及角色分析
    """

    def __init__(
        self, context: Any, config_manager: Any, bot_manager: Any | None = None
    ):
        """
        初始化消息分析器。

        Args:
            context (Any): AstrBot 核心上下文
            config_manager (Any): 插件配置管理器
            bot_manager (Any, optional): 多平台机器人管理器实例
        """
        self.context = context
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.message_handler = MessageHandler(config_manager, bot_manager)
        self.llm_analyzer = LLMAnalyzer(context, config_manager)
        self.user_analyzer = UserAnalyzer(config_manager)

    def _extract_bot_self_id_from_instance(self, bot_instance: Any) -> str | None:
        """
        内部方法：从不同平台的机器人实例中探测其自身 ID。

        Args:
            bot_instance (Any): 宿主机器人实例 (如 OneBot, Discord 实例)

        Returns:
            str | None: 探测到的用户 ID 或 None
        """
        if hasattr(bot_instance, "self_id") and bot_instance.self_id:
            return str(bot_instance.self_id)
        elif hasattr(bot_instance, "user_id") and bot_instance.user_id:
            return str(bot_instance.user_id)
        return None

    async def set_bot_instance(
        self, bot_instance: Any, platform_id: str | None = None
    ) -> None:
        """
        向分析组件注入当前活跃的机器人实例。

        Args:
            bot_instance (Any): 活跃的机器人 SDK 实例
            platform_id (str, optional): 平台标识符，用于多实例路由
        """
        if self.bot_manager:
            self.bot_manager.set_bot_instance(bot_instance, platform_id)
        else:
            # 降级逻辑：仅设置单个默认 ID
            bot_self_id = self._extract_bot_self_id_from_instance(bot_instance)
            if bot_self_id:
                await self.message_handler.set_bot_self_ids([bot_self_id])

    async def analyze_messages(
        self, messages: list[dict], group_id: str, unified_msg_origin: str | None = None
    ) -> dict | None:
        """
        执行完整的群消息流水化分析。

        包含：消息预处理 -> 词频统计 -> 活跃用户识别 -> LLM 摘要/金句提取。

        Args:
            messages (list[dict]): 待处理的原始或统一格式消息字典列表
            group_id (str): 群组 ID，用于上下文标识
            unified_msg_origin (str, optional): 统一消息来源标识

        Returns:
            dict | None: 包含 statistics, topics, user_titles, user_analysis 的字典，失败返回 None
        """
        try:
            # 1. 基础消息统计 (耗时操作，放入线程池避免阻塞事件循环)
            statistics = await asyncio.to_thread(
                self.message_handler.calculate_statistics, messages
            )

            # 2. 用户维度分析 (等级、发言习惯等)
            user_analysis = await asyncio.to_thread(
                self.user_analyzer.analyze_users, messages
            )

            # 3. 筛选分析范围：提取 Top N 活跃用户用于深度称号分析
            max_user_titles = self.config_manager.get_max_user_titles()
            top_users = self.user_analyzer.get_top_users(
                user_analysis, limit=max_user_titles
            )
            logger.info(
                f"已为称号分析筛选出 {len(top_users)} 名活跃用户 (最大限制: {max_user_titles})"
            )

            # 4. LLM 语义分析阶段
            topics = []
            user_titles = []
            golden_quotes = []
            total_token_usage = TokenUsage()

            # 检查开关设置
            topic_enabled = self.config_manager.get_topic_analysis_enabled()
            user_title_enabled = self.config_manager.get_user_title_analysis_enabled()
            golden_quote_enabled = (
                self.config_manager.get_golden_quote_analysis_enabled()
            )

            # 策略：如果多项功能均开启，则通过 LLMAnalyzer 并发调用，显著降低分析总时长
            if topic_enabled and user_title_enabled and golden_quote_enabled:
                (
                    topics,
                    user_titles,
                    golden_quotes,
                    total_token_usage,
                ) = await self.llm_analyzer.analyze_all_concurrent(
                    messages, user_analysis, umo=unified_msg_origin, top_users=top_users
                )
            else:
                # 串行降级路径：根据开关按需串行调用 (适用于 Token 敏感或单项测试)
                if topic_enabled:
                    topics, topic_tokens = await self.llm_analyzer.analyze_topics(
                        messages, umo=unified_msg_origin
                    )
                    total_token_usage.prompt_tokens += topic_tokens.prompt_tokens
                    total_token_usage.completion_tokens += (
                        topic_tokens.completion_tokens
                    )
                    total_token_usage.total_tokens += topic_tokens.total_tokens

                if user_title_enabled:
                    (
                        user_titles,
                        title_tokens,
                    ) = await self.llm_analyzer.analyze_user_titles(
                        messages,
                        user_analysis,
                        umo=unified_msg_origin,
                        top_users=top_users,
                    )
                    total_token_usage.prompt_tokens += title_tokens.prompt_tokens
                    total_token_usage.completion_tokens += (
                        title_tokens.completion_tokens
                    )
                    total_token_usage.total_tokens += title_tokens.total_tokens

                if golden_quote_enabled:
                    (
                        golden_quotes,
                        quote_tokens,
                    ) = await self.llm_analyzer.analyze_golden_quotes(
                        messages, umo=unified_msg_origin
                    )
                    total_token_usage.prompt_tokens += quote_tokens.prompt_tokens
                    total_token_usage.completion_tokens += (
                        quote_tokens.completion_tokens
                    )
                    total_token_usage.total_tokens += quote_tokens.total_tokens

            # 5. 回填分析结果并组装返回字典
            statistics.golden_quotes = golden_quotes
            statistics.token_usage = total_token_usage

            return {
                "statistics": statistics,
                "topics": topics,
                "user_titles": user_titles,
                "user_analysis": user_analysis,
            }

        except Exception as e:
            logger.error(f"消息分析流水线执行失败: {e}")
            return None
