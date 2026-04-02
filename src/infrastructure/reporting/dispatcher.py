import base64
import os
import tempfile
from collections.abc import Callable
from datetime import datetime
from typing import Any

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

    async def dispatch(
        self,
        group_id: str,
        analysis_result: dict[str, Any],
        platform_id: str | None = None,
    ):
        """
        分发分析报告

        Args:
            group_id: 原始分析的群组 ID
            analysis_result: 分析结果
            platform_id: 平台 ID

        """
        trace_id = TraceContext.get()

        source_group_id = group_id
        source_platform_id = platform_id

        destinations = self._resolve_destinations(source_group_id, source_platform_id)
        if not destinations:
            destinations = [(source_platform_id, source_group_id)]

        dest_labels = ", ".join(
            f"{pid or 'default'}:{gid}" for pid, gid in destinations
        )
        output_format = self.config_manager.get_output_format()
        logger.info(
            f"[{trace_id}] 正在分发群 {source_group_id} 的报告 (格式: {output_format}) -> {dest_labels}"
        )

        render_cache: dict[str, Any] = {}
        success_any = False
        for target_platform_id, target_group_id in destinations:
            dest_success = await self._dispatch_to_destination(
                target_group_id,
                target_platform_id,
                analysis_result,
                output_format,
                render_cache,
                source_group_id,
                source_platform_id,
            )
            success_any = success_any or dest_success

        if success_any:
            logger.info(f"[{trace_id}] 群 {source_group_id} 的报告分发成功")
        else:
            logger.warning(f"[{trace_id}] 群 {source_group_id} 的报告分发失败")

    def _resolve_destinations(
        self, source_group_id: str, platform_id: str | None
    ) -> list[tuple[str | None, str]]:
        """
        根据 UMO Group 与双重发送配置解析所有目标 UMO。
        返回 (platform_id, group_id) 的去重列表。
        """
        if not platform_id:
            return [(platform_id, source_group_id)]

        source_umo = f"{platform_id}:GroupMessage:{source_group_id}"
        dest_umos = self.config_manager.get_report_destinations(
            source_umo, include_source_if_group_member=True
        )

        destinations: list[tuple[str | None, str]] = []
        for dest_umo in dest_umos:
            target_platform, target_group = self._parse_target_umo(
                dest_umo, platform_id, source_group_id
            )
            destinations.append((target_platform, target_group))

        # 去重并保持顺序
        deduped: list[tuple[str | None, str]] = []
        seen: set[tuple[str | None, str]] = set()
        for item in destinations:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    def _parse_target_umo(
        self, dest_umo: str, fallback_platform: str | None, fallback_group: str
    ) -> tuple[str | None, str]:
        """解析目标 UMO，无法解析时回退到源 UMO。"""
        trace_id = TraceContext.get()
        try:
            parts = str(dest_umo).split(":")
            if len(parts) >= 3:
                return parts[0], parts[-1]
            if len(parts) == 2:
                return parts[0], parts[1]
            if len(parts) == 1 and parts[0]:
                return fallback_platform, parts[0]
        except Exception:
            logger.debug(
                f"[{trace_id}] 无法解析目标 UMO '{dest_umo}'，回退到源群 {fallback_group}"
            )
        return fallback_platform, fallback_group

    async def _dispatch_to_destination(
        self,
        target_group_id: str,
        target_platform_id: str | None,
        analysis_result: dict[str, Any],
        output_format: str,
        render_cache: dict[str, Any],
        source_group_id: str,
        source_platform_id: str | None,
    ) -> bool:
        """按单个目标分发报告，必要时回退到文本模式。"""
        trace_id = TraceContext.get()
        logger.info(
            f"[{trace_id}] 分发到 {target_platform_id or 'default'}:{target_group_id}"
        )

        if output_format == "image":
            return await self._dispatch_image_cached(
                target_group_id,
                analysis_result,
                target_platform_id,
                render_cache,
                source_group_id,
                source_platform_id,
            )
        if output_format == "pdf":
            return await self._dispatch_pdf_cached(
                target_group_id,
                analysis_result,
                target_platform_id,
                render_cache,
                source_group_id,
            )
        if output_format == "html":
            return await self._dispatch_html_cached(
                target_group_id,
                analysis_result,
                target_platform_id,
                render_cache,
                source_group_id,
            )
        return await self._dispatch_text_cached(
            target_group_id,
            analysis_result,
            target_platform_id,
            render_cache,
        )

    async def _dispatch_image_cached(
        self,
        target_group_id: str,
        analysis_result: dict[str, Any],
        platform_id: str | None,
        render_cache: dict[str, Any],
        source_group_id: str,
        source_platform_id: str | None,
    ) -> bool:
        trace_id = TraceContext.get()
        if not self._html_render_func:
            logger.warning(f"[{trace_id}] 未设置 HTML 渲染函数，回退到文本模式。")
            return await self._dispatch_text_cached(
                target_group_id, analysis_result, platform_id, render_cache
            )

        if "image" not in render_cache:
            try:
                async def avatar_url_getter(user_id: str):
                    if not source_platform_id:
                        return None
                    adapter = self.message_sender.bot_manager.get_adapter(
                        source_platform_id
                    )
                    if adapter and hasattr(adapter, "get_user_avatar_url"):
                        return await adapter.get_user_avatar_url(user_id, size=40)
                    return None

                image_url, html_content = (
                    await self.report_generator.generate_image_report(
                        analysis_result,
                        source_group_id,
                        self._html_render_func,
                        avatar_url_getter=avatar_url_getter,
                    )
                )
                render_cache["image"] = {
                    "image_url": image_url,
                    "html_content": html_content,
                }
            except Exception as e:
                logger.error(f"[{trace_id}] Failed to generate image report: {e}")
                render_cache["image"] = None

        image_ctx = render_cache.get("image")
        image_url = image_ctx.get("image_url") if image_ctx else None
        if image_url:
            caption = TraceContext.make_report_caption()
            sent = await self.message_sender.send_image_smart(
                target_group_id, image_url, caption, platform_id
            )
            if sent:
                await self._try_upload_image(target_group_id, image_url, platform_id)
                return True

        logger.warning(
            f"[{trace_id}] Image dispatch failed, falling back to text report."
        )
        return await self._dispatch_text_cached(
            target_group_id, analysis_result, platform_id, render_cache
        )

    async def _dispatch_pdf_cached(
        self,
        target_group_id: str,
        analysis_result: dict[str, Any],
        platform_id: str | None,
        render_cache: dict[str, Any],
        source_group_id: str,
    ) -> bool:
        trace_id = TraceContext.get()
        if not self.config_manager.playwright_available:
            logger.warning(
                f"[{trace_id}] Playwright not available, falling back to text."
            )
            return await self._dispatch_text_cached(
                target_group_id, analysis_result, platform_id, render_cache
            )

        if "pdf" not in render_cache:
            try:
                render_cache["pdf"] = await self.report_generator.generate_pdf_report(
                    analysis_result, source_group_id
                )
            except Exception as e:
                logger.error(f"[{trace_id}] Failed to generate PDF report: {e}")
                render_cache["pdf"] = None

        pdf_path = render_cache.get("pdf")
        if pdf_path:
            sent = await self.message_sender.send_file(
                target_group_id,
                pdf_path,
                caption="📊 每日群聊分析报告已生成：",
                platform_id=platform_id,
            )
            if sent:
                return True

        logger.warning(
            f"[{trace_id}] PDF dispatch failed, falling back to text report."
        )
        return await self._dispatch_text_cached(
            target_group_id, analysis_result, platform_id, render_cache
        )

    async def _dispatch_html_cached(
        self,
        target_group_id: str,
        analysis_result: dict[str, Any],
        platform_id: str | None,
        render_cache: dict[str, Any],
        source_group_id: str,
    ) -> bool:
        trace_id = TraceContext.get()

        if "html" not in render_cache:
            try:
                html_path, json_path = await self.report_generator.generate_html_report(
                    analysis_result, source_group_id
                )
                caption = (
                    self.report_generator.build_html_caption(html_path)
                    if html_path
                    else ""
                )
                render_cache["html"] = {
                    "html_path": html_path,
                    "json_path": json_path,
                    "caption": caption,
                }
            except Exception as e:
                logger.error(f"[{trace_id}] Failed to generate HTML report: {e}")
                render_cache["html"] = None

        html_ctx = render_cache.get("html") or {}
        html_path = html_ctx.get("html_path")
        caption = html_ctx.get("caption", "")

        if html_path:
            sent = await self.message_sender.send_file(
                target_group_id,
                html_path,
                caption=caption,
                platform_id=platform_id,
            )
            if sent:
                return True

        logger.warning(
            f"[{trace_id}] HTML dispatch failed, falling back to text report."
        )
        return await self._dispatch_text_cached(
            target_group_id, analysis_result, platform_id, render_cache
        )

    async def _dispatch_text_cached(
        self,
        target_group_id: str,
        analysis_result: dict[str, Any],
        platform_id: str | None,
        render_cache: dict[str, Any],
    ) -> bool:
        """分发文本报告（带缓存，避免重复生成）。"""
        logger.info(f"[分发器] 正在向群组 {target_group_id} 分发文本报告")

        if "text" not in render_cache:
            render_cache["text"] = self.report_generator.generate_text_report(
                analysis_result
            )
        text_report = render_cache.get("text", "")

        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        logger.info(f"[分发器] 正在尝试通过适配器发送文本报告。群: {target_group_id}")
        try:
            if adapter and await adapter.send_text_report(target_group_id, text_report):
                return True
            return await self.message_sender.send_text(
                target_group_id,
                f"📊 每日群聊分析报告：\n\n{text_report}",
                platform_id,
            )
        except Exception as e:
            logger.error(
                f"[分发器] 发送文本报告最终失败。群: {target_group_id}, 错误: {e}"
            )
            return False

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
                tempfile.gettempdir(), f"群聊分析报告_{group_id}_{date_str}.png"
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
