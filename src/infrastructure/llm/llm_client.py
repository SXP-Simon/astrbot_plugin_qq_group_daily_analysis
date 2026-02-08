"""
LLM Client - Wrapper for AstrBot's LLM provider system

This module provides a clean interface to AstrBot's LLM capabilities,
abstracting away the provider management details.
"""

from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import logger

from ...domain.value_objects.statistics import TokenUsage
from ...domain.exceptions import LLMException, LLMRateLimitException


class LLMClient:
    """
    Client for interacting with LLM providers.

    This class wraps AstrBot's provider system and provides
    a clean interface for making LLM calls.
    """

    def __init__(self, context: Any):
        """
        Initialize the LLM client.

        Args:
            context: AstrBot plugin context with provider access
        """
        self.context = context
        self._provider_cache: Dict[str, Any] = {}

    def get_provider(self, provider_id: Optional[str] = None) -> Any:
        """
        Get an LLM provider by ID.

        Args:
            provider_id: Specific provider ID, or None for default

        Returns:
            Provider instance

        Raises:
            LLMException: If provider not found
        """
        try:
            if provider_id and provider_id in self._provider_cache:
                return self._provider_cache[provider_id]

            if provider_id:
                provider = self.context.get_provider_by_id(provider_id)
            else:
                # Get default provider
                providers = self.context.get_all_providers()
                if not providers:
                    raise LLMException("No LLM providers available")
                provider = providers[0]

            if provider:
                self._provider_cache[provider_id or "default"] = provider

            return provider

        except Exception as e:
            raise LLMException(f"Failed to get provider: {e}")

    async def chat_completion(
        self,
        prompt: str,
        provider_id: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> Tuple[str, TokenUsage]:
        """
        Make a chat completion request.

        Args:
            prompt: The user prompt
            provider_id: Specific provider ID (optional)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            system_prompt: Optional system prompt

        Returns:
            Tuple of (response_text, token_usage)

        Raises:
            LLMException: If the request fails
        """
        try:
            provider = self.get_provider(provider_id)
            if not provider:
                raise LLMException("No provider available", provider_id or "default")

            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Make the request
            response = await provider.text_chat(
                prompt=prompt,
                session_id=None,  # Stateless
            )

            # Extract response text
            if hasattr(response, "completion_text"):
                response_text = response.completion_text
            elif isinstance(response, dict):
                response_text = response.get("completion_text", response.get("text", ""))
            else:
                response_text = str(response)

            # Extract token usage
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
            raise LLMException(f"Chat completion failed: {e}", provider_id or "default")

    async def analyze_with_json_output(
        self,
        prompt: str,
        provider_id: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> Tuple[str, TokenUsage]:
        """
        Make a completion request expecting JSON output.

        Args:
            prompt: The analysis prompt
            provider_id: Specific provider ID (optional)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Tuple of (response_text, token_usage)
        """
        # Add JSON instruction to prompt if not present
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
        List all available LLM providers.

        Returns:
            List of provider info dictionaries
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
            logger.error(f"Failed to list providers: {e}")
            return []
