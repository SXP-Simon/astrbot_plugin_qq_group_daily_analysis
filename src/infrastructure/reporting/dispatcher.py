import base64
import os
import tempfile
import time
from collections.abc import Callable
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ...shared.trace_context import TraceContext
from ...utils.logger import logger


class ReportDispatcher:
    """
    报告分发器
    负责协调报告生成、格式选择、消息发送和失败重试
    """

    def __init__(
        self,
        config_manager,
        report_generator,
        message_sender,
    ):
        self.config_manager = config_manager
        self.report_generator = report_generator
        self.message_sender = message_sender
        self._html_render_func: Callable | None = None

    def set_html_render(self, render_func: Callable):
        """设置 HTML 渲染函数 (运行时注入)"""
        self._html_render_func = render_func

    def _is_qq_official(self, platform_id: str | None) -> bool:
        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        return bool(adapter and adapter.get_platform_name() == "qq_official")

    async def dispatch(
        self,
        group_id: str,
        analysis_result: dict[str, Any],
        platform_id: str | None = None,
    ) -> bool:
        """分发分析报告，并返回至少一种格式是否实际发送成功。"""
        trace_id = TraceContext.get()
        output_formats = self.config_manager.get_output_format()
        if isinstance(output_formats, str):
            output_formats = [output_formats]

        logger.info(
            f"[{trace_id}] 正在分发群 {group_id} 的报告 (格式: {', '.join(output_formats)})"
        )

        dispatch_map = {
            "image": self._dispatch_image,
            "html": self._dispatch_html,
            "text": self._dispatch_text,
        }
        sent_any = False
        format_results: dict[str, bool] = {}

        for fmt in output_formats:
            handler = dispatch_map.get(fmt)
            if not handler:
                logger.warning(f"[{trace_id}] 不支持的报告格式: {fmt}")
                continue
            try:
                ok = bool(await handler(group_id, analysis_result, platform_id))
                format_results[fmt] = ok
                sent_any = ok or sent_any
            except Exception as e:
                logger.error(
                    f"[{trace_id}] 群 {group_id} 的 {fmt} 报告发送异常: {e}",
                    exc_info=True,
                )
                format_results[fmt] = False

        if sent_any:
            logger.info(
                f"[{trace_id}] 群 {group_id} 的报告分发完成，至少一种格式发送成功"
            )
        else:
            logger.error(f"[{trace_id}] 群 {group_id} 的报告分发失败，未发送任何报告")
        return sent_any

    async def _dispatch_image(
        self, group_id: str, analysis_result: dict[str, Any], platform_id: str | None
    ) -> bool:
        trace_id = TraceContext.get()
        trace_ctx = TraceContext.current()
        # 1. 检查渲染函数
        if not self._html_render_func:
            logger.warning(f"[{trace_id}] 未设置 HTML 渲染函数，回退到文本模式。")
            return await self._dispatch_text(group_id, analysis_result, platform_id)

        # 2. 生成图片
        image_url = None
        html_content = None
        try:
            # 定义头像获取回调，请求小尺寸头像以优化性能
            async def avatar_url_getter(user_id: str):
                if not platform_id:
                    return None
                adapter = self.message_sender.bot_manager.get_adapter(platform_id)
                if adapter and hasattr(adapter, "get_user_avatar_url"):
                    return await adapter.get_user_avatar_url(user_id, size=40)
                return None

            trace = TraceContext.current()
            override_theme = (
                trace.metadata.get("override_template_name") if trace else None
            )
            template_theme = (
                override_theme
                or getattr(
                    self.config_manager, "get_report_template", lambda: "scrapbook"
                )()
            )

            if trace:
                with trace.span(
                    "RENDER_REPORT",
                    {"format": "image", "template": template_theme},
                ):
                    (
                        image_url,
                        html_content,
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
                    html_content,
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

        # 4. 发送图片
        sent = False
        dest_filename: str | None = None
        if image_url:
            with (
                trace_ctx.span(
                    "DISPATCH_REPORT",
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
                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = (
                        f"report_{group_id}_{ts_str}_{trace_id}.jpg"
                        if trace_id
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
                        if not any(rf.get("filename") == dest.name for rf in rfiles):
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
                try:
                    sent = await self.message_sender.send_image_smart(
                        group_id, image_url, caption, platform_id
                    )
                except Exception as e:
                    logger.error(f"[{trace_id}] 图片报告发送异常: {e}", exc_info=True)

                # 5. 尝试上传到群文件/群相册（静默处理）
                try:
                    await self._try_upload_image(group_id, image_url, platform_id)
                except Exception as e:
                    logger.warning(
                        f"[{trace_id}] 图片报告备份失败，不影响发送状态: {e}"
                    )

                if dispatch_span and isinstance(dispatch_span, dict):
                    dispatch_span.setdefault("payload", {}).update(
                        {
                            "platform": platform_id or "auto",
                            "formats": ["image"],
                            "format": "image",
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
        self, group_id: str, analysis_result: dict[str, Any], platform_id: str | None
    ) -> bool:
        trace_id = TraceContext.get()
        trace_ctx = TraceContext.current()

        html_path = None
        try:

            async def avatar_url_getter(user_id: str):
                if not platform_id:
                    return None
                adapter = self.message_sender.bot_manager.get_adapter(platform_id)
                if adapter and hasattr(adapter, "get_user_avatar_url"):
                    return await adapter.get_user_avatar_url(user_id, size=40)
                return None

            trace = TraceContext.current()
            override_theme = (
                trace.metadata.get("override_template_name") if trace else None
            )
            template_theme = (
                override_theme
                or getattr(
                    self.config_manager, "get_report_template", lambda: "scrapbook"
                )()
            )

            if trace:
                with trace.span(
                    "RENDER_REPORT",
                    {"format": "html", "template": template_theme},
                ):
                    (
                        html_path,
                        json_path,
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
                html_path, json_path = await self.report_generator.generate_html_report(
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

        html_filename: str | None = None
        sent = False
        if html_path:
            with (
                trace_ctx.span(
                    "DISPATCH_REPORT",
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
                        if not any(
                            rf.get("filename") == html_file.name for rf in rfiles
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

                if dispatch_span and isinstance(dispatch_span, dict):
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
        self, group_id: str, analysis_result: dict[str, Any], platform_id: str | None
    ) -> bool:
        """分发文本报告"""
        logger.info(f"[分发器] 正在向群组 {group_id} 分发文本报告")
        trace_ctx = TraceContext.current()
        is_qq_official = self._is_qq_official(platform_id)
        fallback_report = None
        if is_qq_official:
            (
                text_report,
                fallback_report,
            ) = await self.report_generator.generate_qq_official_markdown_report(
                analysis_result, self._html_render_func
            )
        else:
            text_report = self.report_generator.generate_text_report(analysis_result)
        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        # 尝试通过适配器发送文本报告
        logger.info(f"[分发器] 正在尝试通过适配器发送文本报告。群: {group_id}")

        with (
            trace_ctx.span(
                "DISPATCH_REPORT",
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

            if dispatch_span and isinstance(dispatch_span, dict):
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

    async def _do_upload_group_file(self, adapter, group_id: str, file_path: str):
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

    async def _do_upload_group_album(self, adapter, group_id: str, file_path: str):
        """上传图片到群相册，失败静默"""
        try:
            album_name = self.config_manager.get_group_album_name()
            strict_mode = self.config_manager.get_group_album_strict_mode()
            album_id = None

            if hasattr(adapter, "find_album_id"):
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

    def _get_onebot_adapter(self, platform_id: str | None):
        """获取 OneBot 适配器，非 OneBot 平台返回 None。"""
        if not platform_id:
            return None
        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        if adapter and hasattr(adapter, "upload_group_file_to_folder"):
            return adapter
        return None
