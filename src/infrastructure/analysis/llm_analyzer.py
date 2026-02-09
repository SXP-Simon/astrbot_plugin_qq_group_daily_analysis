"""
LLM分析器模块
负责协调各个分析器进行话题分析、用户称号分析和金句分析
"""

import asyncio

from ...domain.models.data_models import (
    GoldenQuote,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)
from ...utils.logger import logger
from .analyzers.golden_quote_analyzer import GoldenQuoteAnalyzer
from .analyzers.topic_analyzer import TopicAnalyzer
from .analyzers.user_title_analyzer import UserTitleAnalyzer
from .utils.json_utils import fix_json
from .utils.llm_utils import call_provider_with_retry


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
        self, messages: list[dict], umo: str = None, session_id: str = None
    ) -> tuple[list[SummaryTopic], TokenUsage]:
        """
        使用LLM分析话题
        保持原有接口，委托给专门的TopicAnalyzer处理

        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符
            session_id: 会话ID (用于调试模式)

        Returns:
            (话题列表, Token使用统计)
        """
        try:
            if not session_id:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if umo:
                    # Sanitize umo for filename (replace : with _)
                    safe_umo = umo.replace(":", "_")
                    session_id = f"{timestamp}_{safe_umo}"
                else:
                    session_id = timestamp

            logger.info(f"开始话题分析, session_id: {session_id}")
            return await self.topic_analyzer.analyze_topics(messages, umo, session_id)
        except Exception as e:
            logger.error(f"话题分析失败: {e}")
            return [], TokenUsage()

    async def analyze_user_titles(
        self,
        messages: list[dict],
        user_analysis: dict,
        umo: str = None,
        top_users: list[dict] = None,
        session_id: str = None,
    ) -> tuple[list[UserTitle], TokenUsage]:
        """
        使用LLM分析用户称号
        保持原有接口，委托给专门的UserTitleAnalyzer处理

        Args:
            messages: 群聊消息列表
            user_analysis: 用户分析统计
            umo: 模型唯一标识符
            top_users: 活跃用户列表(可选)
            session_id: 会话ID (用于调试模式)

        Returns:
            (用户称号列表, Token使用统计)
        """
        try:
            if not session_id:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if umo:
                    safe_umo = umo.replace(":", "_")
                    session_id = f"{timestamp}_{safe_umo}"
                else:
                    session_id = timestamp

            logger.info(f"开始用户称号分析, session_id: {session_id}")
            return await self.user_title_analyzer.analyze_user_titles(
                messages, user_analysis, umo, top_users, session_id
            )
        except Exception as e:
            logger.error(f"用户称号分析失败: {e}")
            return [], TokenUsage()

    async def analyze_golden_quotes(
        self, messages: list[dict], umo: str = None, session_id: str = None
    ) -> tuple[list[GoldenQuote], TokenUsage]:
        """
        使用LLM分析群聊金句
        保持原有接口，委托给专门的GoldenQuoteAnalyzer处理

        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符
            session_id: 会话ID (用于调试模式)

        Returns:
            (金句列表, Token使用统计)
        """
        try:
            if not session_id:
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if umo:
                    safe_umo = umo.replace(":", "_")
                    session_id = f"{timestamp}_{safe_umo}"
                else:
                    session_id = timestamp

            logger.info(f"开始金句分析, session_id: {session_id}")
            return await self.golden_quote_analyzer.analyze_golden_quotes(
                messages, umo, session_id
            )
        except Exception as e:
            logger.error(f"金句分析失败: {e}")
            return [], TokenUsage()

    async def analyze_all_concurrent(
        self,
        messages: list[dict],
        user_analysis: dict,
        umo: str = None,
        top_users: list[dict] = None,
        topic_enabled: bool = True,
        user_title_enabled: bool = True,
        golden_quote_enabled: bool = True,
    ) -> tuple[list[SummaryTopic], list[UserTitle], list[GoldenQuote], TokenUsage]:
        """
        并发执行所有分析任务（话题、用户称号、金句），支持按需启用。

        Args:
            messages: 群聊消息列表
            user_analysis: 用户分析统计
            umo: 模型唯一标识符
            top_users: 活跃用户列表(可选)
            topic_enabled: 是否启用话题分析
            user_title_enabled: 是否启用用户称号分析
            golden_quote_enabled: 是否启用金句分析

        Returns:
            (话题列表, 用户称号列表, 金句列表, 总Token使用统计)
        """
        try:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if umo:
                safe_umo = umo.replace(":", "_")
                session_id = f"{timestamp}_{safe_umo}"
            else:
                session_id = timestamp

            logger.info(
                f"开始并发执行分析任务 (话题:{topic_enabled}, 称号:{user_title_enabled}, 金句:{golden_quote_enabled})，会话ID: {session_id}"
            )

            # 保存原始消息数据 (Debug Mode)
            if self.config_manager.get_debug_mode():
                # ... (保持原有的调试保存代码)
                try:
                    import json
                    from pathlib import Path

                    from astrbot.core.utils.astrbot_path import (
                        get_astrbot_plugin_data_path,
                    )

                    plugin_name = "astrbot_plugin_qq_group_daily_analysis"
                    base_data_path = get_astrbot_plugin_data_path()
                    if isinstance(base_data_path, str):
                        base_data_path = Path(base_data_path)

                    debug_dir = base_data_path / plugin_name / "debug_data"
                    debug_dir.mkdir(parents=True, exist_ok=True)

                    msg_file_path = debug_dir / f"{session_id}_messages.json"
                    with open(msg_file_path, "w", encoding="utf-8") as f:
                        json.dump(messages, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            # 构建并发任务列表
            tasks = []
            task_names = []

            if topic_enabled:
                tasks.append(
                    self.topic_analyzer.analyze_topics(messages, umo, session_id)
                )
                task_names.append("topic")

            if user_title_enabled:
                tasks.append(
                    self.user_title_analyzer.analyze_user_titles(
                        messages, user_analysis, umo, top_users, session_id
                    )
                )
                task_names.append("user_title")

            if golden_quote_enabled:
                tasks.append(
                    self.golden_quote_analyzer.analyze_golden_quotes(
                        messages, umo, session_id
                    )
                )
                task_names.append("golden_quote")

            if not tasks:
                return [], [], [], TokenUsage()

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            topics, topic_usage = [], TokenUsage()
            user_titles, title_usage = [], TokenUsage()
            golden_quotes, quote_usage = [], TokenUsage()

            for i, result in enumerate(results):
                name = task_names[i]
                if isinstance(result, Exception):
                    logger.error(f"分析任务 {name} 失败: {result}")
                    continue

                if name == "topic":
                    topics, topic_usage = result
                elif name == "user_title":
                    user_titles, title_usage = result
                elif name == "golden_quote":
                    golden_quotes, quote_usage = result

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
        provider_id_key: str = None,
    ):
        """
        向后兼容的LLM调用方法
        现在委托给llm_utils模块处理

        Args:
            provider: LLM服务商实例或None（已弃用，现在使用 provider_id_key）
            prompt: 输入的提示语
            max_tokens: 最大生成token数
            temperature: 采样温度
            umo: 指定使用的模型唯一标识符
            provider_id_key: 配置中的 provider_id 键名（可选）

        Returns:
            LLM生成的结果
        """
        return await call_provider_with_retry(
            self.context,
            self.config_manager,
            prompt,
            max_tokens,
            temperature,
            umo,
            provider_id_key,
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
