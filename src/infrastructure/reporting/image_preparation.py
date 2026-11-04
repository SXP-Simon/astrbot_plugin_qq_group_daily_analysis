"""Request snapshot and lazy HTML preparation for image rendering."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from .render_trace import render_span
from .typst_contracts import TypstIdentityOptions

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ...domain.value_objects import AnalysisResultPayload
    from ..config.rendering_config import (
        FontMode,
        RenderingResourceConfig,
        ScreenshotOptions,
    )
    from .render_data_preparer import RenderTemplateContext
    from .render_diagnostics import RenderAttemptRecord


class ImagePreparationSource(Protocol):
    """Existing preparation and external-result inspection boundaries."""

    async def _prepare_render_data(
        self,
        analysis_result: AnalysisResultPayload,
        template_theme: str | None = None,
        chart_template: str = "activity_chart.html",
        avatar_url_getter: Callable[[str, int | None], Awaitable[str | None]]
        | None = None,
        nickname_getter: Callable[[str], Awaitable[str | None]] | None = None,
        avatar_cache_namespace: str | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
        environment: str | None = None,
        resources: RenderingResourceConfig | None = None,
        font_mode: FontMode = "network",
    ) -> RenderTemplateContext: ...

    def _render_prepared_html(
        self,
        template_file: str,
        template_theme: str | None,
        payload: RenderTemplateContext,
    ) -> str: ...

    def _resolve_t2i_viewport_options(
        self, html_content: str, image_options: ScreenshotOptions
    ) -> tuple[ScreenshotOptions, str]: ...

    def _inspect_render_result(
        self, image_data: object, response_info: RenderAttemptRecord
    ) -> tuple[bool, str, int, str | None]: ...


@dataclass(frozen=True)
class ImageReportRequest:
    """Immutable request identity; a configuration save affects the next report."""

    result: AnalysisResultPayload
    group_id: str
    theme: str
    identity: TypstIdentityOptions = field(default_factory=TypstIdentityOptions)


@dataclass
class ImageHtmlPreparation:
    """Cache only a fully prepared HTML result for one image request."""

    source: ImagePreparationSource
    request: ImageReportRequest
    content: str | None = None
    payload: RenderTemplateContext | None = None
    environment: str | None = None
    resources: RenderingResourceConfig | None = None
    font_mode: FontMode = "network"
    template_ms: float = 0
    size_kb: float = 0

    async def prepare(
        self,
        environment: str,
        resources: RenderingResourceConfig | None,
        font_mode: FontMode,
    ) -> str:
        """Prepare inside an attempt so unsupported HTML can fall back to Typst.

        Args:
            environment: Snapshotted resource environment.
            resources: Snapshotted remote URLs for an external HTML service.
            font_mode: Local or network fonts for that service.

        Returns:
            Complete HTML, reusing a successful result with identical resources.

        Raises:
            ValueError: The template has no usable HTML entry point.
        """
        if self.content is not None and (environment, resources, font_mode) == (
            self.environment,
            self.resources,
            self.font_mode,
        ):
            return self.content
        async with render_span(
            "IMAGE_HTML_PREPARE",
            {"template": self.request.theme, "resource_environment": environment},
        ):
            identity = self.request.identity
            payload = await self.source._prepare_render_data(
                self.request.result,
                template_theme=self.request.theme,
                avatar_url_getter=identity.avatar_getter,
                nickname_getter=identity.nickname_getter,
                avatar_cache_namespace=identity.namespace,
                hide_user_names=identity.hide_names,
                allow_alphanumeric_user_ids=identity.extended_ids,
                environment=environment,
                resources=resources,
                font_mode=font_mode,
            )
            started = time.perf_counter()
            content = self.source._render_prepared_html(
                "image_template.html", self.request.theme, payload
            )
            if not content:
                raise ValueError(
                    "图片报告 HTML 模板返回空内容，请选择支持 HTML 图片的主题"
                )
            self.template_ms = round((time.perf_counter() - started) * 1000, 2)
            self.size_kb = round(len(content.encode("utf-8")) / 1024, 2)
            self.payload, self.content = payload, content
            self.environment, self.resources, self.font_mode = (
                environment,
                resources,
                font_mode,
            )
            return content
