"""
LLM分析器模块
负责使用LLM进行话题分析、用户称号分析和金句分析
"""

import json
import re
from datetime import datetime
import asyncio
from typing import List, Dict, Tuple
from astrbot.api import logger
from ...src.models.data_models import SummaryTopic, UserTitle, GoldenQuote, TokenUsage


class LLMAnalyzer:
    """LLM分析器"""

    def __init__(self, context, config_manager):
        self.context = context
        self.config_manager = config_manager

    async def _call_provider_with_retry(self, provider, prompt: str, max_tokens: int, temperature: float, umo: str = None):
        """
        调用LLM提供者，带超时、重试与退避。支持自定义服务商。

        Args:
            provider: LLM服务商实例或None。
            prompt (str): 输入的提示语。
            max_tokens (int): 最大生成token数。
            temperature (float): 采样温度。
            umo (str, optional): 指定使用的模型唯一标识符（Unique Model Object），
                用于选择特定的LLM服务商或模型。格式通常为字符串，例如 "gpt-3.5-turbo"。
                如果为None，则使用默认模型。

        Returns:
            LLM生成的结果。
        """
        timeout = self.config_manager.get_llm_timeout()
        retries = self.config_manager.get_llm_retries()
        backoff = self.config_manager.get_llm_backoff()

        # 获取自定义服务商参数
        custom_api_key = self.config_manager.get_custom_api_key()
        custom_api_base = self.config_manager.get_custom_api_base_url()
        custom_model = self.config_manager.get_custom_model_name()

        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                if custom_api_key and custom_api_base and custom_model:
                    logger.info(f"使用自定义LLM提供商: {custom_api_base} model={custom_model}")
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        headers = {
                            "Authorization": f"Bearer {custom_api_key}",
                            "Content-Type": "application/json"
                        }
                        payload = {
                            "model": custom_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": temperature
                        }
                        aio_timeout = aiohttp.ClientTimeout(total=timeout)
                        async with session.post(custom_api_base, json=payload, headers=headers, timeout=aio_timeout) as resp:
                            if resp.status != 200:
                                error_text = await resp.text()
                                logger.error(f"自定义LLM服务商请求失败: HTTP {resp.status}, 内容: {error_text}")
                            try:
                                response_json = await resp.json()
                            except Exception as json_err:
                                error_text = await resp.text()
                                logger.error(f"自定义LLM服务商响应JSON解析失败: {json_err}, 内容: {error_text}")
                                return None
                            # 兼容 OpenAI 格式，安全访问嵌套字段
                            content = None
                            try:
                                choices = response_json.get("choices")
                                if choices and isinstance(choices, list) and len(choices) > 0:
                                    message = choices[0].get("message")
                                    if message and isinstance(message, dict):
                                        content = message.get("content")
                                if content is None:
                                    logger.error(f"自定义LLM响应格式异常: {response_json}")
                                    return None
                            except Exception as key_err:
                                logger.error(f"自定义LLM响应结构解析失败: {key_err}, 响应内容: {response_json}")
                                return None
                            # 构造一个兼容原有逻辑的对象
                            class CustomResponse:
                                completion_text = content
                                raw_completion = response_json
                            return CustomResponse()
                else:
                    # 确保使用当前指定的模型
                    if provider is None:
                        provider = self.context.get_using_provider(umo=umo)
                        provider_id = 'unknown'
                        if provider:
                            try:
                                meta = provider.meta()
                                provider_id = meta.id
                            except Exception as e:
                                logger.debug(f"获取提供商ID失败: {e}")
                        logger.info(f"获取到的 provider ID: {provider_id}")
                        if not provider or provider_id == 'unknown':
                            logger.warning(f"获取的提供商不正确 (Provider ID: {provider_id})")

                    
                    logger.info(f"使用LLM provider: {provider}")
                    if not provider:
                        logger.error("provider 为空，无法调用 text_chat，直接返回 None")
                        return None
                    coro = provider.text_chat(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
                    return await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError as e:
                last_exc = e
                logger.warning(f"LLM请求超时: 第{attempt}次, timeout={timeout}s")
            except Exception as e:
                last_exc = e
                logger.warning(f"LLM请求失败: 第{attempt}次, 错误: {last_exc}")
            # 若非最后一次，等待退避后重试
            if attempt < retries:
                await asyncio.sleep(backoff * attempt)

        # 最终仍失败，记录错误并返回 None 由调用方处理降级，避免抛出异常
        logger.error(f"LLM请求全部重试失败: {last_exc}")
        return None

    async def analyze_topics(self, messages: List[Dict], umo: str = None) -> Tuple[List[SummaryTopic], TokenUsage]:
        """使用LLM分析话题"""
        try:
            # 提取文本消息
            text_messages = []
            for msg in messages:
                sender = msg.get("sender", {})
                nickname = sender.get("nickname", "") or sender.get("card", "")
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")

                for content in msg.get("message", []):
                    if content.get("type") == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        if text and len(text) > 2 and not text.startswith(("/")):
                            text_messages.append({
                                "sender": nickname,
                                "time": msg_time,
                                "content": text
                            })

            if not text_messages:
                return [], TokenUsage()

            # 构建LLM提示词，清理消息内容
            def clean_message_content(content):
                """清理消息内容，移除可能影响JSON解析的字符"""
                # 替换中文引号
                content = content.replace('"', '"').replace('"', '"')
                content = content.replace(''', "'").replace(''', "'")
                # 移除或替换其他特殊字符
                content = content.replace('\n', ' ').replace('\r', ' ')
                content = content.replace('\t', ' ')
                # 移除可能的控制字符
                content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
                return content.strip()

            messages_text = "\n".join([
                f"[{msg['time']}] {msg['sender']}: {clean_message_content(msg['content'])}"
                for msg in text_messages
            ])

            max_topics = self.config_manager.get_max_topics()
            prompt = f"""
你是一个帮我进行群聊信息总结的助手，生成总结内容时，你需要严格遵守下面的几个准则：
请分析接下来提供的群聊记录，提取出最多{max_topics}个主要话题。

对于每个话题，请提供：
1. 话题名称（突出主题内容，尽量简明扼要）
2. 主要参与者（最多5人）
3. 话题详细描述（包含关键信息和结论）

注意：
- 对于比较有价值的点，稍微用一两句话详细讲讲，比如不要生成 "Nolan 和 SOV 讨论了 galgame 中关于性符号的衍生情况" 这种宽泛的内容，而是生成更加具体的讨论内容，让其他人只看这个消息就能知道讨论中有价值的，有营养的信息。
- 对于其中的部分信息，你需要特意提到主题施加的主体是谁，是哪个群友做了什么事情，而不要直接生成和群友没有关系的语句。
- 对于每一条总结，尽量讲清楚前因后果，以及话题的结论，是什么，为什么，怎么做，如果用户没有讲到细节，则可以不用这么做。

群聊记录：
{messages_text}

重要：必须返回标准JSON格式，严格遵守以下规则：
1. 只使用英文双引号 " 不要使用中文引号 " "
2. 字符串内容中的引号必须转义为 \"
3. 多个对象之间用逗号分隔
4. 数组元素之间用逗号分隔
5. 不要在JSON外添加任何文字说明
6. 描述内容避免使用特殊符号，用普通文字表达

请严格按照以下JSON格式返回，确保可以被标准JSON解析器解析：
[
  {{
    "topic": "话题名称",
    "contributors": ["用户1", "用户2"],
    "detail": "话题描述内容"
  }},
  {{
    "topic": "另一个话题",
    "contributors": ["用户3", "用户4"],
    "detail": "另一个话题的描述"
  }}
]

注意：返回的内容必须是纯JSON，不要包含markdown代码块标记或其他格式
"""

            # 调用LLM
            response = await self._call_provider_with_retry(None, prompt, max_tokens=10000, temperature=0.6, umo=umo)
            if response is None:
                logger.error("话题分析调用LLM失败: provider返回None（重试失败）")
                return [], TokenUsage()

            # 提取token使用统计
            token_usage = TokenUsage()
            # 安全地提取 usage，避免 response.raw_completion.usage 为 None 导致的 AttributeError
            usage = None
            if getattr(response, 'raw_completion', None) is not None:
                usage = getattr(response.raw_completion, 'usage', None)
                if usage:
                    token_usage.prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                    token_usage.completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
                    token_usage.total_tokens = getattr(usage, 'total_tokens', 0) or 0

            # 解析响应
            if hasattr(response, 'completion_text'):
                result_text = response.completion_text
            else:
                result_text = str(response)

            # 尝试解析JSON
            try:
                # 提取JSON部分
                json_match = re.search(r'\[.*?\]', result_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group()
                    logger.debug(f"话题分析JSON原文: {json_text[:500]}...")

                    # 强化JSON清理和修复
                    json_text = self._fix_json(json_text)
                    logger.debug(f"修复后的JSON: {json_text[:300]}...")

                    topics_data = json.loads(json_text)
                    topics = [SummaryTopic(**topic) for topic in topics_data[:max_topics]]
                    logger.info(f"话题分析成功，解析到 {len(topics)} 个话题")
                    return topics, token_usage
                else:
                    logger.warning(f"话题分析响应中未找到JSON格式，响应内容: {result_text[:200]}...")
            except json.JSONDecodeError as e:
                logger.error(f"话题分析JSON解析失败: {e}")
                logger.debug(f"修复后的JSON: {json_text if 'json_text' in locals() else 'N/A'}")
                logger.debug(f"原始响应: {result_text}")

                # 如果JSON解析失败，尝试用正则表达式提取话题信息
                topics = self._extract_topics_with_regex(result_text, max_topics)
                if topics:
                    logger.info(f"正则表达式提取成功，获得 {len(topics)} 个话题")
                    return topics, token_usage
                else:
                    # 最后的降级方案
                    logger.info("正则表达式提取失败，使用默认话题...")
                    return [SummaryTopic(
                        topic="群聊讨论",
                        contributors=["群友"],
                        detail="今日群聊内容丰富，涵盖多个话题"
                    )], token_usage

            return [], token_usage

        except Exception as e:
            logger.error(f"话题分析失败: {e}")
            return [], TokenUsage()

    def _fix_json(self, text: str) -> str:
        """修复JSON格式问题"""
        # 移除markdown代码块标记
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*$', '', text)

        # 基础清理
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)

        # 替换中文引号为英文引号
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        # 处理字符串内容中的特殊字符
        # 转义字符串内的双引号
        def escape_quotes_in_strings(match):
            content = match.group(1)
            # 转义内部的双引号
            content = content.replace('"', '\\"')
            return f'"{content}"'

        # 先处理字段值中的引号
        text = re.sub(r'"([^"]*(?:"[^"]*)*)"', escape_quotes_in_strings, text)

        # 修复截断的JSON
        if not text.endswith(']'):
            last_complete = text.rfind('}')
            if last_complete > 0:
                text = text[:last_complete + 1] + ']'

        # 修复常见的JSON格式问题
        # 1. 修复缺失的逗号
        text = re.sub(r'}\s*{', '}, {', text)

        # 2. 确保字段名有引号
        text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)

        # 3. 移除多余的逗号
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        return text

    def _extract_topics_with_regex(self, result_text: str, max_topics: int) -> List[SummaryTopic]:
        """使用正则表达式提取话题信息"""
        try:
            topics = []

            # 更强的正则表达式提取话题信息，处理转义字符
            # 匹配每个完整的话题对象
            topic_pattern = r'\{\s*"topic":\s*"([^"]+)"\s*,\s*"contributors":\s*\[([^\]]+)\]\s*,\s*"detail":\s*"([^"]*(?:\\.[^"]*)*)"\s*\}'
            matches = re.findall(topic_pattern, result_text, re.DOTALL)

            if not matches:
                # 尝试更宽松的匹配
                topic_pattern = r'"topic":\s*"([^"]+)"[^}]*"contributors":\s*\[([^\]]+)\][^}]*"detail":\s*"([^"]*(?:\\.[^"]*)*)"'
                matches = re.findall(topic_pattern, result_text, re.DOTALL)

            for match in matches[:max_topics]:
                topic_name = match[0].strip()
                contributors_str = match[1].strip()
                detail = match[2].strip()

                # 清理detail中的转义字符
                detail = detail.replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ')

                # 解析参与者列表
                contributors = []
                for contrib in re.findall(r'"([^"]+)"', contributors_str):
                    contributors.append(contrib.strip())

                if not contributors:
                    contributors = ["群友"]

                topics.append(SummaryTopic(
                    topic=topic_name,
                    contributors=contributors[:5],  # 最多5个参与者
                    detail=detail
                ))

            return topics
        except Exception as e:
            logger.error(f"正则表达式提取失败: {e}")
            return []

    async def analyze_user_titles(self, messages: List[Dict], user_analysis: Dict, umo: str = None) -> Tuple[List[UserTitle], TokenUsage]:
        """使用LLM分析用户称号"""
        try:
            # 准备用户数据
            user_summaries = []
            for user_id, stats in user_analysis.items():
                if stats["message_count"] < 5:  # 过滤活跃度太低的用户
                    continue

                # 分析用户特征
                night_messages = sum(stats["hours"][h] for h in range(0, 6))
                day_messages = stats["message_count"] - night_messages
                avg_chars = stats["char_count"] / stats["message_count"] if stats["message_count"] > 0 else 0

                user_summaries.append({
                    "name": stats["nickname"],
                    "qq": int(user_id),
                    "message_count": stats["message_count"],
                    "avg_chars": round(avg_chars, 1),
                    "emoji_ratio": round(stats["emoji_count"] / stats["message_count"], 2),
                    "night_ratio": round(night_messages / stats["message_count"], 2),
                    "reply_ratio": round(stats["reply_count"] / stats["message_count"], 2)
                })

            if not user_summaries:
                return [], TokenUsage()

            # 按消息数量排序，取前N名
            max_user_titles = self.config_manager.get_max_user_titles()
            user_summaries.sort(key=lambda x: x["message_count"], reverse=True)
            user_summaries = user_summaries[:max_user_titles]

            # 构建LLM提示词
            users_text = "\n".join([
                f"- {user['name']} (QQ:{user['qq']}): "
                f"发言{user['message_count']}条, 平均{user['avg_chars']}字, "
                f"表情比例{user['emoji_ratio']}, 夜间发言比例{user['night_ratio']}, "
                f"回复比例{user['reply_ratio']}"
                for user in user_summaries
            ])

            prompt = f"""
请为以下群友分配合适的称号和MBTI类型。每个人只能有一个称号，每个称号只能给一个人。

可选称号：
- 龙王: 发言频繁但内容轻松的人
- 技术专家: 经常讨论技术话题的人
- 夜猫子: 经常在深夜发言的人
- 表情包军火库: 经常发表情的人
- 沉默终结者: 经常开启话题的人
- 评论家: 平均发言长度很长的人
- 阳角: 在群里很有影响力的人
- 互动达人: 经常回复别人的人
- ... (你可以自行进行拓展添加)

用户数据：
{users_text}

请以JSON格式返回，格式如下：
[
  {{
    "name": "用户名",
    "qq": 123456789,
    "title": "称号",
    "mbti": "MBTI类型",
    "reason": "获得此称号的原因"
  }}
]
"""

            # 调用LLM
            response = await self._call_provider_with_retry(None, prompt, max_tokens=1500, temperature=0.5, umo=umo)
            if response is None:
                logger.error("用户称号分析调用LLM失败: provider返回None（重试失败）")
                return [], TokenUsage()

            # 提取token使用统计
            token_usage = TokenUsage()
            # 安全地提取 usage，避免 response.raw_completion.usage 为 None 导致的 AttributeError
            usage = None
            if getattr(response, 'raw_completion', None) is not None:
                usage = getattr(response.raw_completion, 'usage', None)
                if usage:
                    token_usage.prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                    token_usage.completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
                    token_usage.total_tokens = getattr(usage, 'total_tokens', 0) or 0

            # 解析响应
            if hasattr(response, 'completion_text'):
                result_text = response.completion_text
            else:
                result_text = str(response)

            # debug日志：打印原始响应
            logger.debug(f"用户称号分析原始响应: {result_text[:500]}...")

            # 尝试解析JSON
            try:
                json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                if json_match:
                    logger.debug(f"用户称号分析JSON原文: {json_match.group()[:500]}...")
                    titles_data = json.loads(json_match.group())
                    return [UserTitle(**title) for title in titles_data], token_usage
            except Exception as e:
                logger.error(f"用户称号分析JSON解析失败: {e}")
                logger.debug(f"原始响应: {result_text}")

            return [], token_usage

        except Exception as e:
            logger.error(f"用户称号分析失败: {e}")
            return [], TokenUsage()

    async def analyze_golden_quotes(self, messages: List[Dict], umo: str = None) -> Tuple[List[GoldenQuote], TokenUsage]:
        """使用LLM分析群聊金句"""
        try:
            # 提取有趣的文本消息
            interesting_messages = []
            for msg in messages:
                sender = msg.get("sender", {})
                nickname = sender.get("nickname", "") or sender.get("card", "")
                msg_time = datetime.fromtimestamp(msg.get("time", 0)).strftime("%H:%M")

                for content in msg.get("message", []):
                    if content.get("type") == "text":
                        text = content.get("data", {}).get("text", "").strip()
                        # 过滤长度适中、可能有趣的消息
                        if 5 <= len(text) <= 100 and not text.startswith(("http", "www", "/")):
                            interesting_messages.append({
                                "sender": nickname,
                                "time": msg_time,
                                "content": text
                            })

            if not interesting_messages:
                return [], TokenUsage()

            # 构建LLM提示词
            messages_text = "\n".join([
                f"[{msg['time']}] {msg['sender']}: {msg['content']}"
                for msg in interesting_messages
            ])

            # 计算金句数量
            max_golden_quotes = self.config_manager.get_max_golden_quotes()

            prompt = f"""
请从以下群聊记录中挑选出{max_golden_quotes}句最具冲击力、最令人惊叹的"金句"。这些金句需满足：
- 核心标准：**逆天的神人发言**，即具备颠覆常识的脑洞、逻辑跳脱的表达或强烈反差感的原创内容
- 典型特征：包含某些争议话题元素、夸张类比、反常规结论、一本正经的"胡说八道"或突破语境的清奇思路，并且具备一定的冲击力，让人印象深刻。

对于每个金句，请提供：
1. 原文内容（完整保留发言细节）
2. 发言人昵称
3. 选择理由（具体说明其"逆天"之处，如逻辑颠覆点/脑洞角度/反差感/争议话题元素）

此外，我将对你进行严格约束：
- 优先筛选 **逆天指数最高** 的内容：发情、性压抑话题 > 争议话题 > 元素级 > 颠覆认知级 > 逻辑跳脱级 > 趣味调侃级，剔除单纯玩梗或网络热词堆砌的普通发言
- 重点标记包含极端类比、反常识论证或无厘头结论的内容，并且包含一定的争议话题元素。

群聊记录：
{messages_text}

请以JSON格式返回，格式如下：
[
  {{
    "content": "金句原文",
    "sender": "发言人昵称",
    "reason": "选择这句话的理由（需明确说明逆天特质）"
  }}
]
"""

            # 调用LLM
            response = await self._call_provider_with_retry(None, prompt, max_tokens=1500, temperature=0.7, umo=umo)
            if response is None:
                logger.error("金句分析调用LLM失败: provider返回None（重试失败）")
                return [], TokenUsage()

            # 提取token使用统计
            token_usage = TokenUsage()
            # 安全地提取 usage，避免 response.raw_completion.usage 为 None 导致的 AttributeError
            usage = None
            if getattr(response, 'raw_completion', None) is not None:
                usage = getattr(response.raw_completion, 'usage', None)
                if usage:
                    token_usage.prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
                    token_usage.completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
                    token_usage.total_tokens = getattr(usage, 'total_tokens', 0) or 0

            # 解析响应
            if hasattr(response, 'completion_text'):
                result_text = response.completion_text
            else:
                result_text = str(response)

            # debug日志：打印原始响应
            logger.debug(f"金句分析原始响应: {result_text[:500]}...")

            # 尝试解析JSON
            try:
                json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                if json_match:
                    logger.debug(f"金句分析JSON原文: {json_match.group()[:500]}...")
                    quotes_data = json.loads(json_match.group())
                    return [GoldenQuote(**quote) for quote in quotes_data[:max_golden_quotes]], token_usage
            except Exception as e:
                logger.error(f"金句分析JSON解析失败: {e}")
                logger.debug(f"原始响应: {result_text}")

            return [], token_usage

        except Exception as e:
            logger.error(f"金句分析失败: {e}")
            return [], TokenUsage()