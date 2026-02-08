"""
话题分析模块
专门处理群聊话题分析
"""

import re
from datetime import datetime

from ...utils.logger import logger

from ...models.data_models import SummaryTopic, TokenUsage
from ..utils import InfoUtils
from ..utils.json_utils import extract_topics_with_regex
from .base_analyzer import BaseAnalyzer


class TopicAnalyzer(BaseAnalyzer):
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
        """获取最大话题数量"""
        return self.config_manager.get_max_topics()

    def get_max_tokens(self) -> int:
        """获取最大token数"""
        return self.config_manager.get_topic_max_tokens()

    def get_temperature(self) -> float:
        """获取温度参数"""
        return 0.6

    def build_prompt(self, messages: list[dict]) -> str:
        """
        构建话题分析提示词

        Args:
            messages: 群聊消息列表

        Returns:
            提示词字符串
        """
        # 验证输入数据格式
        if not isinstance(messages, list):
            logger.error(f"build_prompt 期望列表，但收到: {type(messages)}")
            return ""

        # 检查消息列表是否为空
        if not messages:
            logger.warning("build_prompt 收到空消息列表")
            return ""

        # 提取文本消息
        text_messages = []
        for i, msg in enumerate(messages):
            # 确保msg是字典类型，避免'str' object has no attribute 'get'错误
            if not isinstance(msg, dict):
                continue

            try:
                sender = msg.get("sender", {})
                # 确保sender是字典类型，避免'str' object has no attribute 'get'错误
                if not isinstance(sender, dict):
                    continue

                # 获取发送者ID并过滤机器人消息
                user_id = str(sender.get("user_id", ""))
                bot_self_ids = self.config_manager.get_bot_self_ids()

                # 跳过机器人自己的消息
                if bot_self_ids and user_id in [str(uid) for uid in bot_self_ids]:
                    continue

                nickname = InfoUtils.get_user_nickname(self.config_manager, sender)
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")

                message_list = msg.get("message", [])

                # 提取文本内容，可能分布在多个 content 中
                text_parts = []
                for j, content in enumerate(message_list):
                    if not isinstance(content, dict):
                        continue

                    content_type = content.get("type", "")

                    if content_type == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        if text:
                            text_parts.append(text)
                    elif content_type == "at":
                        # 处理 @ 消息，转换为文本
                        at_data = content.get("data", {})
                        # 兼容不同平台的 ID 字段
                        at_id = (
                            at_data.get("qq")
                            or at_data.get("id")
                            or at_data.get("user_id")
                        )
                        if at_id:
                            at_text = f"@{at_id}"
                            text_parts.append(at_text)
                    elif content_type == "reply":
                        # 处理回复消息，添加标记
                        reply_id = content.get("data", {}).get("id", "")
                        if reply_id:
                            reply_text = f"[回复:{reply_id}]"
                            text_parts.append(reply_text)

                # 合并所有文本部分
                combined_text = "".join(text_parts).strip()

                if (
                    combined_text
                    and len(combined_text) > 2
                    and not combined_text.startswith("/")
                ):
                    # 清理消息内容
                    cleaned_text = combined_text.replace("“", '"').replace("”", '"')
                    cleaned_text = cleaned_text.replace("‘", "'").replace("’", "'")
                    cleaned_text = cleaned_text.replace("\n", " ").replace("\r", " ")
                    cleaned_text = cleaned_text.replace("\t", " ")
                    cleaned_text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned_text)

                    text_messages.append(
                        {"sender": nickname, "time": msg_time, "content": cleaned_text}
                    )
            except Exception as e:
                logger.error(
                    f"build_prompt 处理第 {i + 1} 条消息时出错: {e}", exc_info=True
                )
                continue

        if not text_messages:
            logger.warning("build_prompt 没有提取到有效的文本消息，返回空prompt")
            return ""

        # 构建消息文本
        messages_text = "\n".join(
            [
                f"[{msg['time']}] {msg['sender']}: {msg['content']}"
                for msg in text_messages
            ]
        )

        max_topics = self.get_max_count()

        # 从配置读取 prompt 模板（默认使用 "default" 风格）
        prompt_template = self.config_manager.get_topic_analysis_prompt()

        if prompt_template:
            # 使用配置中的 prompt 并替换变量
            try:
                prompt = prompt_template.format(
                    max_topics=max_topics, messages_text=messages_text
                )
                logger.info("使用配置中的话题分析提示词")
                return prompt
            except KeyError as e:
                logger.warning(f"话题分析提示词变量格式错误: {e}")
            except Exception as e:
                logger.warning(f"应用话题分析提示词失败: {e}")

        logger.warning("未找到有效的话题分析提示词配置，请检查配置文件")
        return ""

    def extract_with_regex(self, result_text: str, max_topics: int) -> list[dict]:
        """
        使用正则表达式提取话题信息

        Args:
            result_text: LLM响应文本
            max_topics: 最大话题数量

        Returns:
            话题数据列表
        """
        return extract_topics_with_regex(result_text, max_topics)

    def create_data_objects(self, topics_data: list[dict]) -> list[SummaryTopic]:
        """
        创建话题对象列表

        Args:
            topics_data: 原始话题数据列表

        Returns:
            SummaryTopic对象列表
        """
        logger.debug(
            f"create_data_objects 开始处理，输入数据数量: {len(topics_data) if topics_data else 0}"
        )
        logger.debug(f"输入数据类型: {type(topics_data)}")

        try:
            topics = []
            max_topics = self.get_max_count()

            logger.debug(f"处理前 {max_topics} 条话题数据")

            for i, topic_data in enumerate(topics_data[:max_topics]):
                logger.debug(f"处理第 {i + 1} 条话题数据，类型: {type(topic_data)}")

                # 确保topic_data是字典类型，避免'str' object has no attribute 'get'错误
                if not isinstance(topic_data, dict):
                    logger.warning(
                        f"跳过非字典类型的话题数据: {type(topic_data)} - {topic_data}"
                    )
                    continue

                try:
                    # 确保数据格式正确
                    topic_name = topic_data.get("topic", "").strip()
                    contributors = topic_data.get("contributors", [])
                    detail = topic_data.get("detail", "").strip()

                    logger.debug(
                        f"话题数据 - 名称: {topic_name}, 参与者: {contributors}, 详情: {detail[:50]}..."
                    )

                    # 验证必要字段
                    if not topic_name or not detail:
                        logger.warning(f"话题数据格式不完整，跳过: {topic_data}")
                        continue

                    # 确保参与者列表有效
                    if not contributors or not isinstance(contributors, list):
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

    def extract_text_messages(self, messages: list[dict]) -> list[dict]:
        """
        从群聊消息中提取文本消息

        Args:
            messages: 群聊消息列表

        Returns:
            提取的文本消息列表
        """
        logger.debug(
            f"extract_text_messages 开始处理，输入消息数量: {len(messages) if messages else 0}"
        )
        logger.debug(f"extract_text_messages 输入消息类型: {type(messages)}")

        if not messages:
            logger.warning("extract_text_messages 收到空消息列表")
            return []

        text_messages = []

        for i, msg in enumerate(messages):
            logger.debug(f"处理第 {i + 1} 条消息，类型: {type(msg)}")
            # 确保msg是字典类型，避免'str' object has no attribute 'get'错误
            if not isinstance(msg, dict):
                logger.warning(f"跳过非字典类型的消息: {type(msg)} - {msg}")
                continue

            try:
                sender = msg.get("sender", {})
                # 确保sender是字典类型，避免'str' object has no attribute 'get'错误
                if not isinstance(sender, dict):
                    logger.warning(
                        f"extract_text_messages 跳过sender非字典类型的消息: {type(sender)} - {sender}"
                    )
                    continue

                # 获取发送者ID并过滤机器人消息
                user_id = str(sender.get("user_id", ""))
                bot_self_ids = self.config_manager.get_bot_self_ids()

                # 跳过机器人自己的消息
                if bot_self_ids and user_id in [str(uid) for uid in bot_self_ids]:
                    logger.debug(f"extract_text_messages 过滤掉机器人QQ号: {user_id}")
                    continue

                nickname = InfoUtils.get_user_nickname(self.config_manager, sender)
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")

                for content in msg.get("message", []):
                    if content.get("type") == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        if text and len(text) > 2 and not text.startswith("/"):
                            # 清理消息内容
                            text = text.replace('""', '"').replace('""', '"')
                            text = text.replace(""", "'").replace(""", "'")
                            text = text.replace("\n", " ").replace("\r", " ")
                            text = text.replace("\t", " ")
                            text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
                            text_messages.append(
                                {
                                    "sender": nickname,
                                    "time": msg_time,
                                    "content": text.strip(),
                                }
                            )
            except Exception as e:
                logger.error(f"处理第 {i + 1} 条消息时出错: {e}", exc_info=True)
                continue

        logger.debug(
            f"extract_text_messages 完成，提取到 {len(text_messages)} 条文本消息"
        )
        if text_messages:
            logger.debug(f"extract_text_messages 第一条文本消息: {text_messages[0]}")
        return text_messages

    async def analyze_topics(
        self, messages: list[dict], umo: str = None, session_id: str = None
    ) -> tuple[list[SummaryTopic], TokenUsage]:
        """
        分析群聊话题

        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符
            session_id: 会话ID (用于调试模式)

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
                logger.info("没有有效的文本消息，返回空结果")
                return [], TokenUsage()

            logger.info(f"开始分析 {len(text_messages)} 条文本消息中的话题")
            logger.debug(f"文本消息类型: {type(text_messages)}")
            if text_messages:
                logger.debug(f"第一条文本消息类型: {type(text_messages[0])}")
                logger.debug(f"第一条文本消息内容: {text_messages[0]}")

            # 直接传入原始消息，让 build_prompt 方法处理
            return await self.analyze(messages, umo, session_id)

        except Exception as e:
            logger.error(f"话题分析失败: {e}", exc_info=True)
            return [], TokenUsage()
