"""
LLM分析器模块
负责协调各个分析器进行话题分析、用户称号分析和金句分析
"""

import asyncio

from ...domain.models.data_models import (
    GoldenQuote,
    QualityReview,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)
from ...domain.repositories.analysis_repository import IAnalysisProvider
from ...shared.constants import PLUGIN_NAME
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from .analyzers.chat_quality_analyzer import ChatQualityAnalyzer
from .analyzers.comic_analyzer import ComicStoryboardAnalyzer
from .analyzers.golden_quote_analyzer import GoldenQuoteAnalyzer
from .analyzers.topic_analyzer import TopicAnalyzer
from .analyzers.user_title_analyzer import UserTitleAnalyzer
from .utils.json_utils import fix_json
from .utils.llm_utils import call_provider_with_retry


class LLMAnalyzer(IAnalysisProvider):
    """
    LLM分析器
    作为统一入口，协调各个专门的分析器进行不同类型的分析
    保持向后兼容性，提供原有的接口
    """

    topic_analyzer: TopicAnalyzer
    user_title_analyzer: UserTitleAnalyzer
    golden_quote_analyzer: GoldenQuoteAnalyzer
    comic_storyboard_analyzer: ComicStoryboardAnalyzer

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
        self.chat_quality_analyzer = ChatQualityAnalyzer(context, config_manager)
        self.comic_storyboard_analyzer = ComicStoryboardAnalyzer(
            context, config_manager
        )

    @staticmethod
    def _make_session_id(
        session_id: str | None, umo: str | None = None, prefix: str = ""
    ) -> str:
        """Generate a session ID if not already provided."""
        if session_id:
            return session_id
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if umo:
            safe_umo = umo.replace(":", "_")
            return f"{prefix}{timestamp}_{safe_umo}"
        return f"{prefix}{timestamp}"

    async def analyze_topics(
        self,
        messages: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
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
            session_id = self._make_session_id(session_id, umo)

            logger.info(f"开始话题分析, session_id: {session_id}")
            return await self.topic_analyzer.analyze_topics(messages, umo, session_id)
        except Exception as e:
            logger.error(f"话题分析失败: {e}")
            return [], TokenUsage()

    async def analyze_user_titles(
        self,
        messages: list[dict],
        user_activity: dict,
        umo: str | None = None,
        top_users: list[dict] | None = None,
        session_id: str | None = None,
    ) -> tuple[list[UserTitle], TokenUsage]:
        """
        使用LLM分析用户称号
        保持原有接口，委托给专门的UserTitleAnalyzer处理

        Args:
            messages: 群聊消息列表
            user_activity: 用户分析统计
            umo: 模型唯一标识符
            top_users: 活跃用户列表(可选)
            session_id: 会话ID (用于调试模式)

        Returns:
            (用户称号列表, Token使用统计)
        """
        try:
            session_id = self._make_session_id(session_id, umo)

            logger.info(f"开始用户称号分析, session_id: {session_id}")
            return await self.user_title_analyzer.analyze_user_titles(
                messages, user_activity, umo, top_users, session_id
            )
        except Exception as e:
            logger.error(f"用户称号分析失败: {e}")
            return [], TokenUsage()

    async def analyze_golden_quotes(
        self,
        messages: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
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
            session_id = self._make_session_id(session_id, umo)

            logger.info(f"开始金句分析, session_id: {session_id}")
            return await self.golden_quote_analyzer.analyze_golden_quotes(
                messages, umo, session_id
            )
        except Exception as e:
            logger.error(f"金句分析失败: {e}")
            return [], TokenUsage()

    async def analyze_comic_storyboards(
        self,
        topics: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
        persona_id: str | None = None,
        prompt_template: str | None = None,
    ) -> tuple[list[dict], TokenUsage]:
        """使用 LLM 分析并生成漫画分镜和绘画提示词。

        Args:
            topics: 已提取的有效群聊话题。
            umo: 群聊统一消息来源标识。
            session_id: 调试会话标识。
            persona_id: 漫画分镜专用人格 ID。
            prompt_template: 角色专属的漫画分镜提示词模板。

        Returns:
            分镜列表和 Token 使用统计。
        """
        try:
            session_id = self._make_session_id(session_id, umo)

            logger.info(f"开始漫画分镜分析, session_id: {session_id}")
            (
                storyboards,
                usage,
            ) = await self.comic_storyboard_analyzer.analyze_storyboards(
                topics, umo, session_id, persona_id, prompt_template
            )
            trace = TraceContext.current()
            if trace and usage and usage.total_tokens > 0:
                trace.add_token_usage(
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    analyzer_name="comic_storyboard",
                )
            return storyboards, usage
        except Exception as e:
            logger.error(f"漫画分镜分析失败: {e}", exc_info=True)
            return [], TokenUsage()

    async def summarize_quality_reviews(
        self,
        batch_reviews: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
    ) -> tuple[QualityReview | None, TokenUsage]:
        """
        汇总多个质量分析报告（增量模式使用）
        """
        return await self.chat_quality_analyzer.summarize_batch_reviews(
            batch_reviews, umo, session_id
        )

    async def analyze_all_concurrent(
        self,
        messages: list[dict],
        user_activity: dict,
        umo: str | None = None,
        top_users: list[dict] | None = None,
        topic_enabled: bool = True,
        user_title_enabled: bool = True,
        golden_quote_enabled: bool = True,
        chat_quality_enabled: bool = False,
    ) -> tuple[
        list[SummaryTopic],
        list[UserTitle],
        list[GoldenQuote],
        TokenUsage,
        QualityReview | None,
    ]:
        """
        并发执行所有分析任务（话题、用户称号、金句），支持按需启用。

        Args:
            messages: 群聊消息列表
            user_activity: 用户分析统计
            umo: 模型唯一标识符
            top_users: 活跃用户列表(可选)
            topic_enabled: 是否启用话题分析
            user_title_enabled: 是否启用用户称号分析
            golden_quote_enabled: 是否启用金句分析

        Returns:
            (话题列表, 用户称号列表, 金句列表, 总Token使用统计)
        """
        try:
            session_id = self._make_session_id(None, umo)

            logger.info(
                f"开始并发执行分析任务 (话题:{topic_enabled}, 称号:{user_title_enabled}, 金句:{golden_quote_enabled}, 质量:{chat_quality_enabled})，会话ID: {session_id}"
            )

            # 保存原始消息数据 (Debug Mode)
            if self.config_manager.get_debug_mode():
                self._save_debug_messages(messages, session_id)

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
                        messages, user_activity, umo, top_users, session_id
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

            if chat_quality_enabled:
                tasks.append(
                    self.chat_quality_analyzer.analyze_quality(
                        messages, umo, session_id
                    )
                )
                task_names.append("chat_quality")

            if not tasks:
                return [], [], [], TokenUsage(), None

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            topics, topic_usage = [], TokenUsage()
            user_titles, title_usage = [], TokenUsage()
            golden_quotes, quote_usage = [], TokenUsage()
            chat_quality_review = None
            quality_usage = TokenUsage()  # Initialize here
            subtask_errors: list[str] = []

            for i, result in enumerate(results):
                name = task_names[i]
                if isinstance(result, Exception):
                    logger.error(f"分析任务 {name} 失败: {result}")
                    subtask_errors.append(f"{name}: {str(result)}")
                    continue

                if name == "topic" and isinstance(result, tuple):
                    topics, topic_usage = result
                elif name == "user_title" and isinstance(result, tuple):
                    user_titles, title_usage = result
                elif name == "golden_quote" and isinstance(result, tuple):
                    golden_quotes, quote_usage = result
                elif name == "chat_quality" and isinstance(result, tuple):
                    chat_quality_review, quality_usage = result
                    if not isinstance(quality_usage, TokenUsage):
                        quality_usage = TokenUsage()

            # 合并Token使用统计
            total_usage = TokenUsage(
                prompt_tokens=topic_usage.prompt_tokens
                + title_usage.prompt_tokens
                + quote_usage.prompt_tokens
                + quality_usage.prompt_tokens,
                completion_tokens=topic_usage.completion_tokens
                + title_usage.completion_tokens
                + quote_usage.completion_tokens
                + quality_usage.completion_tokens,
                total_tokens=topic_usage.total_tokens
                + title_usage.total_tokens
                + quote_usage.total_tokens
                + quality_usage.total_tokens,
            )

            # 校验并补全未成功产出内容的子任务说明
            if (
                topic_enabled
                and not topics
                and not any(e.startswith("topic") for e in subtask_errors)
            ):
                subtask_errors.append(
                    "topic: 未能提取出有效话题（有效文本过少或模型未返回话题）"
                )
            if (
                user_title_enabled
                and not user_titles
                and not any(e.startswith("user_title") for e in subtask_errors)
            ):
                subtask_errors.append(
                    "user_title: 未能生成用户称号（活跃用户不足或模型未返回称号）"
                )
            if (
                golden_quote_enabled
                and not golden_quotes
                and not any(e.startswith("golden_quote") for e in subtask_errors)
            ):
                subtask_errors.append(
                    "golden_quote: 未能提取出精彩金句（符合条件的消息过少或模型未返回）"
                )
            if (
                chat_quality_enabled
                and not chat_quality_review
                and not any(e.startswith("chat_quality") for e in subtask_errors)
            ):
                subtask_errors.append(
                    "chat_quality: 未能生成质量锐评（模型未按预期格式输出）"
                )

            # 记录 Token 消耗与丰富执行详情到 TraceContext
            trace = TraceContext.current()
            if trace:
                if topic_usage.total_tokens > 0:
                    trace.add_token_usage(
                        topic_usage.prompt_tokens,
                        topic_usage.completion_tokens,
                        analyzer_name="topics",
                    )
                if title_usage.total_tokens > 0:
                    trace.add_token_usage(
                        title_usage.prompt_tokens,
                        title_usage.completion_tokens,
                        analyzer_name="user_titles",
                    )
                if quote_usage.total_tokens > 0:
                    trace.add_token_usage(
                        quote_usage.prompt_tokens,
                        quote_usage.completion_tokens,
                        analyzer_name="golden_quotes",
                    )
                if quality_usage.total_tokens > 0:
                    trace.add_token_usage(
                        quality_usage.prompt_tokens,
                        quality_usage.completion_tokens,
                        analyzer_name="chat_quality",
                    )
                # 丰富 LLM_ANALYSIS span payload 便于 WebUI 详情精准诊断
                for s in reversed(trace._spans):
                    if s.get("stage_name") == "LLM_ANALYSIS":
                        s.setdefault("payload", {}).update(
                            {
                                "topics_count": len(topics),
                                "topics": [t.topic for t in topics] if topics else [],
                                "user_titles_count": len(user_titles),
                                "golden_quotes_count": len(golden_quotes),
                                "chat_quality_review": bool(chat_quality_review),
                                "prompt_tokens": total_usage.prompt_tokens,
                                "completion_tokens": total_usage.completion_tokens,
                                "total_tokens": total_usage.total_tokens,
                                "enabled_features": {
                                    "topics": topic_enabled,
                                    "user_titles": user_title_enabled,
                                    "golden_quotes": golden_quote_enabled,
                                    "chat_quality": chat_quality_enabled,
                                },
                                "prompts": trace.metadata.get("llm_prompts", {}),
                            }
                        )
                        if subtask_errors:
                            s["payload"]["subtask_errors"] = subtask_errors
                        break

            logger.info(
                f"并发分析完成 - 话题: {len(topics)}, 称号: {len(user_titles)}, 金句: {len(golden_quotes)}, 质量锐评: {1 if chat_quality_review else 0}"
            )
            return (
                topics,
                user_titles,
                golden_quotes,
                total_usage,
                chat_quality_review,
            )

        except Exception as e:
            logger.error(f"并发分析失败: {e}")
            trace = TraceContext.current()
            if trace:
                for s in reversed(trace._spans):
                    if s.get("stage_name") == "LLM_ANALYSIS":
                        s.setdefault("payload", {}).update(
                            {
                                "error": str(e),
                                "subtask_errors": [f"全局并发分析异常: {e}"],
                            }
                        )
                        break
            return [], [], [], TokenUsage(), None

    async def analyze_incremental_concurrent(
        self,
        messages: list[dict],
        umo: str | None = None,
        topics_per_batch: int = 2,
        quotes_per_batch: int = 1,
        topic_enabled: bool = True,
        golden_quote_enabled: bool = True,
        chat_quality_enabled: bool = False,
    ) -> tuple[list[SummaryTopic], list[GoldenQuote], TokenUsage, QualityReview | None]:
        """
        增量分析模式的并发执行方法。
        仅执行话题分析和金句分析（用户称号分析在最终报告时执行），
        使用较小的批次数量以控制单次分析的输出规模。

        Args:
            messages: 本次增量分析的群聊消息列表
            umo: 模型唯一标识符
            topics_per_batch: 本次批次最大话题数量
            quotes_per_batch: 本次批次最大金句数量
            topic_enabled: 是否启用话题分析
            golden_quote_enabled: 是否启用金句分析

        Returns:
            (话题列表, 金句列表, 总Token使用统计)
        """
        try:
            session_id = self._make_session_id(None, umo, "incr_")

            logger.info(
                f"开始增量并发分析 (话题:{topic_enabled}/{topics_per_batch}, 金句:{golden_quote_enabled}/{quotes_per_batch}, 质量锐评:{chat_quality_enabled})，"
                f"消息数量: {len(messages)}，会话ID: {session_id}"
            )

            # 保存原始消息数据 (Debug Mode)
            if self.config_manager.get_debug_mode():
                self._save_debug_messages(messages, session_id)

            # 设置增量模式的最大数量覆盖值
            self.topic_analyzer._incremental_max_count = topics_per_batch
            self.golden_quote_analyzer._incremental_max_count = quotes_per_batch

            try:
                # 构建并发任务列表（仅话题和金句，不包含用户称号）
                tasks = []
                task_names = []

                if topic_enabled:
                    tasks.append(
                        self.topic_analyzer.analyze_topics(messages, umo, session_id)
                    )
                    task_names.append("topic")

                if golden_quote_enabled:
                    tasks.append(
                        self.golden_quote_analyzer.analyze_golden_quotes(
                            messages, umo, session_id
                        )
                    )
                    task_names.append("golden_quote")

                if chat_quality_enabled:
                    tasks.append(
                        self.chat_quality_analyzer.analyze_quality(
                            messages, umo, session_id
                        )
                    )
                    task_names.append("chat_quality")

                if not tasks:
                    return [], [], TokenUsage(), None

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 处理结果
                topics, topic_usage = [], TokenUsage()
                golden_quotes, quote_usage = [], TokenUsage()
                chat_quality_review = None
                quality_usage = TokenUsage()
                subtask_errors: list[str] = []

                for i, result in enumerate(results):
                    name = task_names[i]
                    if isinstance(result, Exception):
                        logger.error(f"增量{name}分析失败: {result}")
                        subtask_errors.append(f"{name}: {str(result)}")
                        continue

                    if name == "topic" and isinstance(result, tuple):
                        topics, topic_usage = result
                    elif name == "golden_quote" and isinstance(result, tuple):
                        golden_quotes, quote_usage = result
                    elif name == "chat_quality" and isinstance(result, tuple):
                        chat_quality_review, quality_usage = result
                        if not isinstance(quality_usage, TokenUsage):
                            quality_usage = TokenUsage()

                # 校验并补全增量子任务未产出说明
                if (
                    topic_enabled
                    and not topics
                    and not any(e.startswith("topic") for e in subtask_errors)
                ):
                    subtask_errors.append(
                        "topic: 未能提取出增量话题（可能有效文本过少或模型未返回）"
                    )
                if (
                    golden_quote_enabled
                    and not golden_quotes
                    and not any(e.startswith("golden_quote") for e in subtask_errors)
                ):
                    subtask_errors.append(
                        "golden_quote: 未能提取出增量金句（可能符合条件的消息过少或模型未返回）"
                    )
                if (
                    chat_quality_enabled
                    and not chat_quality_review
                    and not any(e.startswith("chat_quality") for e in subtask_errors)
                ):
                    subtask_errors.append(
                        "chat_quality: 未能生成增量质量锐评（模型未按预期格式输出）"
                    )

                # 合并Token使用统计
                total_usage = TokenUsage(
                    prompt_tokens=topic_usage.prompt_tokens
                    + quote_usage.prompt_tokens
                    + quality_usage.prompt_tokens,
                    completion_tokens=topic_usage.completion_tokens
                    + quote_usage.completion_tokens
                    + quality_usage.completion_tokens,
                    total_tokens=topic_usage.total_tokens
                    + quote_usage.total_tokens
                    + quality_usage.total_tokens,
                )

                # 记录 Token 消耗到 TraceContext
                trace = TraceContext.current()
                if trace:
                    if topic_usage.total_tokens > 0:
                        trace.add_token_usage(
                            topic_usage.prompt_tokens,
                            topic_usage.completion_tokens,
                            analyzer_name="topics",
                        )
                    if quote_usage.total_tokens > 0:
                        trace.add_token_usage(
                            quote_usage.prompt_tokens,
                            quote_usage.completion_tokens,
                            analyzer_name="golden_quotes",
                        )
                    if quality_usage.total_tokens > 0:
                        trace.add_token_usage(
                            quality_usage.prompt_tokens,
                            quality_usage.completion_tokens,
                            analyzer_name="chat_quality",
                        )
                    for s in reversed(trace._spans):
                        if s.get("stage_name") == "LLM_ANALYSIS":
                            s.setdefault("payload", {}).update(
                                {
                                    "incremental": True,
                                    "topics_count": len(topics),
                                    "topics": [t.topic for t in topics]
                                    if topics
                                    else [],
                                    "golden_quotes_count": len(golden_quotes),
                                    "chat_quality_review": bool(chat_quality_review),
                                    "prompt_tokens": total_usage.prompt_tokens,
                                    "completion_tokens": total_usage.completion_tokens,
                                    "total_tokens": total_usage.total_tokens,
                                    "enabled_features": {
                                        "topics": topic_enabled,
                                        "user_titles": False,
                                        "golden_quotes": golden_quote_enabled,
                                        "chat_quality": chat_quality_enabled,
                                    },
                                }
                            )
                            if subtask_errors:
                                s["payload"]["subtask_errors"] = subtask_errors
                            break

                logger.info(
                    f"增量并发分析完成 - 话题: {len(topics)}, 金句: {len(golden_quotes)}, 质量锐评: {1 if chat_quality_review else 0}, "
                    f"Token消耗: {total_usage.total_tokens}"
                )
                return topics, golden_quotes, total_usage, chat_quality_review

            finally:
                # 无论成功或失败，都要恢复原始的最大数量设置
                self.topic_analyzer._incremental_max_count = None
                self.golden_quote_analyzer._incremental_max_count = None

        except Exception as e:
            logger.error(f"增量并发分析失败: {e}", exc_info=True)
            trace = TraceContext.current()
            if trace:
                for s in reversed(trace._spans):
                    if s.get("stage_name") == "LLM_ANALYSIS":
                        s.setdefault("payload", {}).update(
                            {
                                "error": str(e),
                                "subtask_errors": [f"全局增量并发分析异常: {e}"],
                            }
                        )
                        break
            return [], [], TokenUsage(), None

    def _save_debug_messages(self, messages: list[dict], session_id: str):
        """
        保存调试消息数据到文件（Debug Mode 专用）

        Args:
            messages: 群聊消息列表
            session_id: 会话ID
        """
        try:
            import json

            from astrbot.api.star import StarTools

            debug_dir = StarTools.get_data_dir(PLUGIN_NAME) / "debug_data"
            debug_dir.mkdir(parents=True, exist_ok=True)

            msg_file_path = debug_dir / f"{session_id}_messages.json"
            with open(msg_file_path, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # 向后兼容的方法，保持原有调用方式
    async def _call_provider_with_retry(
        self,
        provider,
        prompt: str,
        umo: str | None = None,
        provider_id_key: str | None = None,
    ):
        """
        向后兼容的LLM调用方法
        现在委托给llm_utils模块处理

        Args:
            provider: LLM服务商实例或None（已弃用，现在使用 provider_id_key）
            prompt: 输入的提示语
            umo: 指定使用的模型唯一标识符
            provider_id_key: 配置中的 provider_id 键名（可选）

        Returns:
            LLM生成的结果
        """
        return await call_provider_with_retry(
            self.context,
            self.config_manager,
            prompt,
            umo,
            provider_id_key,
            observation_label=provider_id_key or "兼容LLM调用入口",
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

    async def analyze_retry_prompt(
        self, original_prompt: str, last_error: str, umo: str | None
    ) -> str | None:
        """
        当画图 API 遇到多次失败后，将错误信息交给 LLM 进行分析和改写。
        如果 LLM 认为原 Prompt 严重违规且无法修改，将返回 None；
        否则返回脱敏/重写后的新 Prompt，进行最后一次尝试。
        """
        prompt = f"""
你是一个专业且注重安全合规的内容改写员。
有一段画图提示词在提交给画图模型时被拒绝或遇到了异常，原因可能包含敏感内容审查、尺寸格式报错或连接异常。

【原画图提示词】:
{original_prompt}

【画图模型返回的最后一次异常信息】:
{last_error}

请你根据异常信息，对原画图提示词进行诊断和修改：
1. 如果报错是因为“色情、暴力、血腥、政治”等严重违规审查，且你认为原内容**绝对无法**被修改为健康场景（例如要求本身就是极端不合法的），请直接返回 {{"can_fix": false, "new_prompt": ""}}
2. 如果是因为审查问题，但你可以通过**去掉敏感词**、**把场景转换为正能量/健康搞笑/委婉抽象**的画面描述来避开审查，请进行脱敏重写。
3. 如果只是普通的超时或未知错误，你可以尝试简化画面中的复杂要素，让场景更简洁。

请严格以 JSON 格式输出，不要包含任何 markdown 代码块（如 ```json 等），只输出 JSON 字符串：
{{
  "can_fix": true,
  "new_prompt": "修改后且保证健康合规的全新英文或中文画图提示词"
}}
"""
        try:
            llm_response = await call_provider_with_retry(
                context=self.context,
                config_manager=self.config_manager,
                prompt=prompt,
                umo=umo,
                provider_id_key="drawing_prompt_provider_id",
                observation_label="绘图提示词修复",
            )
            if not llm_response or not llm_response.completion_text:
                return None

            response_text = llm_response.completion_text.strip()
            if response_text.startswith("```"):
                import re

                response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
                response_text = re.sub(r"\s*```$", "", response_text)

            import json

            try:
                data = json.loads(response_text)
            except json.JSONDecodeError:
                # 尝试通过正则寻找大括号内的内容
                import re

                match = re.search(r"(\{.*\})", response_text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                else:
                    raise

            if data.get("can_fix") and data.get("new_prompt"):
                new_prompt = data["new_prompt"].strip()
                if new_prompt:
                    logger.info("[Comic] LLM 成功分析异常并给出了重写的安全提示词。")
                    return new_prompt

            logger.info("[Comic] LLM 判断该异常无法通过重写修复，或未提供新提示词。")
            return None
        except Exception as e:
            logger.error(f"[Comic] 请求 LLM 重写提示词时发生错误: {e}")
            return None
