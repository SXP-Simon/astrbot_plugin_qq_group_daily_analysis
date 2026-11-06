"""
话题分析模块
专门处理群聊话题分析
"""

from __future__ import annotations

from ....domain.value_objects import SummaryTopic, TokenUsage
from ....domain.value_objects.unified_message import (
    AnalysisTextMessage,
    UnifiedMessage,
)
from ....shared.type_guards import is_object_list
from ....utils.logger import logger
from ....utils.template_utils import render_template
from ..utils.analysis_messages import extract_analysis_messages
from ..utils.json_utils import extract_topics_with_regex
from ..utils.response_validation import validate_topic_items
from ..utils.structured_output_schema import JSONObject, build_topics_schema
from .base_analyzer import BaseAnalyzer


class TopicAnalyzer(BaseAnalyzer[SummaryTopic, list[AnalysisTextMessage]]):
    """
    话题分析器
    专门处理群聊话题的提取和分析
    """

    def get_provider_id_key(self) -> str:
        """获取 Provider ID 配置键名"""
        return "topic_provider_id"

    def get_data_type(self) -> str:
        """获取数据类型标识"""
        return "话题"

    def get_max_count(self) -> int:
        """获取最大话题数量，增量模式下使用覆盖值"""
        if self.incremental_max_count is not None:
            return self.incremental_max_count
        return self.config_manager.get_max_topics()

    def get_response_schema_name(self) -> str:
        return "daily_topics"

    def get_response_schema(self) -> JSONObject:
        return build_topics_schema(self.get_max_count())

    def build_prompt(self, data: list[AnalysisTextMessage]) -> str:
        """
        构建话题分析提示词

        Args:
            data: 已提取的模型输入消息。

        Returns:
            提示词字符串
        """
        # 检查消息列表是否为空
        if not data:
            logger.warning("build_prompt 收到空消息列表")
            return ""

        # 构建消息文本
        # 使用用户提供的 ID-Only 格式: [HH:MM] [用户ID]: 消息内容
        messages_text = "\n".join(
            [f"[{msg['time']}] [{msg['user_id']}]: {msg['content']}" for msg in data]
        )

        max_topics = self.get_max_count()

        # 从配置读取 prompt 模板（默认使用 "default" 风格）
        prompt_template = self.config_manager.get_topic_analysis_prompt()

        if prompt_template:
            try:
                prompt = render_template(
                    prompt_template,
                    max_topics=max_topics,
                    messages_text=messages_text,
                )
                logger.debug("使用配置中的话题分析提示词")
                return prompt
            except Exception as e:
                logger.warning(f"应用话题分析提示词失败: {e}")

        logger.warning("未找到有效的话题分析提示词配置，请检查配置文件")
        return ""

    def extract_with_regex(
        self, result_text: str, max_count: int
    ) -> list[dict[str, object]]:
        """
        使用正则表达式提取话题信息

        Args:
            result_text: LLM响应文本
            max_count: 最大话题数量

        Returns:
            话题数据列表
        """
        return extract_topics_with_regex(result_text, max_count)

    def create_data_objects(
        self, data_list: list[dict[str, object]]
    ) -> list[SummaryTopic]:
        """
        创建话题对象列表

        Args:
            topics_data: 原始话题数据列表

        Returns:
            SummaryTopic对象列表
        """
        logger.debug(
            f"create_data_objects 开始处理，输入数据数量: {len(data_list) if data_list else 0}"
        )
        logger.debug(f"输入数据类型: {type(data_list)}")

        try:
            topics: list[SummaryTopic] = []
            max_topics = self.get_max_count()

            logger.debug(f"处理前 {max_topics} 条话题数据")

            for i, topic_data in enumerate(data_list[:max_topics]):
                logger.debug(f"处理第 {i + 1} 条话题数据，类型: {type(topic_data)}")

                try:
                    # 确保数据格式正确
                    topic_name = str(topic_data.get("topic", "") or "").strip()
                    contributors = topic_data.get("contributors", [])
                    detail = str(topic_data.get("detail", "") or "").strip()

                    logger.debug(
                        f"话题数据 - 名称: {topic_name}, 参与者: {contributors}, 详情: {detail[:50]}..."
                    )

                    # 验证必要字段
                    if not topic_name or not detail:
                        logger.warning(f"话题数据格式不完整，跳过: {topic_data}")
                        continue

                    # 确保参与者列表有效
                    if not contributors or not is_object_list(contributors):
                        contributors = ["群友"]
                    else:
                        # 清理参与者名称
                        contributors = [
                            str(c).strip() for c in contributors if c and str(c).strip()
                        ] or ["群友"]

                    topics.append(
                        SummaryTopic(
                            topic=topic_name,
                            contributors=contributors[:5],  # 最多5个参与者
                            detail=detail,
                        )
                    )
                except Exception as e:
                    logger.error(f"处理第 {i + 1} 条话题数据时出错: {e}", exc_info=True)
                    continue

            logger.debug(f"create_data_objects 完成，创建了 {len(topics)} 个话题对象")
            return topics

        except Exception as e:
            logger.error(f"创建话题对象失败: {e}", exc_info=True)
            return []

    def validate_parsed_data(
        self, data_list: list[dict[str, object]]
    ) -> tuple[bool, list[dict[str, object]] | None, str | None]:
        return validate_topic_items(data_list)

    def extract_text_messages(
        self, messages: list[UnifiedMessage]
    ) -> list[AnalysisTextMessage]:
        """
        从已清理的消息中提取文本消息用于话题分析。

        Args:
            messages: 已由 MessageCleaner 处理过的统一消息列表

        Returns:
            提取的文本消息列表
        """
        text_messages = extract_analysis_messages(
            messages,
            use_card=self.config_manager.get_enable_user_card(),
            bot_self_ids=self.config_manager.get_bot_self_ids(),
        )
        for message in text_messages:
            message["content"] = (
                message["content"]
                .replace("“", '"')
                .replace("”", '"')
                .replace("‘", "'")
                .replace("’", "'")
            )
        return [message for message in text_messages if len(message["content"]) > 2]

    async def analyze_topics(
        self,
        messages: list[UnifiedMessage],
        umo: str | None = None,
    ) -> tuple[list[SummaryTopic], TokenUsage]:
        """分析群聊话题

        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符

        Returns:
            (话题列表, Token使用统计)
        """
        try:
            logger.debug(
                f"analyze_topics 开始处理，消息数量: {len(messages) if messages else 0}"
            )
            logger.debug(f"消息类型: {type(messages)}")
            if messages:
                logger.debug(
                    f"第一条消息类型: {type(messages[0]) if messages else '无'}"
                )
                logger.debug(f"第一条消息内容: {messages[0] if messages else '无'}")

            # 检查是否有有效的文本消息
            text_messages = self.extract_text_messages(messages)
            logger.debug(f"提取到 {len(text_messages)} 条文本消息")

            if not text_messages:
                logger.debug("没有有效的文本消息，返回空结果")
                return [], TokenUsage()

            logger.debug(f"开始分析 {len(text_messages)} 条文本消息中的话题")
            logger.debug(f"文本消息类型: {type(text_messages)}")
            if text_messages:
                logger.debug(f"第一条文本消息类型: {type(text_messages[0])}")
                logger.debug(f"第一条文本消息内容: {text_messages[0]}")

            # 建立 ID 到昵称的映射表
            id_to_nickname: dict[str, str] = {}
            for msg in text_messages:
                sender = msg.get("sender")
                user_id = msg.get("user_id")
                if sender and user_id:
                    id_to_nickname[user_id] = sender

            # 提取一次，同时用于提示词构建和参与者身份回填。
            topics, usage = await self.analyze(text_messages, umo)

            # 后处理：contributors 此时包含的是 ID，需要映射回昵称
            for topic in topics:
                raw_ids = topic.contributors  # LLM 返回的是 ID 列表

                # 填充 contributor_ids。QQ 官方 member_openid 并非纯数字，
                # 因此仅接受本批次已知用户或已配置机器人 ID，而不是用 isdigit 过滤。
                bot_ids = {str(uid) for uid in self.config_manager.get_bot_self_ids()}
                known_ids = set(id_to_nickname) | bot_ids
                valid_ids: list[str] = []
                for raw_uid in raw_ids:
                    uid = str(raw_uid).strip().strip("[]")
                    if uid and uid in known_ids and uid not in valid_ids:
                        valid_ids.append(uid)
                topic.contributor_ids = valid_ids

                # 映射回昵称用于显示
                resolved_names: list[str] = []
                for uid in valid_ids:
                    # 尝试从当前批次消息映射
                    name = id_to_nickname.get(uid)
                    if not name:
                        # Fallback for bot self IDs or unknown IDs
                        name = "Bot" if uid in bot_ids else uid
                    resolved_names.append(name)

                topic.contributors = resolved_names

            return topics, usage

        except Exception as e:
            logger.error(f"话题分析失败: {e}", exc_info=True)
            raise
