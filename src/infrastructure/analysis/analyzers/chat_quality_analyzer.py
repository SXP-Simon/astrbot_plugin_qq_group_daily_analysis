"""
聊天质量分析模块
专门处理群聊质量锐评分析
"""

from datetime import datetime

from ....domain.models.data_models import QualityDimension, QualityReview, TokenUsage
from ....utils.logger import logger
from ...utils.template_utils import render_template
from ..utils import InfoUtils
from ..utils.json_utils import extract_quality_with_regex, parse_json_object_response
from ..utils.llm_utils import (
    call_provider_with_retry,
    extract_response_text,
    extract_token_usage,
)
from ..utils.response_validation import validate_quality_review_item
from ..utils.structured_output_schema import JSONObject, build_chat_quality_schema
from .base_analyzer import BaseAnalyzer


class ChatQualityAnalyzer(BaseAnalyzer[QualityReview, list[dict]]):
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

    def get_response_schema_name(self) -> str:
        return "daily_chat_quality_review"

    def get_response_schema(self) -> JSONObject:
        return build_chat_quality_schema(self.get_max_count())

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

        if prompt_template:
            return render_template(prompt_template, messages_text=messages_text)

        prompt_template = """请分析以下群聊记录，输出一份"聊天质量锐评"。

## 任务目标：
1. **维度划分**：将聊天内容划分为 3-6 个【高层级、抽象、泛化】的维度（例如：就业焦虑、生涯规划、技术方案研究、情感树洞、无意义水群等）。
2. **严禁在维度名称（name）中出现任何具体的群聊人物名、项目名、具体的报错内容或细碎的事件点。标题必须保持高度抽象且字数简练（2-6个字）。**
3. 为每个维度计算一个大致的百分比占位（总和小于等于 100%）。
4. **点评内容**：为每个维度写一句犀利、幽默、毒舌或温情的点评。具体的吐槽内容、具体的细节事件描述请放在这里。
5. **全群表现**：给出一句总结性的评价，作为总结标题对应的“金句”。
6. **主题设定**：设定一个本次报告的主题标题和副标题。

## 点评风格指南：
- 语言要接地气，多用互联网黑话。吐槽要精准，避重就轻。
- **只有维度名称（name）需要抽象，点评（comment）和总结（summary）可以非常具体和生动。**

## 返回格式要求：
必须以纯 JSON 格式返回，不得包含任何 Markdown 格式。

```json
{{
  "title": "今日群聊主题",
  "subtitle": "副标题",
  "dimensions": [
    {{
      "name": "抽象维度名",
      "percentage": 比例,
      "comment": "维度的毒舌点评"
    }}
  ],
  "summary": "一句总结性的金句"
}}
```

群聊记录：
${messages_text}
"""

        return render_template(prompt_template, messages_text=messages_text)

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

    def _validate_review_payload(
        self, data: dict
    ) -> tuple[bool, dict | None, str | None]:
        return validate_quality_review_item(data)

    async def _retry_parse_quality_object(
        self,
        *,
        original_prompt: str,
        previous_output: str,
        parse_error: str | None,
        umo: str | None,
        system_prompt: str | None,
        base_temperature: float | None,
    ) -> dict | None:
        response_format = self.get_response_format()
        if response_format is None:
            return None

        for idx, temperature in enumerate(
            self.get_schema_retry_temperatures(base_temperature), start=1
        ):
            retry_prompt = self.build_schema_retry_prompt(
                original_prompt=original_prompt,
                previous_output=previous_output,
                parse_error=parse_error,
                attempt_index=idx,
            )
            logger.warning(
                f"聊天质量结构化解析失败，触发 schema 修复重试 "
                f"(attempt={idx}, temperature={temperature:.1f})"
            )
            retry_response = await call_provider_with_retry(
                self.context,
                self.config_manager,
                prompt=retry_prompt,
                umo=umo,
                provider_id_key=self.get_provider_id_key(),
                system_prompt=system_prompt,
                response_format=response_format,
                extra_generate_kwargs={"temperature": temperature},
            )
            if retry_response is None:
                continue

            retry_text = extract_response_text(retry_response)
            if not retry_text:
                continue

            retry_success, retry_parsed_data, _ = parse_json_object_response(
                retry_text, self.get_data_type()
            )
            if retry_success and retry_parsed_data:
                valid, normalized, _ = self._validate_review_payload(retry_parsed_data)
                if valid and normalized:
                    return normalized

            retry_regex_data = extract_quality_with_regex(retry_text)
            if retry_regex_data:
                valid, normalized, _ = self._validate_review_payload(retry_regex_data)
                if valid and normalized:
                    return normalized

        return None

    async def summarize_batch_reviews(
        self,
        batch_reviews: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
    ) -> tuple[QualityReview | None, TokenUsage]:
        """
        汇总多个增量批次的质量报告，生成最终的每日全天总评。
        """
        if not batch_reviews:
            return None, TokenUsage()

        if len(batch_reviews) == 1:
            return self._build_review_from_dict(batch_reviews[0]), TokenUsage()

        try:
            # 构建汇总用的提示词
            reviews_text = ""
            for i, rev in enumerate(batch_reviews):
                title = rev.get("title", "未命名")
                summary = rev.get("summary", "")
                dims = ", ".join(
                    [
                        f"{d.get('name')}({d.get('percentage')}%)"
                        for d in rev.get("dimensions", [])
                    ]
                )
                reviews_text += f"\n批次 {i + 1} [{title}]:\n- 维度表现: {dims}\n- 核心摘要: {summary}\n"

            # 获取配置中的汇总提示词模板，如果没有则使用默认模板
            prompt_template = (
                self.config_manager.get_quality_summary_prompt()
                or """你现在有一份今天全天分散时间段的多个“增量批次点评笔记”。
你的任务是将这些分散的笔记汇总成一份最终的“全天聊天质量终极锐评”。

## 任务目标：
1. **全局抽象维度**：根据各批次的维度表现，平衡权重，提取出 3-6 个覆盖全天的【核心、上层抽象】课题维度（如：职场/行业风向、技术架构演进、社畜心理博弈等）。
2. **严禁在维度名称（name）中出现具体的批次细节。标题必须代表全天的某种趋势。**
3. **百分比融合**：根据全天笔记的频率和强度，给出一个代表全天整体分布的比例（总和不超过100%）。
4. **终极点评**：为每个汇总维度写出一句升华后的全天总结性点评。可以融合具体批次中的有趣槽点。
5. **终极总结**：拟定全天的大型主题标题、副标题，并给出一句霸气的全天表现总结。

## 风格要求：
- 只有维度名称（name）需要高度概括抽象。
- 点评（comment）和总结（summary）请尽量生动、具体，要把一整天的梗串联起来。

## 返回格式要求：
必须以纯 JSON 格式返回，不得包含任何 Markdown 格式。

```json
{{
  "title": "今日群聊主题",
  "subtitle": "副标题",
  "dimensions": [
    {{
      "name": "抽象大类标题",
      "percentage": 比例,
      "comment": "维度的全天锐评"
    }}
  ],
  "summary": "全天总结金句"
}}
```
"""
            )
            prompt = render_template(prompt_template, reviews_text=reviews_text)

            # 调用 LLM 进行汇总
            system_prompt = await self._build_system_prompt(umo)
            base_temperature = await self._resolve_provider_temperature(
                self.get_provider_id_key(), umo
            )

            # 应用人设强化注入
            prompt = self._apply_persona_reinforcement(prompt, system_prompt)

            response = await call_provider_with_retry(
                self.context,
                self.config_manager,
                prompt=prompt,
                umo=umo,
                provider_id_key=self.get_provider_id_key(),
                system_prompt=system_prompt,
                response_format=self.get_response_format(),
            )

            if response is None:
                return None, TokenUsage()

            token_usage_dict = extract_token_usage(response)
            usage = TokenUsage(
                prompt_tokens=token_usage_dict["prompt_tokens"],
                completion_tokens=token_usage_dict["completion_tokens"],
                total_tokens=token_usage_dict["total_tokens"],
            )

            result_text = extract_response_text(response)
            if not result_text:
                return None, usage

            success, parsed_data, error_msg = parse_json_object_response(
                result_text, "汇总质量分析"
            )

            if success and parsed_data:
                valid, normalized, validation_error = self._validate_review_payload(
                    parsed_data
                )
                if valid and normalized:
                    review = self._build_review_from_dict(normalized)
                    logger.info(
                        f"聊天质量汇总分析成功，解析到 {len(review.dimensions)} 个汇总维度"
                    )
                    return review, usage
                error_msg = validation_error or error_msg

            repaired_data = await self._retry_parse_quality_object(
                original_prompt=prompt,
                previous_output=result_text,
                parse_error=error_msg,
                umo=umo,
                system_prompt=system_prompt,
                base_temperature=base_temperature,
            )
            if repaired_data:
                review = self._build_review_from_dict(repaired_data)
                logger.info(
                    f"聊天质量汇总 schema 修复重试成功，解析到 {len(review.dimensions)} 个汇总维度"
                )
                return review, usage

            # 降级：如果汇总失败，返回最新的一个
            logger.warning(f"聊天质量汇总分析失败，降级使用最新批次: {error_msg}")
            return self._build_review_from_dict(batch_reviews[-1]), usage

        except Exception as e:
            logger.error(f"聊天质量汇总分析异常: {e}", exc_info=True)
            return self._build_review_from_dict(batch_reviews[-1]), TokenUsage()

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
            base_temperature = await self._resolve_provider_temperature(
                self.get_provider_id_key(), umo
            )

            # 2. 构建 prompt
            prompt = self.build_prompt(messages)
            if not prompt:
                return None, TokenUsage()

            # 应用人设强化注入
            prompt = self._apply_persona_reinforcement(prompt, system_prompt)

            # 3. 调用 LLM
            response = await call_provider_with_retry(
                self.context,
                self.config_manager,
                prompt=prompt,
                umo=umo,
                provider_id_key=self.get_provider_id_key(),
                system_prompt=system_prompt,
                response_format=self.get_response_format(),
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
                valid, normalized, validation_error = self._validate_review_payload(
                    parsed_data
                )
                if valid and normalized:
                    review = self._build_review_from_dict(normalized)
                    logger.debug(
                        f"聊天质量分析成功，解析到 {len(review.dimensions)} 个维度"
                    )
                    return review, usage
                error_msg = validation_error or error_msg

            regex_data = extract_quality_with_regex(result_text)
            if regex_data:
                valid, normalized, validation_error = self._validate_review_payload(
                    regex_data
                )
                if valid and normalized:
                    review = self._build_review_from_dict(normalized)
                    logger.debug(
                        f"聊天质量首轮结构化失败后，正则提取成功，获得 {len(review.dimensions)} 个维度"
                    )
                    return review, usage
                error_msg = validation_error or error_msg

            repaired_data = await self._retry_parse_quality_object(
                original_prompt=prompt,
                previous_output=result_text,
                parse_error=error_msg,
                umo=umo,
                system_prompt=system_prompt,
                base_temperature=base_temperature,
            )
            if repaired_data:
                review = self._build_review_from_dict(repaired_data)
                logger.debug(
                    f"聊天质量 schema 修复重试成功，解析到 {len(review.dimensions)} 个维度"
                )
                return review, usage

            # 7. 全部失败
            logger.error(f"聊天质量分析失败: JSON解析和正则提取均未成功: {error_msg}")
            return None, usage

        except Exception as e:
            logger.error(f"聊天质量分析失败: {e}", exc_info=True)
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
