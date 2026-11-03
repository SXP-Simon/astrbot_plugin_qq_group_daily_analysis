"""Adapters for the three image rendering services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlsplit

from .html_renderer import RenderServiceInfo, describe_html_renderer

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ...domain.value_objects import AnalysisResultPayload
    from ..config.rendering_config import RenderingStrategyOptions, ScreenshotOptions
    from .typst_data import TypstIdentityOptions
    from .typst_renderer import TypstReportRenderer


class ImageBackend(Protocol):
    """An image service declares whether it needs prepared HTML."""

    requires_html: bool

    def describe(self, strategy: RenderingStrategyOptions) -> RenderServiceInfo: ...

    async def render(
        self,
        strategy: RenderingStrategyOptions,
        content: str | None,
        options: ScreenshotOptions,
    ) -> object: ...


@dataclass
class NativeImageBackend:
    """Keep native report input outside the HTML pipeline."""

    factory: Callable[[], TypstReportRenderer]
    result: AnalysisResultPayload
    theme: str
    identity: TypstIdentityOptions
    requires_html: bool = False

    def describe(self, strategy: RenderingStrategyOptions) -> RenderServiceInfo:
        return {
            "config_lookup": "插件独立 Typst 编译器",
            "configured_endpoint": "本地隔离进程",
        }

    async def render(
        self,
        strategy: RenderingStrategyOptions,
        content: str | None,
        options: ScreenshotOptions,
    ) -> bytes:
        return await self.factory().render(
            self.result, self.theme, strategy, self.identity
        )


class CustomRender(Protocol):
    """Typed boundary of the custom T2I client."""

    async def __call__(
        self,
        endpoint: str,
        html: str,
        options: ScreenshotOptions,
        token: str,
        *,
        request_timeout_ms: int,
    ) -> bytes: ...


@dataclass
class CustomImageBackend:
    """Adapt the independently configured HTTP service."""

    render_custom: CustomRender
    requires_html: bool = True

    def describe(self, strategy: RenderingStrategyOptions) -> RenderServiceInfo:
        url = urlsplit(strategy.get("service_endpoint", ""))
        host = url.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if url.port is not None:
            host += f":{url.port}"
        return {
            "config_lookup": "本轮自定义 T2I 服务",
            "configured_endpoint": f"{url.scheme}://{host}",
        }

    async def render(
        self,
        strategy: RenderingStrategyOptions,
        content: str | None,
        options: ScreenshotOptions,
    ) -> bytes:
        assert content is not None
        return await self.render_custom(
            strategy.get("service_endpoint", ""),
            content,
            options,
            strategy.get("service_token", ""),
            request_timeout_ms=strategy.get("request_timeout", 40000),
        )


@dataclass
class HostImageBackend:
    """Inspect the external host result at the existing image boundary."""

    callback: Callable[..., Awaitable[str | bytes | None]] | None
    requires_html: bool = True

    def describe(self, strategy: RenderingStrategyOptions) -> RenderServiceInfo:
        return (
            describe_html_renderer(self.callback)
            if callable(self.callback)
            else {
                "config_lookup": "未提供宿主渲染回调",
                "configured_endpoint": "未设置",
            }
        )

    async def render(
        self,
        strategy: RenderingStrategyOptions,
        content: str | None,
        options: ScreenshotOptions,
    ) -> object:
        if not callable(self.callback):
            raise RuntimeError("未提供可调用的 AstrBot 渲染接口")
        return await self.callback(content, {}, False, options)
