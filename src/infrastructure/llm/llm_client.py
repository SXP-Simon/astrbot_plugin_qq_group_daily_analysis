"""
LLM 客户端 - 包装 AstrBot 的 LLM 提供商系统

该模块提供了一个访问 AstrBot LLM 功能的清晰接口，
抽象了提供商管理的细节。
"""

from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import logger

from ...domain.value_objects.statistics import TokenUsage
from ...domain.exceptions import LLMException, LLMRateLimitException


class LLMClient:
    """
    用于与 LLM 提供商交互的客户端。

    该类包装了 AstrBot 的提供商系统，并提供了一个
    清晰的接口来进行 LLM 调用。
    """

    def __init__(self, context: Any):
        """
        初始化 LLM 客户端。

        Args:
            context: 具有提供商访问权限的 AstrBot 插件上下文
        """
        self.context = context
        self._provider_cache: Dict[str, Any] = {}

    def get_provider(self, provider_id: Optional[str] = None) -> Any:
        """
        通过 ID 获取 LLM 提供商。

        Args:
            provider_id: 特定的提供商 ID，None 表示默认

        Returns:
            提供商实例

        Raises:
            LLMException: 如果未找到提供商
        """
        try:
            if provider_id and provider_id in self._provider_cache:
                return self._provider_cache[provider_id]

            if provider_id:
                provider = self.context.get_provider_by_id(provider_id)
            else:
                # 获取默认提供商
                providers = self.context.get_all_providers()
                if not providers:
                    raise LLMException("无可用 LLM 提供商")
                provider = providers[0]

            if provider:
                self._provider_cache[provider_id or "default"] = provider

            return provider

        except Exception as e:
            raise LLMException(f"获取提供商失败: {e}")

    async def chat_completion(
        self,
        prompt: str,
        provider_id: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, TokenUsage]:
        """
        发起聊天完成请求。

        Args:
            prompt: 用户提示词
            provider_id: 特定的提供商 ID (可选)
            max_tokens: 响应中的最大 token 数
            temperature: 采样温度
            system_prompt: 可选的系统提示词

        Returns:
            (response_text, token_usage) 元组

        Raises:
            LLMException: 如果请求失败
        """
        try:
            provider = self.get_provider(provider_id)
            if not provider:
                raise LLMException("无可用提供商", provider_id or "default")

            # 构建消息
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # 发起请求
            response = await provider.text_chat(
                messages=messages,
                session_id=None,  # 无状态
            )

            # 提取响应文本
            if hasattr(response, "completion_text"):
                response_text = response.completion_text
            elif isinstance(response, dict):
                response_text = response.get("completion_text", response.get("text", ""))
            else:
                response_text = str(response)

            # 提取 token 使用情况
            token_usage = TokenUsage()
            if hasattr(response, "usage"):
                usage = response.usage
                if hasattr(usage, "prompt_tokens"):
                    token_usage = TokenUsage(
                        prompt_tokens=usage.prompt_tokens or 0,
                        completion_tokens=usage.completion_tokens or 0,
                        total_tokens=usage.total_tokens or 0,
                    )

            return response_text, token_usage

        except Exception as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                raise LLMRateLimitException(str(e), provider_id or "default")
            raise LLMException(f"聊天完成请求失败: {e}", provider_id or "default")

    async def analyze_with_json_output(
        self,
        prompt: str,
        provider_id: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> Tuple[str, TokenUsage]:
        """
        发起期望 JSON 输出的完成请求。

        Args:
            prompt: 分析提示词
            provider_id: 特定的提供商 ID (可选)
            max_tokens: 响应中的最大 token 数
            temperature: 采样温度

        Returns:
            (response_text, token_usage) 元组
        """
        # 如果提示词中没有 JSON 指令，则添加
        json_instruction = "\nRespond with valid JSON only."
        if "json" not in prompt.lower():
            prompt = prompt + json_instruction

        return await self.chat_completion(
            prompt=prompt,
            provider_id=provider_id,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def list_available_providers(self) -> List[Dict[str, str]]:
        """
        列出所有可用的 LLM 提供商。

        Returns:
            提供商信息字典列表
        """
        try:
            providers = self.context.get_all_providers()
            return [
                {
                    "id": getattr(p, "id", str(i)),
                    "name": getattr(p, "name", f"Provider {i}"),
                    "type": getattr(p, "type", "unknown"),
                }
                for i, p in enumerate(providers)
            ]
        except Exception as e:
            logger.error(f"列出提供商失败: {e}")
            return []
