"""HTML 静态资源本地化拦截流水线协调器与可观测性采集。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ...domain.repositories.resource_cache_repository import (
    IResourceCacheRepository,
)
from ...domain.services.resource_interceptor import (
    IHTMLResourceLocalizer,
    IResourceInterceptor,
)
from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from .interceptors.css_stylesheet_interceptor import CssStylesheetInterceptor
from .interceptors.font_face_interceptor import FontFaceInterceptor
from .interceptors.google_fonts_interceptor import GoogleFontsInterceptor
from .interceptors.preconnect_interceptor import PreconnectInterceptor
from .interceptors.remote_image_interceptor import RemoteImageInterceptor
from .interceptors.remote_script_interceptor import RemoteScriptInterceptor


class HTMLResourceLocalizer(IHTMLResourceLocalizer):
    """流水线协调器，依次将 HTML 内容传递给注册的各资源拦截器进行处理，并采集可观测性指标。"""

    def __init__(
        self,
        cache_repo: IResourceCacheRepository,
        plugin_root: Path | str | None = None,
        interceptors: list[IResourceInterceptor] | None = None,
    ):
        """初始化资源本地化协调器。

        Args:
            cache_repo: 静态资源持久化缓存仓储。
            plugin_root: 插件根路径（用于解析本地静态资源）。
            interceptors: 可选的自定义拦截器列表。
        """
        self.cache_repo = cache_repo
        self.plugin_root = Path(plugin_root) if plugin_root else None

        if interceptors is not None:
            self._interceptors = list(interceptors)
        else:
            self._interceptors = [
                GoogleFontsInterceptor(cache_repo),
                CssStylesheetInterceptor(cache_repo),
                FontFaceInterceptor(cache_repo),
                RemoteImageInterceptor(cache_repo, plugin_root=self.plugin_root),
                RemoteScriptInterceptor(cache_repo),
                PreconnectInterceptor(cache_repo),
            ]

    def add_interceptor(self, interceptor: IResourceInterceptor) -> None:
        """向流水线末尾追加新拦截器（开闭原则支持）。

        Args:
            interceptor: 拦截器实例。
        """
        self._interceptors.append(interceptor)

    async def localize_html(
        self, html_content: str, context: dict[str, Any] | None = None
    ) -> str:
        """执行拦截流水线，完成 HTML 外部资源全面本地化与内联，并收集利用率指标。

        Args:
            html_content: 原始 HTML 字符串。
            context: 可选上下文参数。

        Returns:
            完成本地化后的 HTML 字符串。
        """
        if not html_content:
            return ""

        ctx = dict(context or {})
        template_name = ctx.get("template", "global") or "global"
        ctx["template"] = template_name

        # 初始化遥测追踪结构
        telemetry: dict[str, Any] = {
            "template": template_name,
            "started_at": time.time(),
            "total_intercepted": 0,
            "cache_hits": 0,
            "downloaded": 0,
            "local_asset_hits": 0,
            "failed": 0,
            "inlined_bytes": 0,
            "duration_ms": 0.0,
            "items": [],
        }
        ctx["telemetry"] = telemetry
        if context is not None:
            context["telemetry"] = telemetry

        start_time = time.time()
        result = html_content

        for interceptor in self._interceptors:
            try:
                result = await interceptor.intercept(result, context=ctx)
            except Exception as e:
                logger.error(
                    f"[资源本地化] 拦截器 {interceptor.__class__.__name__} 执行异常: {e}"
                )

        telemetry["duration_ms"] = round((time.time() - start_time) * 1000, 2)
        telemetry["total_intercepted"] = len(telemetry["items"])
        if telemetry["total_intercepted"] > 0:
            telemetry["hit_rate"] = round(
                (telemetry["cache_hits"] + telemetry["local_asset_hits"])
                / telemetry["total_intercepted"]
                * 100,
                1,
            )
        else:
            telemetry["hit_rate"] = 100.0

        # 如果存在当前链路追踪，自动记录可观测性指标
        trace = TraceContext.current()
        if trace:
            trace.record_resource_localization(telemetry)

        return result
