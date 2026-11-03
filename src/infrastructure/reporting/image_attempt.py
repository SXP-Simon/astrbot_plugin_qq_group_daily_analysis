"""Per-attempt strategy snapshot and image rendering telemetry."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from ...shared.trace_context import TraceContext

if TYPE_CHECKING:
    from ...shared.trace_context import SpanRecord
    from ..config.rendering_config import (
        FontMode,
        RenderingStrategyOptions,
        ScreenshotOptions,
    )
    from .html_renderer import RenderServiceInfo
    from .image_backends import ImageBackend
    from .image_preparation import ImageHtmlPreparation, ImageReportRequest
    from .render_diagnostics import RenderAttemptRecord


@dataclass
class ImageAttempt:
    """Separate service metadata from screenshot options before dispatch."""

    index: int
    strategy: RenderingStrategyOptions
    backend: ImageBackend
    default_environment: str
    status: Literal["running", "success", "failed", "cancelled"] = "running"
    viewport: str = "default"
    error: str = "渲染服务返回了空内容。"
    render_ms: float = 0
    started: float = field(default_factory=time.perf_counter)
    options: ScreenshotOptions = field(init=False)
    record: RenderAttemptRecord = field(init=False)
    response: RenderAttemptRecord = field(init=False)
    info: RenderServiceInfo = field(init=False)
    environment: str = field(init=False)
    font_mode: FontMode = field(init=False)

    def __post_init__(self) -> None:
        options = self.strategy.copy()
        name = options.pop("strategy_name", f"方案 {self.index}")
        priority = options.pop("strategy_priority", None)
        self.environment = options.pop("resource_environment", self.default_environment)
        resources = options.pop("resource_urls", None)
        service = options.pop("render_service", "astrbot")
        configured_font_mode = options.pop("font_mode", "network")
        self.font_mode = (
            "local"
            if service == "typst"
            else configured_font_mode
            if service == "custom"
            else "network"
        )
        options.pop("service_endpoint", None)
        options.pop("service_token", None)
        timeout = options.pop("request_timeout", 40000)
        self.options = options
        self.info = self.backend.describe(self.strategy)
        self.response = {"return_type": "未返回", "render_service": self.info}
        self.record = {
            "attempt": self.index,
            "strategy_name": name,
            "priority": priority,
            "service_type": service,
            "font_mode": self.font_mode,
            "resource_environment": self.environment,
            "resource_urls": resources.copy() if resources is not None else None,
            "render_timeout_ms": options.get("timeout"),
            "request_timeout_ms": timeout if service == "custom" else None,
            "started_at": time.time(),
            "status": "running",
            "type": str(options.get("type", "jpeg")),
            **self.response,
        }

    def finish(self) -> None:
        self.record.update(self.response)
        self.record.update(
            viewport=self.viewport,
            duration_ms=round((time.perf_counter() - self.started) * 1000, 2),
            status=self.status,
        )
        if self.status != "success":
            self.record["error"] = self.error


class ImageRenderTelemetry:
    """Keep renderer diagnostics out of dispatch and HTML preparation."""

    def __init__(self) -> None:
        self.trace = TraceContext.current()
        self.start = len(self.trace._spans) if self.trace else 0
        self.parent: SpanRecord | None = (
            next(
                (
                    span
                    for span in reversed(self.trace._spans)
                    if span["stage_name"] == "RENDER_REPORT"
                    and span["status"] == "running"
                ),
                None,
            )
            if self.trace
            else None
        )

    def attach(self, attempt: ImageAttempt) -> None:
        if not self.parent:
            return
        payload = self.parent["payload"]
        payload["render_service"] = attempt.info
        attempts = payload.setdefault("render_attempts", [])
        if isinstance(attempts, list):
            attempts.append(attempt.record)

    def success(
        self,
        attempt: ImageAttempt,
        request: ImageReportRequest,
        html: ImageHtmlPreparation,
        image_size: int,
        dimensions: str | None,
    ) -> None:
        """Publish successful output and retain earlier failures as recovery warnings.

        Args:
            attempt: Successful service attempt.
            request: Original immutable request.
            html: Successful HTML cache, unused for native output.
            image_size: Validated encoded byte count.
            dimensions: Validated image dimensions.
        """
        if self.trace:
            for span in self.trace._spans[self.start :]:
                if span["status"] == "failed" and (
                    span["stage_name"].startswith("TYPST_")
                    or span["stage_name"]
                    in ("IMAGE_RENDER_ATTEMPT", "IMAGE_HTML_PREPARE")
                ):
                    span["status"] = "warning"
                    span["payload"]["failure_reason"] = span["payload"].pop("error", "")
                    span["payload"]["warning"] = "后续渲染方案已恢复图片报告"
        if not self.parent:
            return
        native = not attempt.backend.requires_html
        result = request.result
        stats = result.get("statistics")
        self.parent["payload"].update(
            {
                "format": "image",
                "template": request.theme,
                "viewport": attempt.viewport,
                "render_attempt": attempt.index,
                "resource_environment": attempt.environment,
                "image_format": str(attempt.options.get("type", "jpeg")),
                "image_bytes": image_size,
                "dimensions": dimensions,
                "template_render_ms": 0 if native else html.template_ms,
                "html_size_kb": 0 if native else html.size_kb,
                "t2i_render_ms": attempt.render_ms,
                "topics_rendered": len(result.get("topics") or []),
                "titles_rendered": len(result.get("user_titles") or []),
                "quotes_rendered": len(stats.golden_quotes) if stats else 0,
                "html_chars": 0 if native else len(html.content or ""),
                "hide_user_names": request.identity.hide_names,
            }
        )
        if not native:
            self.parent["payload"]["avatars_processed"] = (
                len(html.payload["avatar_reuse_registry"]) if html.payload else 0
            )
