"""
话题分析模块
专门处理群聊话题分析
"""

import re
from datetime import datetime

from ....domain.models.data_models import SummaryTopic, TokenUsage
from ....utils.logger import logger
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
        """获取最大话题数量，增量模式下使用覆盖值"""
        if self._incremental_max_count is not None:
            return self._incremental_max_count
        return self.config_manager.get_max_topics()

    def get_max_tokens(self) -> int:
        """获取最大token数"""
        return self.config_manager.get_topic_max_tokens()

    def get_temperature(self) -> float:
        """获取温度参数"""
        return 0.6

    def build_prompt(self, data: list[dict]) -> str:
        """
        构建话题分析提示词

        Args:
            messages: 群聊消息列表

        Returns:
            提示词字符串
        """
        # 验证输入数据格式
        if not isinstance(data, list):
            logger.error(f"build_prompt 期望列表，但收到: {type(data)}")
            return ""

        # 检查消息列表是否为空
        if not data:
            logger.warning("build_prompt 收到空消息列表")
            return ""

        # 提取文本消息
        text_messages = []
        for i, msg in enumerate(data):
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
                        at_id = at_data.get("id") or at_data.get("user_id")
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
                        {
                            "sender": nickname,
                            "time": msg_time,
                            "content": cleaned_text,
                            "user_id": str(user_id),
                        }
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
        # 使用用户提供的 ID-Only 格式: [HH:MM] [用户ID]: 消息内容
        messages_text = "\n".join(
            [
                f"[{msg['time']}] [{msg['user_id']}]: {msg['content']}"
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

    def extract_with_regex(self, result_text: str, max_count: int) -> list[dict]:
        """
        使用正则表达式提取话题信息

        Args:
            result_text: LLM响应文本
            max_count: 最大话题数量

        Returns:
            话题数据列表
        """
        return extract_topics_with_regex(result_text, max_count)

    def create_data_objects(self, data_list: list[dict]) -> list[SummaryTopic]:
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
            topics = []
            max_topics = self.get_max_count()

            logger.debug(f"处理前 {max_topics} 条话题数据")

            for i, topic_data in enumerate(data_list[:max_topics]):
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
        从已清理的消息中提取文本消息用于话题分析。

        Args:
            messages: 已由 MessageCleaner 处理过的 legacy 消息列表

        Returns:
            提取的文本消息列表
        """
        text_messages = []

        for msg in messages:
            # 获取发送者显示名
            sender = msg.get("sender", {})
            nickname = InfoUtils.get_user_nickname(self.config_manager, sender)
            msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")

            for content in msg.get("message", []):
                if content.get("type") == "text":
                    text = content.get("data", {}).get("text", "").strip()
                    # 已经在 MessageCleaner 中处理过基本的垃圾内容
                    if text:
                        # 简单的额外清理
                        cleaned_text = text.replace("\n", " ").replace("\r", " ")
                        cleaned_text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned_text)

                        text_messages.append(
                            {
                                "sender": nickname,
                                "time": msg_time,
                                "content": cleaned_text.strip(),
                                "user_id": str(sender.get("user_id", "")),
                            }
                        )
        return text_messages

    async def analyze_topics(
        self,
        messages: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
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

            # 建立 ID 到昵称的映射表
            id_to_nickname = {}
            for msg in text_messages:
                sender = msg.get("sender")
                user_id = msg.get("user_id")
                if sender and user_id:
                    id_to_nickname[user_id] = sender

            # 直接传入原始消息，让 build_prompt 方法处理
            topics, usage = await self.analyze(messages, umo, session_id)

            # 后处理：contributors 此时包含的是 ID，需要映射回昵称
            for topic in topics:
                raw_ids = topic.contributors  # LLM 返回的是 ID 列表

                # 填充 contributor_ids
                # 过滤掉非数字的脏数据 (LLM 偶尔会发疯)
                valid_ids = [
                    str(uid).strip() for uid in raw_ids if str(uid).strip().isdigit()
                ]
                topic.contributor_ids = valid_ids

                # 映射回昵称用于显示
                resolved_names = []
                for uid in valid_ids:
                    # 尝试从当前批次消息映射
                    name = id_to_nickname.get(uid)
                    if not name:
                        # 尝试去全局配置里找 (e.g. 机器人自己)
                        bot_ids = self.config_manager.get_bot_self_ids()
                        if uid in bot_ids:
                            name = "Bot"
                        else:
                            name = uid  # Fallback to ID
                    resolved_names.append(name)

                topic.contributors = resolved_names

            return topics, usage

        except Exception as e:
            logger.error(f"话题分析失败: {e}", exc_info=True)
            return [], TokenUsage()
