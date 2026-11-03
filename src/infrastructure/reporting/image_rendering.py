"""Bounded image rendering orchestration, independent of concrete services."""

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...utils.logger import logger
from .image_attempt import ImageAttempt, ImageRenderTelemetry
from .image_preparation import (
    ImageHtmlPreparation,
    ImagePreparationSource,
    ImageReportRequest,
)
from .render_diagnostics import summarize_render_error
from .render_trace import render_span

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..config.rendering_config import RenderingStrategyOptions
    from .image_backends import ImageBackend


@dataclass
class ImageReportSession:
    """Own one request's queue, fallback policy, HTML cache and output inspection."""

    source: ImagePreparationSource
    request: ImageReportRequest
    backends: Mapping[str, ImageBackend]
    semaphore: asyncio.Semaphore
    environment: str
    timeout: float

    async def run(
        self, strategies: list[RenderingStrategyOptions]
    ) -> tuple[str | None, str | None]:
        """Try the snapshotted strategies until an image succeeds or time expires.

        Args:
            strategies: Ordered service/resource snapshots for this request.

        Returns:
            Image path or Base64 URI, and the last successful HTML if applicable.
        """
        html = ImageHtmlPreparation(self.source, self.request)
        telemetry = ImageRenderTelemetry()
        acquired = False
        try:
            async with render_span(
                "IMAGE_RENDER_QUEUE", {"group_id": self.request.group_id}
            ):
                await self.semaphore.acquire()
                acquired = True
            deadline = asyncio.get_running_loop().time() + self.timeout
            last_error = "没有可用的渲染策略。"
            attempt: ImageAttempt | None = None
            for index, strategy in enumerate(strategies, 1):
                if asyncio.get_running_loop().time() >= deadline:
                    break
                attempt = ImageAttempt(
                    index,
                    strategy,
                    self.backends[strategy.get("render_service", "astrbot")],
                    self.environment,
                )
                logger.debug(
                    f"[T2I诊断 v2] 开始生成图片；配置读取：{attempt.info['config_lookup']}；配置地址：{attempt.info['configured_endpoint']}"
                )
                telemetry.attach(attempt)
                image, expired = await self._attempt(attempt, html, telemetry, deadline)
                if image is not None:
                    return (
                        image,
                        html.content if attempt.backend.requires_html else None,
                    )
                last_error = attempt.error
                logger.warning(f"第 {index} 次图片生成失败：{last_error}")
                if expired:
                    break
            last = attempt.info if attempt else None
            logger.error(
                f"图片生成未成功，最后一次失败原因：{last_error}"
                + (
                    f"\n配置读取：{last['config_lookup']}；配置地址：{last['configured_endpoint']}"
                    if last
                    else ""
                )
            )
            return None, html.content
        finally:
            if acquired:
                self.semaphore.release()

    async def _attempt(
        self,
        attempt: ImageAttempt,
        html: ImageHtmlPreparation,
        telemetry: ImageRenderTelemetry,
        deadline: float,
    ) -> tuple[str | None, bool]:
        """Contain preparation and service failures within a single bounded attempt.

        Args:
            attempt: Mutable diagnostic record already visible in the task panel.
            html: Request-scoped transactional HTML cache.
            telemetry: Parent report metrics publisher.
            deadline: Shared monotonic deadline across all attempts.

        Returns:
            A valid image and whether the shared deadline has expired.

        Raises:
            asyncio.CancelledError: Cancellation never starts another strategy.
        """
        expired = False
        timeout = asyncio.timeout_at(deadline)
        async with render_span(
            "IMAGE_RENDER_ATTEMPT",
            {
                "attempt": attempt.index,
                "strategy_name": attempt.record.get("strategy_name"),
                "service_type": attempt.record.get("service_type"),
            },
        ) as span:
            try:
                async with timeout:
                    image_data = await self._render(attempt, html)
                    valid, attempt.error, size, dimensions = await asyncio.to_thread(
                        self.source._inspect_render_result, image_data, attempt.response
                    )
                if valid and isinstance(image_data, (bytes, str)):
                    attempt.status = "success"
                    telemetry.success(attempt, self.request, html, size, dimensions)
                    logger.info(
                        f"图片生成成功 (轮次 {attempt.index}, 视口 {attempt.viewport})"
                    )
                    return (
                        f"base64://{base64.b64encode(image_data).decode('utf-8')}"
                        if isinstance(image_data, bytes)
                        else image_data,
                        False,
                    )
                attempt.status = "failed"
            except asyncio.CancelledError:
                attempt.status, attempt.error = "cancelled", "本轮图片渲染已停止。"
                raise
            except Exception as error:
                attempt.status = "failed"
                expired = isinstance(error, TimeoutError) and timeout.expired()
                detail = summarize_render_error(str(error)) or (
                    "请求超时，未提供更多信息"
                    if isinstance(error, TimeoutError)
                    else "未提供具体原因"
                )
                attempt.error = f"{type(error).__name__}：{detail}"
                if expired:
                    attempt.error = f"本次图片渲染已达到总等待上限（{self.timeout:g} 秒），已停止后续方案。"
                elif (
                    isinstance(error, TimeoutError)
                    and attempt.record.get("service_type") == "astrbot"
                ):
                    attempt.error += "\n排查建议：请先确认 AstrBot 能否连接 T2I 服务，并查看同一时间的服务日志。如果日志显示页面资源加载超时，再检查模板图片、字体等 CDN 资源在渲染服务所在环境中能否访问。"
                logger.debug("图片渲染异常的调用堆栈", exc_info=True)
            finally:
                attempt.finish()
                if span:
                    span["status"] = attempt.status
                    span["payload"].update(attempt.record)
        return None, expired

    async def _render(
        self, attempt: ImageAttempt, html: ImageHtmlPreparation
    ) -> object:
        """Prepare only the representation required by this service.

        Args:
            attempt: Service adapter and its screenshot-only options.
            html: Request-scoped HTML cache.

        Returns:
            Untrusted service output for validation at the existing boundary.
        """
        content = None
        if attempt.backend.requires_html:
            content = await html.prepare(
                attempt.environment,
                attempt.strategy.get("resource_urls"),
                attempt.font_mode,
            )
            attempt.options, attempt.viewport = (
                self.source._resolve_t2i_viewport_options(content, attempt.options)
            )
            if attempt.options.get("type") == "png":
                attempt.options.pop("quality", None)
        else:
            attempt.viewport = "Typst 固定 940px"
        started = time.perf_counter()
        result = await attempt.backend.render(
            attempt.strategy, content, attempt.options
        )
        attempt.render_ms = round((time.perf_counter() - started) * 1000, 2)
        return result
