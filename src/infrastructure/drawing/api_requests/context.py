"""绘图请求服务与客户端之间的显式依赖契约。

供应商请求模块不直接依赖 ``DrawingClient``，只通过本上下文访问 URL 解析、
配置回退、代理、尺寸换算和响应解析能力。这样服务商文件保持可独立阅读，且
不会因继承关系隐式获得不相关的客户端状态。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol


class DrawingRequestHooks(Protocol):
    """描述绘图请求服务依赖的宿主能力。"""

    def _build_target_url(self, raw_url: str, protocol: str) -> str: ...

    def _get_provider_value(self, name: str, provider: dict) -> Any: ...

    def _get_request_proxy(self, provider: dict | None = None) -> str | None: ...

    def _resolve_size(self, size_or_ratio: str, aspect_ratio: str) -> str: ...

    def _sanitize_url(self, url: str) -> str: ...

    def _summarize_response(self, data: Any) -> str: ...

    def _decode_base64(self, encoded: str) -> bytes: ...


@dataclass(slots=True)
class DrawingRequestContext:
    """聚合绘图请求执行所需的显式依赖。

    该数据对象是组合关系的边界：请求模块只接收这个最小能力集合，HTTP JSON
    请求和图片提取则以函数形式注入，方便保留原有可替换入口。
    """

    hooks: DrawingRequestHooks
    request_json: Callable[..., Awaitable[bytes | None]]
    extract_image: Callable[[Any, str | None], Awaitable[bytes | None]]

    def build_target_url(self, raw_url: str, protocol: str) -> str:
        return self.hooks._build_target_url(raw_url, protocol)

    def get_provider_value(self, name: str, provider: dict) -> Any:
        return self.hooks._get_provider_value(name, provider)

    def get_request_proxy(self, provider: dict | None = None) -> str | None:
        return self.hooks._get_request_proxy(provider)

    def resolve_size(self, size_or_ratio: str, aspect_ratio: str) -> str:
        """按当前供应商条目的宽高比解析尺寸别名。

        Args:
            size_or_ratio: 条目中的尺寸别名、分辨率或比例。
            aspect_ratio: 同一条目中的目标宽高比。

        Returns:
            对应的 ``宽x高`` 尺寸字符串。
        """
        return self.hooks._resolve_size(size_or_ratio, aspect_ratio)

    def sanitize_url(self, url: str) -> str:
        return self.hooks._sanitize_url(url)

    def summarize_response(self, data: Any) -> str:
        return self.hooks._summarize_response(data)

    def decode_base64(self, encoded: str) -> bytes:
        return self.hooks._decode_base64(encoded)
