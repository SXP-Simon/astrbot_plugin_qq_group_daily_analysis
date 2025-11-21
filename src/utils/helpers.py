"""
通用工具函数模块
包含消息分析和其他通用功能
"""

from ...src.models.data_models import TokenUsage
from ...src.core.message_handler import MessageHandler
from ...src.analysis.llm_analyzer import LLMAnalyzer
from ...src.analysis.statistics import UserAnalyzer
from astrbot.api import logger


class MessageAnalyzer:
    """消息分析器 - 整合所有分析功能"""

    def __init__(self, context, config_manager, bot_manager=None):
        self.context = context
        self.config_manager = config_manager
        self.bot_manager = bot_manager
        self.message_handler = MessageHandler(config_manager, bot_manager)
        self.llm_analyzer = LLMAnalyzer(context, config_manager)
        self.user_analyzer = UserAnalyzer(config_manager)

    def _extract_bot_qq_id_from_instance(self, bot_instance):
        """从bot实例中提取QQ号（单个）"""
        if hasattr(bot_instance, "self_id") and bot_instance.self_id:
            return str(bot_instance.self_id)
        elif hasattr(bot_instance, "qq") and bot_instance.qq:
            return str(bot_instance.qq)
        elif hasattr(bot_instance, "user_id") and bot_instance.user_id:
            return str(bot_instance.user_id)
        return None

    async def set_bot_instance(self, bot_instance, platform_id=None):
        """设置bot实例（保持向后兼容）"""
        if self.bot_manager:
            self.bot_manager.set_bot_instance(bot_instance, platform_id)
        else:
            # 从bot实例提取QQ号并设置为列表
            bot_qq_id = self._extract_bot_qq_id_from_instance(bot_instance)
            if bot_qq_id:
                # 将单个QQ号转换为列表，保持统一处理
                await self.message_handler.set_bot_qq_ids([bot_qq_id])

    async def analyze_messages(
        self, messages: list[dict], group_id: str, unified_msg_origin: str = None
    ) -> dict:
        """完整的消息分析流程"""
        try:
            # 基础统计
            statistics = self.message_handler.calculate_statistics(messages)

            # 用户分析
            user_analysis = self.user_analyzer.analyze_users(messages)

            # 获取活跃用户列表 - 使用get_top_users方法,limit从配置中读取
            max_user_titles = self.config_manager.get_max_user_titles()
            top_users = self.user_analyzer.get_top_users(
                user_analysis, limit=max_user_titles
            )
            logger.info(
                f"获取到 {len(top_users)} 个活跃用户用于称号分析(配置上限: {max_user_titles})"
            )

            # LLM分析 - 使用并发方式
            topics = []
            user_titles = []
            golden_quotes = []
            total_token_usage = TokenUsage()

            # 检查各个分析功能是否启用
            topic_enabled = self.config_manager.get_topic_analysis_enabled()
            user_title_enabled = self.config_manager.get_user_title_analysis_enabled()
            golden_quote_enabled = (
                self.config_manager.get_golden_quote_analysis_enabled()
            )

            # 如果三个分析都启用，使用并发执行
            if topic_enabled and user_title_enabled and golden_quote_enabled:
                # 并发执行所有三个分析任务，传入活跃用户列表
                (
                    topics,
                    user_titles,
                    golden_quotes,
                    total_token_usage,
                ) = await self.llm_analyzer.analyze_all_concurrent(
                    messages, user_analysis, umo=unified_msg_origin, top_users=top_users
                )
            else:
                # 如果只启用部分分析，则按需执行
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
                    # 传入活跃用户列表
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

            # 更新统计数据
            statistics.golden_quotes = golden_quotes
            statistics.token_usage = total_token_usage

            return {
                "statistics": statistics,
                "topics": topics,
                "user_titles": user_titles,
                "user_analysis": user_analysis,
            }

        except Exception as e:
            logger.error(f"消息分析失败: {e}")
            return None
