"""
聊天质量分析模块
专门处理群聊质量锐评分析
"""

from datetime import datetime

from ....domain.models.data_models import QualityDimension, QualityReview, TokenUsage
from ....utils.logger import logger
from ..utils import InfoUtils
from ..utils.json_utils import extract_quality_with_regex, parse_json_object_response
from ..utils.llm_utils import (
    call_provider_with_retry,
    extract_response_text,
    extract_token_usage,
)
from .base_analyzer import BaseAnalyzer


class ChatQualityAnalyzer(BaseAnalyzer):
    """
    聊天质量分析器
    专门处理群聊质量的锐评和多维度分析

    注意：由于聊天质量分析返回的是 JSON 对象而非数组，
    此分析器重写了 analyze() 方法，使用 parse_json_object_response 解析，
    并以 extract_quality_with_regex 作为正则降级方案。
    """

    def get_provider_id_key(self) -> str:
        """获取 Provider ID 配置键名"""
        return "quality_provider_id"

    def get_data_type(self) -> str:
        """获取数据类型标识"""
        return "聊天质量"

    def get_max_count(self) -> int:
        """获取最大维度数量"""
        return 8

    def get_max_tokens(self) -> int:
        """获取最大token数"""
        return self.config_manager.get_quality_max_tokens()

    def get_temperature(self) -> float:
        """获取温度参数"""
        return 0.8

    def build_prompt(self, data: list[dict]) -> str:
        """
        构建聊天质量分析提示词
        """
        if not data:
            return ""

        # 提取文本消息
        text_messages = []
        for msg in data:
            if not isinstance(msg, dict):
                continue

            sender = msg.get("sender", {})
            user_id = str(sender.get("user_id", ""))
            bot_self_ids = self.config_manager.get_bot_self_ids()
            if bot_self_ids and user_id in [str(uid) for uid in bot_self_ids]:
                continue

            nickname = InfoUtils.get_user_nickname(self.config_manager, sender)
            msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")
            message_list = msg.get("message", [])

            text_parts = []
            for content in message_list:
                if content.get("type") == "text":
                    text = content.get("data", {}).get("text", "").strip()
                    if text:
                        text_parts.append(text)

            combined_text = "".join(text_parts).strip()
            if combined_text and not combined_text.startswith("/"):
                text_messages.append(f"[{msg_time}] [{nickname}]: {combined_text}")

        messages_text = "\n".join(text_messages[:1000])

        prompt_template = self.config_manager.get_quality_analysis_prompt()

        if not prompt_template:
            prompt_template = """你是一个毒舌且幽默的群聊质量分析师。
请分析以下群聊记录，输出一份"聊天质量锐评"。

## 任务目标：
1. 将聊天内容划分为 3-6 个不同的维度/类别（如：技术探讨、水群闲聊、就业焦虑、深夜发情等）。
2. 为每个维度计算一个大致的百分比占位（总和小于等于 100%）。
3. 为每个维度写一句犀利、幽默、毒舌或温情的点评。
4. 给出一句总结性的全群表现评价。
5. 设定一个本次报告的主题标题和副标题。

## 点评风格指南：
- 语言要接地气，多用互联网黑话。
- 吐槽要精准，避重就轻。
- 如果群友在认真讨论技术，可以夸两句但也要带点调侃。
- 如果群友在无意义水群，请狠狠吐槽。

## 返回格式要求：
必须以纯 JSON 格式返回，不得包含任何 Markdown 格式。

```json
{{
  "title": "主题标题 (如: 互联网难民收容所)",
  "subtitle": "副标题 (如: 只要不工作，我们就是最好的朋友)",
  "dimensions": [
    {{
      "name": "维度名称",
      "percentage": 25.5,
      "comment": "维度的毒舌点评"
    }}
  ],
  "summary": "一句总结性的金句"
}}
```

群聊记录：
{messages_text}
"""

        return prompt_template.format(messages_text=messages_text)

    def extract_with_regex(self, result_text: str, max_count: int) -> list[dict]:
        """
        使用正则表达式提取质量分析数据（BaseAnalyzer 要求的接口）

        注意: 此方法供 BaseAnalyzer.analyze() 的降级流程使用，
        但由于聊天质量分析重写了 analyze()，实际由 analyze_quality() 中调用
        extract_quality_with_regex 实现。
        """
        return []

    def create_data_objects(self, data_list: list[dict]) -> list[QualityReview]:
        """
        满足 BaseAnalyzer 抽象要求。
        聊天质量分析的数据对象创建在 analyze_quality 中完成。
        """
        return []

    def _build_review_from_dict(self, data: dict) -> QualityReview:
        """
        从解析后的字典构建 QualityReview 对象

        Args:
            data: 解析后的 JSON 对象字典

        Returns:
            QualityReview 数据对象
        """
        # 控制维度占比总和不超过100%
        total_percentage = sum(
            max(0.0, min(100.0, float(d.get("percentage", 0))))
            for d in data.get("dimensions", [])
        )

        factor = 1.0
        if total_percentage > 100:
            factor = 100.0 / total_percentage

        dimensions = []
        for d in data.get("dimensions", []):
            raw_p = float(d.get("percentage", 0))

            final_p = round(max(0.0, min(100.0, raw_p)) * factor, 1)

            dimensions.append(
                QualityDimension(
                    name=d.get("name", "未知"),
                    percentage=final_p,
                    comment=d.get("comment", ""),
                )
            )

        # 自动分配颜色
        colors = [
            "#607d8b",
            "#2196f3",
            "#f44336",
            "#e91e63",
            "#ff9800",
            "#4caf50",
            "#009688",
            "#9c27b0",
        ]
        for i, d in enumerate(dimensions):
            d.color = colors[i % len(colors)]

        return QualityReview(
            title=data.get("title", "聊天质量锐评"),
            subtitle=data.get("subtitle", "今天的群里发生了什么？"),
            dimensions=dimensions,
            summary=data.get("summary", "今天也是充满活力的一天。"),
        )

    async def analyze_quality(
        self,
        messages: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
    ) -> tuple[QualityReview | None, TokenUsage]:
        """
        分析聊天质量

        流程遵循 BaseAnalyzer 的设计模式：
        1. 构建 prompt
        2. 调用 LLM
        3. 提取 token 使用统计
        4. JSON 解析（使用 parse_json_object_response）
        5. 正则降级（使用 extract_quality_with_regex）
        """
        try:
            # 1. 获取人格设定
            system_prompt = await self._build_system_prompt(umo)

            # 2. 构建 prompt
            prompt = self.build_prompt(messages)
            if not prompt:
                return None, TokenUsage()

            # 3. 调用 LLM
            response = await call_provider_with_retry(
                self.context,
                self.config_manager,
                prompt=prompt,
                max_tokens=self.get_max_tokens(),
                temperature=self.get_temperature(),
                umo=umo,
                provider_id_key=self.get_provider_id_key(),
                system_prompt=system_prompt,
            )

            if response is None:
                return None, TokenUsage()

            # 4. 提取 token 使用统计
            token_usage_dict = extract_token_usage(response)
            usage = TokenUsage(
                prompt_tokens=token_usage_dict["prompt_tokens"],
                completion_tokens=token_usage_dict["completion_tokens"],
                total_tokens=token_usage_dict["total_tokens"],
            )

            # 5. 提取响应文本
            result_text = extract_response_text(response)
            if not result_text:
                return None, usage

            # 6. JSON 解析（使用 parse_json_object_response）
            success, parsed_data, error_msg = parse_json_object_response(
                result_text, self.get_data_type()
            )

            if success and parsed_data:
                review = self._build_review_from_dict(parsed_data)
                logger.info(f"聊天质量分析成功，解析到 {len(review.dimensions)} 个维度")
                return review, usage

            # 7. 正则降级（使用 extract_quality_with_regex）
            logger.warning(f"聊天质量JSON解析失败，尝试正则表达式提取: {error_msg}")
            regex_data = extract_quality_with_regex(result_text)

            if regex_data:
                review = self._build_review_from_dict(regex_data)
                logger.info(
                    f"聊天质量正则提取成功，获得 {len(review.dimensions)} 个维度"
                )
                return review, usage

            # 8. 全部失败
            logger.error("聊天质量分析失败: JSON解析和正则表达式提取均未成功")
            return None, usage

        except Exception as e:
            logger.error(f"聊天质量分析解析失败: {e}", exc_info=True)
            return None, TokenUsage()

    # Override analyze to bridge the base class interface
    async def analyze(
        self,
        data: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
    ) -> tuple[list[QualityReview], TokenUsage]:
        review, usage = await self.analyze_quality(data, umo, session_id)
        return [review] if review else [], usage
