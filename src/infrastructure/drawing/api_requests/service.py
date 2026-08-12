"""绘图供应商请求服务的统一分发层。

每个服务商协议位于独立模块中，本服务仅提供稳定的调用入口并传递共享上下文。
``DrawingClient`` 因此不需要了解某个服务商的请求体格式，也无需使用 Mixin
将大量实现混入客户端类。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chat import call_chat_api
from .common import post_json_for_image
from .context import DrawingRequestContext
from .gemini import call_gemini_api
from .google import call_google_api
from .grok import call_grok_api
from .images import call_images_api
from .presets import call_preset_api, call_stepfun_api


@dataclass(slots=True)
class DrawingApiRequestService:
    """协调各服务商请求实现并对外暴露统一调用入口。

    每个方法保持一层直接转发，目的是固定高层调用契约；服务商特有的参数和
    能力限制仍留在各自模块，避免该类成为新的请求逻辑聚集点。
    """

    context: DrawingRequestContext

    async def call_google_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None,
        provider: dict,
    ) -> bytes | None:
        return await call_google_api(self.context, prompt, images_data, provider)

    async def call_preset_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None,
        provider: dict,
        provider_type: str,
    ) -> bytes | None:
        return await call_preset_api(
            self.context, prompt, images_data, provider, provider_type
        )

    async def post_json_for_image(
        self,
        target_url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int | float,
        provider_name: str,
        provider: dict,
    ) -> bytes | None:
        return await post_json_for_image(
            self.context,
            target_url,
            headers,
            payload,
            timeout,
            provider_name,
            provider,
        )

    async def call_stepfun_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None,
        provider: dict,
        api_key: str,
        model: str,
        timeout: int | float,
    ) -> bytes | None:
        return await call_stepfun_api(
            self.context, prompt, images_data, provider, api_key, model, timeout
        )

    async def call_images_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        provider: dict | None = None,
    ) -> bytes | None:
        return await call_images_api(self.context, prompt, images_data, provider)

    async def call_grok_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        provider: dict | None = None,
    ) -> bytes | None:
        return await call_grok_api(self.context, prompt, images_data, provider)

    async def call_gemini_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        provider: dict | None = None,
    ) -> bytes | None:
        return await call_gemini_api(self.context, prompt, images_data, provider)

    async def call_chat_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        provider: dict | None = None,
    ) -> bytes | None:
        return await call_chat_api(self.context, prompt, images_data, provider)
