"""
金句分析模块
专门处理群聊金句提取和分析
"""

from datetime import datetime

from ...utils.logger import logger

from ...models.data_models import GoldenQuote, TokenUsage
from ..utils import InfoUtils
from ..utils.json_utils import extract_golden_quotes_with_regex
from .base_analyzer import BaseAnalyzer


class GoldenQuoteAnalyzer(BaseAnalyzer):
    """
    金句分析器
    专门处理群聊金句的提取和分析
    """

    def get_provider_id_key(self) -> str:
        """获取 Provider ID 配置键名"""
        return "golden_quote_provider_id"

    def get_data_type(self) -> str:
        """获取数据类型标识"""
        return "金句"

    def get_max_count(self) -> int:
        """获取最大金句数量"""
        return self.config_manager.get_max_golden_quotes()

    def get_max_tokens(self) -> int:
        """获取最大token数"""
        return self.config_manager.get_golden_quote_max_tokens()

    def get_temperature(self) -> float:
        """获取温度参数"""
        return 0.7

    def build_prompt(self, messages: list[dict]) -> str:
        """
        构建金句分析提示词

        Args:
            messages: 群聊的文本消息列表

        Returns:
            提示词字符串
        """
        if not messages:
            return ""

        # 构建消息文本
        messages_text = "\n".join(
            [f"[{msg['time']}] {msg['sender']}: {msg['content']}" for msg in messages]
        )

        max_golden_quotes = self.get_max_count()

        # 从配置读取 prompt 模板（默认使用 "default" 风格）
        prompt_template = self.config_manager.get_golden_quote_analysis_prompt()

        if prompt_template:
            # 使用配置中的 prompt 并替换变量
            try:
                prompt = prompt_template.format(
                    max_golden_quotes=max_golden_quotes, messages_text=messages_text
                )
                logger.info("使用配置中的金句分析提示词")
                return prompt
            except KeyError as e:
                logger.warning(f"金句分析提示词变量格式错误: {e}")
            except Exception as e:
                logger.warning(f"应用金句分析提示词失败: {e}")

        logger.warning("未找到有效的金句分析提示词配置，请检查配置文件")
        return ""

    def extract_with_regex(self, result_text: str, max_count: int) -> list[dict]:
        """
        使用正则表达式提取金句信息

        Args:
            result_text: LLM响应文本
            max_count: 最大提取数量

        Returns:
            金句数据列表
        """
        return extract_golden_quotes_with_regex(result_text, max_count)

    def create_data_objects(self, quotes_data: list[dict]) -> list[GoldenQuote]:
        """
        创建金句对象列表

        Args:
            quotes_data: 原始金句数据列表

        Returns:
            GoldenQuote对象列表
        """
        try:
            quotes = []
            max_quotes = self.get_max_count()

            for quote_data in quotes_data[:max_quotes]:
                # 确保数据格式正确
                content = quote_data.get("content", "").strip()
                sender = quote_data.get("sender", "").strip()
                reason = quote_data.get("reason", "").strip()

                # 验证必要字段
                if not content or not sender or not reason:
                    logger.warning(f"金句数据格式不完整，跳过: {quote_data}")
                    continue

                quotes.append(
                    GoldenQuote(content=content, sender=sender, reason=reason)
                )

            return quotes

        except Exception as e:
            logger.error(f"创建金句对象失败: {e}")
            return []

    async def analyze_golden_quotes(
        self, messages: list[dict], umo: str = None, session_id: str = None
    ) -> tuple[list[GoldenQuote], TokenUsage]:
        """
        分析群聊金句

        Args:
            messages: 群聊消息列表
            umo: 模型唯一标识符
            session_id: 会话ID (用于调试模式)

        Returns:
            (金句列表, Token使用统计)
        """
        try:
            # 提取圣经的文本消息
            interesting_messages = self.extract_interesting_messages(messages)

            if not interesting_messages:
                logger.info("没有符合条件的圣经消息，返回空结果")
                return [], TokenUsage()

            logger.info(f"开始从 {len(interesting_messages)} 条圣经消息中提取金句")
            quotes, usage = await self.analyze(interesting_messages, umo, session_id)

            # 回填 User ID
            for quote in quotes:
                for msg in interesting_messages:
                    # 尝试匹配内容和发送者
                    # 注意：LLM 可能会微调内容，这里使用包含匹配或精确匹配
                    if (
                        quote.content in msg["content"]
                        or msg["content"] in quote.content
                    ) and quote.sender == msg["sender"]:
                        quote.user_id = str(msg.get("user_id", ""))
                        break

            return quotes, usage

        except Exception as e:
            logger.error(f"金句分析失败: {e}")
            return [], TokenUsage()

    def extract_interesting_messages(self, messages: list[dict]) -> list[dict]:
        """
        提取圣经的文本消息

        Args:
            messages: 群聊消息列表

        Returns:
            圣经的文本消息列表
        """
        try:
            interesting_messages = []

            for msg in messages:
                sender = msg.get("sender", {})
                nickname = InfoUtils.get_user_nickname(self.config_manager, sender)
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")

                for content in msg.get("message", []):
                    if content.get("type") == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        # 过滤长度适中、可能圣经的消息
                        if 5 <= len(text) <= 100 and not text.startswith(
                            ("http", "www", "/")
                        ):
                            interesting_messages.append(
                                {
                                    "sender": nickname,
                                    "time": msg_time,
                                    "content": text,
                                    "user_id": str(sender.get("user_id", "")),
                                }
                            )

            return interesting_messages

        except Exception as e:
            logger.error(f"提取圣经消息失败: {e}")
            return []
