from __future__ import annotations

import asyncio
import base64
import os
import tempfile
import time
from contextlib import nullcontext
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from ...application.services.merged_forward_delivery import PreparedForwardMessage
from ...shared.constants import AnalysisStage
from ...shared.trace_context import TraceContext
from ...utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from ...application.handlers.comic_command_handler import ComicCommandHandler
    from ...application.services.merged_forward_delivery import (
        MergedForwardDeliveryService,
    )
    from ...application.services.wordcloud_delivery_service import (
        WordCloudDeliveryService,
    )
    from ...domain.repositories.platform_adapter_repository import (
        GroupAlbumSupportProtocol,
        GroupFileSupportProtocol,
    )
    from ...domain.value_objects import AnalysisResultPayload
    from ..config.config_manager import ConfigManager
    from ..messaging.message_sender import MessageSender
    from ..platform.adapters.onebot_adapter import OneBotAdapter
    from .generators import ReportGenerator


class ReportDispatcher:
    """
    报告分发器
    负责协调报告生成、格式选择、消息发送和失败重试
    """

    config_manager: ConfigManager
    report_generator: ReportGenerator | None
    message_sender: MessageSender

    # 普通投递与合并准备独立计时，防止慢普通任务无限占用本次分发。
    _ORDINARY_DELIVERY_TIMEOUT_SECONDS = 1800

    def __init__(
        self,
        config_manager: ConfigManager,
        report_generator: ReportGenerator | None,
        message_sender: MessageSender,
    ) -> None:
        self.config_manager = config_manager
        self.report_generator = report_generator
        self.message_sender = message_sender
        self.wordcloud_delivery: WordCloudDeliveryService | None = None
        self.merged_delivery: MergedForwardDeliveryService | None = None
        self.comic_handler: ComicCommandHandler | None = None
        self._html_render_func: Callable[..., Awaitable[str | bytes | None]] | None = (
            None
        )

    def set_html_render(
        self, render_func: Callable[..., Awaitable[str | bytes | None]]
    ):
        """设置 HTML 渲染函数 (运行时注入)"""
        self._html_render_func = render_func

    def _is_qq_official(self, platform_id: str | None) -> bool:
        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        return bool(adapter and adapter.get_platform_name() == "qq_official")

    # 复用多平台通用 Markdown 结构化排版的平台（如 Telegram、Discord、Satori）：
    # 身份自动降级为昵称文本，排版与结构化报告一致。
    _SHARED_MARKDOWN_PLATFORMS = frozenset({"telegram", "discord", "satori"})

    def _uses_shared_markdown_report(self, platform_id: str | None) -> bool:
        """平台是否复用 QQ 官方的 Markdown 文本排版。"""
        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        return bool(
            adapter and adapter.get_platform_name() in self._SHARED_MARKDOWN_PLATFORMS
        )

    async def dispatch(
        self,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        platform_id: str | None = None,
        *,
        output_formats: Sequence[str] | None = None,
    ) -> bool:
        """分发分析报告，允许入口保留其原有的格式选择范围。

        Args:
            group_id: 目标群号。
            analysis_result: 同一次分析的完整结果。
            platform_id: 平台实例标识。
            output_formats: 本次发送的格式；未指定时使用全部已配置格式。

        Returns:
            至少一种报告格式是否实际发送成功。
        """
        if output_formats is None:
            output_formats = self.config_manager.get_output_format()
        if isinstance(output_formats, str):
            output_formats = [output_formats]

        if self.merged_delivery and self.merged_delivery.enabled_for(platform_id):
            return await self._dispatch_merged(
                group_id, analysis_result, platform_id, output_formats
            )

        sent_any = await self._dispatch_report_formats(
            group_id, analysis_result, platform_id, output_formats
        )
        if sent_any and self.wordcloud_delivery:
            adapter = self.message_sender.bot_manager.get_adapter(platform_id)
            resolved_platform = platform_id or (adapter.platform_id if adapter else "")
            await self.wordcloud_delivery.send_with_report(
                analysis_result.get("wordcloud"), group_id, resolved_platform
            )
        return sent_any

    async def _dispatch_report_formats(
        self,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        platform_id: str | None,
        output_formats: Sequence[str],
    ) -> bool:
        """沿用普通报告各格式的生成、文件发送和回退方式。

        Args:
            group_id: 目标群号。
            analysis_result: 同一次分析的完整结果。
            platform_id: 平台实例标识。
            output_formats: 本次请求的报告格式。

        Returns:
            至少一种报告格式是否发送成功。
        """
        trace_id = TraceContext.get()
        logger.info(
            f"[{trace_id}] 正在分发群 {group_id} 的报告 (格式: {', '.join(output_formats)})"
        )

        dispatch_map = {
            "image": self._dispatch_image,
            "html": self._dispatch_html,
            "text": self._dispatch_text,
        }
        sent_any = False
        for fmt in output_formats:
            handler = dispatch_map.get(fmt)
            if not handler:
                logger.warning(f"[{trace_id}] 不支持的报告格式: {fmt}")
                continue
            try:
                ok = bool(await handler(group_id, analysis_result, platform_id))
                sent_any = ok or sent_any
            except Exception as e:
                logger.error(
                    f"[{trace_id}] 群 {group_id} 的 {fmt} 报告发送异常: {e}",
                    exc_info=True,
                )

        if sent_any:
            logger.info(
                f"[{trace_id}] 群 {group_id} 的报告分发完成，至少一种格式发送成功"
            )
        else:
            logger.error(f"[{trace_id}] 群 {group_id} 的报告分发失败，未发送任何报告")
        return sent_any

    async def _dispatch_merged(
        self,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        platform_id: str | None,
        output_formats: Sequence[str],
    ) -> bool:
        """只合并选中的结果，并行启动未选中结果的普通发送。

        Args:
            group_id: 目标群号。
            analysis_result: 同一次分析的完整结果。
            platform_id: 平台实例标识。
            output_formats: 本次请求的报告格式。

        Returns:
            报告是否通过其配置的发送方式至少成功发送一种格式。

        Raises:
            asyncio.CancelledError: 上层任务取消，停止本次尚未完成的投递。
        """
        if not self.merged_delivery:
            return False
        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        resolved_platform = platform_id or (adapter.platform_id if adapter else "")
        producers: dict[str, Callable[[], Awaitable[list[PreparedForwardMessage]]]] = {}
        ordinary_tasks: dict[str, asyncio.Task[bool]] = {}
        merge_report = self.merged_delivery.enabled_for(platform_id, "report")
        if merge_report:
            for fmt in output_formats:
                if fmt not in {"image", "html", "text"}:
                    logger.warning(f"不支持的合并报告格式：{fmt}")
                    continue
                # 每种格式独立交给总超时管理，慢图片不能吞掉已完成的文本。
                producers[f"report:{fmt}"] = partial(
                    self.prepare_report, fmt, group_id, analysis_result, platform_id
                )
        else:
            ordinary_tasks["report"] = asyncio.create_task(
                self._dispatch_report_formats(
                    group_id, analysis_result, platform_id, output_formats
                )
            )
        if self.wordcloud_delivery:
            if self.merged_delivery.enabled_for(platform_id, "wordcloud"):
                producers["wordcloud"] = partial(
                    self.wordcloud_delivery.prepare_for_report,
                    analysis_result.get("wordcloud"),
                    group_id,
                    resolved_platform,
                )
            else:
                ordinary_tasks["wordcloud"] = asyncio.create_task(
                    self.wordcloud_delivery.send_with_report(
                        analysis_result.get("wordcloud"), group_id, resolved_platform
                    )
                )
        if self.comic_handler:
            if self.merged_delivery.enabled_for(platform_id, "comic"):
                producers["comic"] = partial(
                    self.comic_handler.prepare_for_report,
                    group_id,
                    platform_id,
                    analysis_result,
                )
            else:
                # 普通漫画继续使用后台生成入口，不占用合并收集的等待期限。
                try:
                    self.comic_handler.try_trigger_comic_generation(
                        group_id, platform_id, analysis_result
                    )
                except Exception as exc:
                    logger.warning(f"群 {group_id} 普通漫画启动失败：{exc}")
        trace = TraceContext.current()
        with (
            trace.span(
                AnalysisStage.DISPATCH_REPORT,
                {
                    "platform": platform_id or "auto",
                    "group_id": group_id,
                    "formats": list(output_formats),
                    "transmission_mode": "merged_forward",
                },
            )
            if trace
            else nullcontext()
        ) as dispatch_span:
            merged_task = asyncio.create_task(
                self.merged_delivery.deliver(group_id, platform_id, producers)
            )
            ordinary_sent: set[str] = set()
            try:
                if ordinary_tasks:
                    done, pending = await asyncio.wait(
                        ordinary_tasks.values(),
                        timeout=self._ORDINARY_DELIVERY_TIMEOUT_SECONDS,
                    )
                    for task in pending:
                        task.cancel()
                    if pending:
                        logger.warning(
                            f"群 {group_id} 普通结果投递超时，合并结果继续独立发送"
                        )
                        await asyncio.wait(pending, timeout=1.0)
                    for kind, task in ordinary_tasks.items():
                        if task not in done or task.cancelled():
                            continue
                        try:
                            if task.result():
                                ordinary_sent.add(kind)
                        except Exception as exc:
                            logger.warning(f"群 {group_id} 普通 {kind} 投递失败：{exc}")
                try:
                    delivered = await merged_task
                except Exception as exc:
                    logger.warning(f"群 {group_id} 合并结果投递失败：{exc}")
                    delivered = set()
            finally:
                unfinished = {
                    task
                    for task in (merged_task, *ordinary_tasks.values())
                    if not task.done()
                }
                for task in (merged_task, *ordinary_tasks.values()):
                    if task in unfinished:
                        task.cancel()
                    # 外层取消时也消费已经失败的兄弟任务，避免未读取异常。
                    task.add_done_callback(
                        lambda completed: (
                            None if completed.cancelled() else completed.exception()
                        )
                    )
                if unfinished:
                    await asyncio.wait(unfinished, timeout=1.0)
            report_sent = "report" in (delivered if merge_report else ordinary_sent)
            if dispatch_span:
                dispatch_span["payload"].update(
                    {
                        "success": report_sent,
                        "merged_sent_kinds": sorted(delivered),
                        "ordinary_sent_kinds": sorted(ordinary_sent),
                    }
                )
                if not report_sent:
                    dispatch_span["status"] = "warning"
        return report_sent

    async def prepare_report(
        self,
        fmt: str,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        platform_id: str | None,
    ) -> list[PreparedForwardMessage]:
        """仅准备报告节点及历史副本，平台发送由合并服务统一执行。

        Args:
            fmt: 图片、HTML 或文本报告格式。
            group_id: 目标群号。
            analysis_result: 本次分析结果。
            platform_id: 平台实例标识。

        Returns:
            已准备的报告节点；生成失败时尝试返回文本报告。
        """
        generator = self.report_generator
        if generator is None:
            logger.error("报告生成器未初始化，无法准备合并报告")
            return []
        trace = TraceContext.current()
        if fmt in {"image", "html"}:
            try:
                if fmt == "image" and not self._html_render_func:
                    raise RuntimeError("未设置 HTML 渲染函数")

                async def avatar_url_getter(
                    user_id: str, size: int | None = None
                ) -> str | None:
                    if not platform_id:
                        return None
                    adapter = self.message_sender.bot_manager.get_adapter(platform_id)
                    return (
                        await adapter.get_user_avatar_url(user_id, size=size or 40)
                        if adapter
                        else None
                    )

                override_theme = (
                    str(trace.metadata.get("override_template_name") or "").strip()
                    if trace
                    else ""
                )
                template_theme = (
                    override_theme
                    or self.config_manager.get_report_template()
                    or "scrapbook"
                )
                with (
                    trace.span(
                        AnalysisStage.RENDER_REPORT,
                        {"format": fmt, "template": template_theme},
                    )
                    if trace
                    else nullcontext()
                ):
                    if fmt == "image":
                        image_url, _ = await generator.generate_image_report(
                            analysis_result,
                            group_id,
                            self._html_render_func,
                            avatar_url_getter=avatar_url_getter,
                            avatar_cache_namespace=platform_id,
                            allow_alphanumeric_user_ids=self._is_qq_official(
                                platform_id
                            ),
                            template_theme=template_theme,
                        )
                        if not image_url:
                            raise RuntimeError("报告图片生成未返回有效图片")
                        self._preserve_prepared_report(image_url, "image", group_id)
                        caption = (
                            TraceContext.make_report_caption()
                            if self.config_manager.get_show_report_caption()
                            else ""
                        )

                        async def after_send() -> None:
                            await self._try_upload_image(
                                group_id, image_url, platform_id
                            )

                        return [
                            PreparedForwardMessage(
                                kind="report",
                                text=caption,
                                image_url=image_url,
                                after_send=after_send,
                            )
                        ]
                    html_path, _ = await generator.generate_html_report(
                        analysis_result,
                        group_id,
                        avatar_url_getter=avatar_url_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=self._is_qq_official(platform_id),
                        template_theme=template_theme,
                        trace_id=TraceContext.get(),
                    )
                    if not html_path:
                        raise RuntimeError("HTML 报告生成未返回有效文件")
                    self._preserve_prepared_report(html_path, "html", group_id)
                    base_url = self.config_manager.get_html_base_url()
                    if self.config_manager.get_html_only_url() and base_url.strip():
                        output_dir = self.config_manager.get_html_output_dir() or str(
                            generator.data_dir / "self_hosted_html_reports"
                        )
                        relative_path = os.path.relpath(html_path, output_dir)
                        url_path = relative_path.replace(os.sep, "/")
                        encoded_path = quote(url_path.lstrip("/"), safe="/")
                        return [
                            PreparedForwardMessage(
                                kind="report",
                                text=(
                                    "📊 今日群聊分析报告已生成：\n"
                                    f"{base_url.rstrip('/')}/{encoded_path}"
                                ),
                            )
                        ]
                    # 合并节点只使用跨 OneBot 实现兼容的文字及图片，HTML 留在历史中。
                    logger.info("HTML 报告已保存，合并转发节点使用文本报告内容")
            except Exception as exc:
                logger.warning(f"群 {group_id} 的 {fmt} 报告准备失败，尝试文本：{exc}")
        elif fmt != "text":
            logger.warning(f"不支持的合并报告格式：{fmt}")
            return []
        try:
            if self._is_qq_official(platform_id):
                text_report, _ = await generator.generate_markdown_report(
                    analysis_result, self._html_render_func, mention_style="qq"
                )
            elif self._uses_shared_markdown_report(platform_id):
                text_report, _ = await generator.generate_markdown_report(
                    analysis_result, mention_style="name"
                )
            else:
                text_report = generator.generate_text_report(analysis_result)
            return [
                PreparedForwardMessage(
                    kind="report", text=f"📊 每日群聊分析报告：\n\n{text_report}"
                )
            ]
        except Exception as exc:
            logger.error(f"群 {group_id} 的合并文本报告准备失败：{exc}", exc_info=True)
            return []

    def _preserve_prepared_report(self, source: str, fmt: str, group_id: str) -> None:
        """保存已准备报告，并沿用报告文件与追踪元数据格式。

        Args:
            source: 已生成图片的数据或 HTML 文件路径。
            fmt: 报告格式。
            group_id: 报告所属群号。
        """
        generator = self.report_generator
        if generator is None:
            return
        trace = TraceContext.current()
        try:
            if fmt == "image":
                reports_dir = generator.data_dir / "reports"
                reports_dir.mkdir(parents=True, exist_ok=True)
                trace_id = TraceContext.get() or (trace.trace_id if trace else "")
                suffix = f"_{trace_id}" if trace_id else ""
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = reports_dir / f"report_{group_id}_{timestamp}{suffix}.jpg"
                if os.path.exists(source):
                    import shutil

                    shutil.copy2(source, path)
                elif source.startswith("base64://"):
                    path.write_bytes(base64.b64decode(source[9:]))
                else:
                    return
            else:
                path = Path(source)
            if trace:
                files = trace.metadata.setdefault("report_files", [])
                if isinstance(files, list) and not any(
                    isinstance(item, dict) and item.get("filename") == path.name
                    for item in files
                ):
                    files.append(
                        {
                            "filename": path.name,
                            "path": str(path.resolve()),
                            "format": fmt,
                            "size_bytes": path.stat().st_size if path.exists() else 0,
                            "created_at": time.time(),
                        }
                    )
                from ...shared.trace_context import _global_trace_store

                if _global_trace_store is not None:
                    _global_trace_store.save_trace(trace.to_dict())
        except Exception as exc:
            logger.warning(f"群 {group_id} 的 {fmt} 报告历史保存失败：{exc}")

    async def _dispatch_image(
        self,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        platform_id: str | None,
    ) -> bool:
        trace_id = TraceContext.get()
        trace_ctx = TraceContext.current()
        if not self.report_generator:
            logger.error(f"[{trace_id}] 报告生成器未初始化，无法生成图片报告。")
            return False

        # 1. 检查渲染函数
        if not self._html_render_func:
            logger.warning(f"[{trace_id}] 未设置 HTML 渲染函数，回退到文本模式。")
            return await self._dispatch_text(group_id, analysis_result, platform_id)

        # 2. 生成图片
        image_url = None
        try:
            # 定义头像获取回调，请求小尺寸头像以优化性能
            async def avatar_url_getter(
                user_id: str, size: int | None = None
            ) -> str | None:
                if not platform_id:
                    return None
                adapter = self.message_sender.bot_manager.get_adapter(platform_id)
                if adapter:
                    return await adapter.get_user_avatar_url(user_id, size=size or 40)
                return None

            trace = TraceContext.current()
            override_theme = (
                str(trace.metadata.get("override_template_name") or "").strip()
                if trace
                else ""
            )
            template_theme: str = (
                override_theme
                or self.config_manager.get_report_template()
                or "scrapbook"
            )

            if trace:
                with trace.span(
                    AnalysisStage.RENDER_REPORT,
                    {"format": "image", "template": template_theme},
                ):
                    (
                        image_url,
                        _html_content,
                    ) = await self.report_generator.generate_image_report(
                        analysis_result,
                        group_id,
                        self._html_render_func,
                        avatar_url_getter=avatar_url_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=self._is_qq_official(platform_id),
                        template_theme=template_theme,
                    )
            else:
                (
                    image_url,
                    _html_content,
                ) = await self.report_generator.generate_image_report(
                    analysis_result,
                    group_id,
                    self._html_render_func,
                    avatar_url_getter=avatar_url_getter,
                    avatar_cache_namespace=platform_id,
                    allow_alphanumeric_user_ids=self._is_qq_official(platform_id),
                    template_theme=template_theme,
                )
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to generate image report: {e}")
            # image_url and html_content remain None

        # 渲染器可能吞掉取消信号，已超时的普通报告不得继续发送迟到结果。
        current_task = asyncio.current_task()
        if current_task and current_task.cancelling():
            raise asyncio.CancelledError

        # 4. 发送图片
        sent = False
        dest_filename: str | None = None
        if image_url:
            with (
                trace_ctx.span(
                    AnalysisStage.DISPATCH_REPORT,
                    {
                        "platform": platform_id or "auto",
                        "group_id": group_id,
                        "formats": ["image"],
                        "format": "image",
                    },
                )
                if trace_ctx
                else nullcontext()
            ) as dispatch_span:
                try:
                    reports_dir = self.report_generator.data_dir / "reports"
                    reports_dir.mkdir(parents=True, exist_ok=True)
                    eff_trace_id = (
                        trace_id
                        or (trace_ctx.trace_id if trace_ctx else "")
                        or TraceContext.get()
                        or ""
                    )
                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = (
                        f"report_{group_id}_{ts_str}_{eff_trace_id}.jpg"
                        if eff_trace_id
                        else f"report_{group_id}_{ts_str}.jpg"
                    )
                    dest = reports_dir / filename
                    dest_filename = dest.name
                    if os.path.exists(image_url):
                        import shutil

                        shutil.copy2(image_url, dest)
                    elif image_url.startswith("base64://"):
                        data = base64.b64decode(image_url[9:])
                        dest.write_bytes(data)

                    # 关联到 TraceContext 并在数据库中更新元数据
                    if trace_ctx:
                        rfiles = trace_ctx.metadata.setdefault("report_files", [])
                        if isinstance(rfiles, list) and not any(
                            isinstance(rf, dict) and rf.get("filename") == dest.name
                            for rf in rfiles
                        ):
                            rfiles.append(
                                {
                                    "filename": dest.name,
                                    "path": str(dest.resolve()),
                                    "format": "image",
                                    "size_bytes": dest.stat().st_size
                                    if dest.exists()
                                    else 0,
                                    "created_at": time.time(),
                                }
                            )
                        from ...shared.trace_context import _global_trace_store

                        if _global_trace_store is not None:
                            try:
                                _global_trace_store.save_trace(trace_ctx.to_dict())
                            except Exception:
                                pass
                except Exception as e:
                    logger.warning(f"[{trace_id}] 保存历史报告副本失败: {e}")

                caption = (
                    TraceContext.make_report_caption()
                    if self.config_manager.get_show_report_caption()
                    else ""
                )
                is_b64 = image_url.startswith("base64://")
                raw_image_kb = 0.0
                base64_payload_kb = 0.0
                bloat_ratio = None
                if is_b64:
                    b64_str = image_url[9:]
                    b64_len = len(b64_str)
                    base64_payload_kb = round(b64_len / 1024, 2)
                    padding = b64_str.count("=", max(0, b64_len - 2))
                    raw_bytes_len = max(0, (b64_len * 3 // 4) - padding)
                    raw_image_kb = round(raw_bytes_len / 1024, 2)
                    bloat_pct = round(
                        ((b64_len - raw_bytes_len) / max(raw_bytes_len, 1)) * 100, 1
                    )
                    bloat_ratio = f"+{bloat_pct}%"
                elif os.path.exists(image_url):
                    raw_image_kb = round(os.path.getsize(image_url) / 1024, 2)

                dispatch_start_ts = time.perf_counter()
                try:
                    sent = await self.message_sender.send_image_smart(
                        group_id, image_url, caption, platform_id
                    )
                except Exception as e:
                    logger.error(f"[{trace_id}] 图片报告发送异常: {e}", exc_info=True)
                dispatch_api_ms = round(
                    (time.perf_counter() - dispatch_start_ts) * 1000, 2
                )

                # 5. 尝试上传到群文件/群相册（静默处理）
                try:
                    await self._try_upload_image(group_id, image_url, platform_id)
                except Exception as e:
                    logger.warning(
                        f"[{trace_id}] 图片报告备份失败，不影响发送状态: {e}"
                    )

                if dispatch_span:
                    dispatch_span.setdefault("payload", {}).update(
                        {
                            "platform": platform_id or "auto",
                            "formats": ["image"],
                            "format": "image",
                            "transmission_mode": "base64" if is_b64 else "file_path",
                            "raw_image_kb": raw_image_kb,
                            "base64_payload_kb": base64_payload_kb,
                            "bloat_ratio": bloat_ratio,
                            "dispatch_api_ms": dispatch_api_ms,
                            "success": bool(sent),
                            "image_sent": bool(sent),
                            "report_file": dest_filename,
                        }
                    )
                    if not sent:
                        dispatch_span["status"] = "warning"
                        dispatch_span["payload"]["warning"] = (
                            "图片报告发送失败，已自动降级回退至文本报告"
                        )
                        if trace_ctx:
                            trace_ctx.metadata["has_warnings"] = True

        if sent:
            return True

        # 6. 最终回退：如果图片发送失败（包括生成失败或发送接口报错），直接尝试发送文本报告
        logger.warning(
            f"[{trace_id}] Image dispatch failed, falling back to text report."
        )
        return await self._dispatch_text(group_id, analysis_result, platform_id)

    async def _dispatch_html(
        self,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        platform_id: str | None,
    ) -> bool:
        trace_id = TraceContext.get()
        trace_ctx = TraceContext.current()
        if not self.report_generator:
            logger.error(f"[{trace_id}] 报告生成器未初始化，无法生成 HTML 报告。")
            return False

        html_path = None
        try:

            async def avatar_url_getter(
                user_id: str, size: int | None = None
            ) -> str | None:
                if not platform_id:
                    return None
                adapter = self.message_sender.bot_manager.get_adapter(platform_id)
                if adapter:
                    return await adapter.get_user_avatar_url(user_id, size=size or 40)
                return None

            trace = TraceContext.current()
            override_theme = (
                str(trace.metadata.get("override_template_name") or "").strip()
                if trace
                else ""
            )
            template_theme: str = (
                override_theme
                or self.config_manager.get_report_template()
                or "scrapbook"
            )

            if trace:
                with trace.span(
                    AnalysisStage.RENDER_REPORT,
                    {"format": "html", "template": template_theme},
                ):
                    (
                        html_path,
                        _json_path,
                    ) = await self.report_generator.generate_html_report(
                        analysis_result,
                        group_id,
                        avatar_url_getter=avatar_url_getter,
                        avatar_cache_namespace=platform_id,
                        allow_alphanumeric_user_ids=self._is_qq_official(platform_id),
                        template_theme=template_theme,
                        trace_id=trace_id,
                    )
            else:
                (
                    html_path,
                    _json_path,
                ) = await self.report_generator.generate_html_report(
                    analysis_result,
                    group_id,
                    avatar_url_getter=avatar_url_getter,
                    avatar_cache_namespace=platform_id,
                    allow_alphanumeric_user_ids=self._is_qq_official(platform_id),
                    template_theme=template_theme,
                    trace_id=trace_id,
                )
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to generate HTML report: {e}")

        current_task = asyncio.current_task()
        if current_task and current_task.cancelling():
            raise asyncio.CancelledError

        html_filename: str | None = None
        sent = False
        if html_path:
            with (
                trace_ctx.span(
                    AnalysisStage.DISPATCH_REPORT,
                    {
                        "platform": platform_id or "auto",
                        "group_id": group_id,
                        "formats": ["html"],
                        "format": "html",
                    },
                )
                if trace_ctx
                else nullcontext()
            ) as dispatch_span:
                try:
                    html_file = Path(html_path)
                    html_filename = html_file.name
                    if trace_ctx:
                        rfiles = trace_ctx.metadata.setdefault("report_files", [])
                        if isinstance(rfiles, list) and not any(
                            isinstance(rf, dict)
                            and rf.get("filename") == html_file.name
                            for rf in rfiles
                        ):
                            rfiles.append(
                                {
                                    "filename": html_file.name,
                                    "path": str(html_file.resolve()),
                                    "format": "html",
                                    "size_bytes": html_file.stat().st_size
                                    if html_file.exists()
                                    else 0,
                                    "created_at": time.time(),
                                }
                            )
                        from ...shared.trace_context import _global_trace_store

                        if _global_trace_store is not None:
                            try:
                                _global_trace_store.save_trace(trace_ctx.to_dict())
                            except Exception:
                                pass
                except Exception as e:
                    logger.warning(f"[{trace_id}] 关联 HTML 报告元数据失败: {e}")

                is_only_url = self.config_manager.get_html_only_url()
                base_url = self.config_manager.get_html_base_url()

                if is_only_url:
                    if base_url and base_url.strip():
                        # 获取配置的目录
                        html_output_dir = self.config_manager.get_html_output_dir()

                        # 若用户配置为空，使用默认目录
                        if not html_output_dir:
                            html_output_dir = str(
                                self.report_generator.data_dir
                                / "self_hosted_html_reports"
                            )

                        # 计算相对路径并转换为URL
                        rel_path = os.path.relpath(html_path, html_output_dir)
                        url_path = rel_path.replace(os.sep, "/")
                        encoded_url_path = quote(url_path.lstrip("/"), safe="/")
                        report_url = f"{base_url.rstrip('/')}/{encoded_url_path}"

                        sent = await self.message_sender.send_text(
                            group_id,
                            f"📊 今日群聊分析报告已生成：\n{report_url}",
                            platform_id,
                        )
                    else:
                        logger.warning(
                            f"[{trace_id}] 群 {group_id} 开启了仅发送外链，但未配置 html_base_url，已进行降级，回退至发送 HTML 文件。"
                        )

                if not sent:
                    caption = (
                        self.report_generator.build_html_caption(html_path)
                        if self.config_manager.get_show_report_caption()
                        else ""
                    )
                    sent = await self.message_sender.send_file(
                        group_id,
                        html_path,
                        caption=caption,
                        platform_id=platform_id,
                    )

                if dispatch_span:
                    dispatch_span.setdefault("payload", {}).update(
                        {
                            "platform": platform_id or "auto",
                            "formats": ["html"],
                            "format": "html",
                            "success": bool(sent),
                            "html_sent": bool(sent),
                            "html_file": html_filename,
                        }
                    )
                    if not sent:
                        dispatch_span["status"] = "warning"
                        dispatch_span["payload"]["warning"] = (
                            "HTML 报告发送失败，已自动降级回退至文本报告"
                        )
                        if trace_ctx:
                            trace_ctx.metadata["has_warnings"] = True

                if sent:
                    return True

        logger.warning(
            f"[{trace_id}] HTML dispatch failed, falling back to text report."
        )
        return await self._dispatch_text(group_id, analysis_result, platform_id)

    async def _dispatch_text(
        self,
        group_id: str,
        analysis_result: AnalysisResultPayload,
        platform_id: str | None,
    ) -> bool:
        """分发文本报告"""
        logger.info(f"[分发器] 正在向群组 {group_id} 分发文本报告")
        trace_ctx = TraceContext.current()
        if not self.report_generator:
            logger.error("[分发器] 报告生成器未初始化，无法生成文本报告。")
            return False
        is_qq_official = self._is_qq_official(platform_id)
        fallback_report = None
        if is_qq_official:
            (
                text_report,
                fallback_report,
            ) = await self.report_generator.generate_markdown_report(
                analysis_result, self._html_render_func, mention_style="qq"
            )
        elif self._uses_shared_markdown_report(platform_id):
            # 支持富文本 Markdown 但无 QQ @ 提及能力的平台（如 Telegram / Discord）走通用 Markdown 排版（身份降级为昵称）
            (
                text_report,
                _,
            ) = await self.report_generator.generate_markdown_report(
                analysis_result, mention_style="name"
            )
        else:
            text_report = self.report_generator.generate_text_report(analysis_result)
        current_task = asyncio.current_task()
        if current_task and current_task.cancelling():
            raise asyncio.CancelledError
        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        # 尝试通过适配器发送文本报告
        logger.info(f"[分发器] 正在尝试通过适配器发送文本报告。群: {group_id}")

        with (
            trace_ctx.span(
                AnalysisStage.DISPATCH_REPORT,
                {
                    "platform": platform_id or "auto",
                    "group_id": group_id,
                    "formats": ["text"],
                    "format": "text",
                },
            )
            if trace_ctx
            else nullcontext()
        ) as dispatch_span:
            sent = False
            try:
                if adapter:
                    if is_qq_official:
                        sent = bool(
                            await adapter.send_text_report(
                                group_id,
                                text_report,
                                fallback_content=fallback_report,
                            )
                        )
                    else:
                        sent = bool(
                            await adapter.send_text_report(group_id, text_report)
                        )
                if not sent:
                    sent = bool(
                        await self.message_sender.send_text(
                            group_id,
                            f"📊 每日群聊分析报告：\n\n{text_report}",
                            platform_id,
                        )
                    )
            except Exception as e:
                logger.error(
                    f"[分发器] 发送文本报告最终失败。群: {group_id}, 错误: {e}"
                )
                sent = False

            if dispatch_span:
                dispatch_span.setdefault("payload", {}).update(
                    {
                        "platform": platform_id or "auto",
                        "formats": ["text"],
                        "format": "text",
                        "success": bool(sent),
                        "text_sent": bool(sent),
                    }
                )
            return sent

    # ================================================================
    # 图片报告上传到群文件 / 群相册（仅 QQ 平台 image 格式）
    # ================================================================

    async def _try_upload_image(
        self,
        group_id: str,
        image_url: str,
        platform_id: str | None,
    ):
        """
        尝试将图片报告上传到群文件和/或群相册。

        仅在配置启用且平台为 OneBot 时执行，失败静默处理。
        """
        enable_file = self.config_manager.get_enable_group_file_upload()
        enable_album = self.config_manager.get_enable_group_album_upload()
        if not enable_file and not enable_album:
            return

        # 仅 OneBot 平台支持
        adapter = self._get_onebot_adapter(platform_id)
        if not adapter:
            return

        # 将图片保存为临时文件
        image_file = self._save_image_to_temp(image_url, group_id)
        if not image_file:
            return

        try:
            # 上传到群文件
            if enable_file:
                await self._do_upload_group_file(adapter, group_id, image_file)

            # 上传到群相册
            if enable_album:
                await self._do_upload_group_album(adapter, group_id, image_file)
        finally:
            try:
                os.remove(image_file)
            except OSError:
                pass

    async def _do_upload_group_file(
        self,
        adapter: GroupFileSupportProtocol | OneBotAdapter,
        group_id: str,
        file_path: str,
    ) -> None:
        """上传文件到群文件目录，失败静默"""
        try:
            folder_name = self.config_manager.get_group_file_folder()
            folder_id = None
            if folder_name:
                folder_id = await adapter.find_or_create_folder(group_id, folder_name)
            await adapter.upload_group_file_to_folder(
                group_id=group_id,
                file_path=file_path,
                folder_id=folder_id,
            )
        except Exception as e:
            logger.warning(f"群文件上传失败 (群 {group_id}): {e}")

    async def _do_upload_group_album(
        self,
        adapter: GroupAlbumSupportProtocol | OneBotAdapter,
        group_id: str,
        file_path: str,
    ) -> None:
        """上传图片到群相册，失败静默"""
        try:
            album_name = self.config_manager.get_group_album_name()
            strict_mode = self.config_manager.get_group_album_strict_mode()
            album_id = None

            if album_name:
                album_id = await adapter.find_album_id(group_id, album_name)
                if not album_id and strict_mode:
                    logger.info(
                        f"群相册严格模式开启：在群 {group_id} 中未找到名为 '{album_name}' 的相册，停止上传。"
                    )
                    return
            elif strict_mode:
                logger.info(
                    f"群相册严格模式开启：未设置目标相册名称，停止上传以防止操作群 {group_id} 的默认相册。"
                )
                return

            await adapter.upload_group_album(
                group_id,
                file_path,
                album_id=album_id,
                album_name=album_name,
                strict_mode=strict_mode,
            )
        except Exception as e:
            logger.warning(f"群相册上传失败 (群 {group_id}): {e}")

    def _save_image_to_temp(self, image_url: str, group_id: str) -> str | None:
        """将 base64 图片保存为临时 PNG 文件，返回路径。失败返回 None。"""
        try:
            image_data = None
            if image_url.startswith("base64://"):
                image_data = base64.b64decode(image_url[len("base64://") :])
            elif image_url.startswith("data:"):
                parts = image_url.split(",", 1)
                if len(parts) == 2:
                    image_data = base64.b64decode(parts[1])
            elif os.path.isfile(image_url):
                return os.path.abspath(image_url)
            elif image_url.startswith("file:///"):
                p = image_url[len("file:///") :]
                if os.path.isfile(p):
                    return os.path.abspath(p)

            if not image_data:
                return None

            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(
                tempfile.gettempdir(), f"report_{group_id}_{date_str}.png"
            )
            with open(path, "wb") as f:
                f.write(image_data)
            return path
        except Exception as e:
            logger.debug(f"保存图片到临时文件失败: {e}")
            return None

    def _get_onebot_adapter(self, platform_id: str | None) -> OneBotAdapter | None:
        """获取 OneBot 适配器，非 OneBot 平台返回 None。"""
        if not platform_id:
            return None
        from ..platform.adapters.onebot_adapter import OneBotAdapter

        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        if isinstance(adapter, OneBotAdapter):
            return adapter
        return None
