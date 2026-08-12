from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol


class DrawingRequestHooks(Protocol):
    """描述绘图请求服务依赖的宿主能力。"""

    def _build_target_url(self, raw_url: str, protocol: str) -> str: ...

    def _get_provider_value(self, name: str, provider: dict) -> Any: ...

    def _get_request_proxy(self, provider: dict | None = None) -> str | None: ...

    def _resolve_size(self, size_or_ratio: str) -> str: ...

    def _sanitize_url(self, url: str) -> str: ...

    def _summarize_response(self, data: Any) -> str: ...

    def _decode_base64(self, encoded: str) -> bytes: ...


@dataclass(slots=True)
class DrawingRequestContext:
    """聚合绘图请求执行所需的显式依赖。"""

    hooks: DrawingRequestHooks
    request_json: Callable[..., Awaitable[bytes | None]]
    extract_image: Callable[[Any, str | None], Awaitable[bytes | None]]

    def build_target_url(self, raw_url: str, protocol: str) -> str:
        return self.hooks._build_target_url(raw_url, protocol)

    def get_provider_value(self, name: str, provider: dict) -> Any:
        return self.hooks._get_provider_value(name, provider)

    def get_request_proxy(self, provider: dict | None = None) -> str | None:
        return self.hooks._get_request_proxy(provider)

    def resolve_size(self, size_or_ratio: str) -> str:
        return self.hooks._resolve_size(size_or_ratio)

    def sanitize_url(self, url: str) -> str:
        return self.hooks._sanitize_url(url)

    def summarize_response(self, data: Any) -> str:
        return self.hooks._summarize_response(data)

    def decode_base64(self, encoded: str) -> bytes:
        return self.hooks._decode_base64(encoded)
