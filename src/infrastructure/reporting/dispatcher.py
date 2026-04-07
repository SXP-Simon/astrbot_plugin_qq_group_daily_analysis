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
        """
        trace_id = TraceContext.get()
        output_format = self.config_manager.get_output_format()
        logger.info(
            f"[{trace_id}] 正在分发群 {group_id} 的报告 (格式: {output_format})"
        )

        success = False
        if output_format == "image":
            success = await self._dispatch_image(group_id, analysis_result, platform_id)
        elif output_format == "pdf":
            success = await self._dispatch_pdf(group_id, analysis_result, platform_id)
        elif output_format == "html":
            success = await self._dispatch_html(group_id, analysis_result, platform_id)
        else:
            success = await self._dispatch_text(group_id, analysis_result, platform_id)

        if success:
            logger.info(f"[{trace_id}] 群 {group_id} 的报告分发成功")
        else:
            logger.warning(f"[{trace_id}] 群 {group_id} 的报告分发失败")

    async def _dispatch_image(
        self, group_id: str, analysis_result: dict[str, Any], platform_id: str | None
    ) -> bool:
        trace_id = TraceContext.get()
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

            image_url, html_content = await self.report_generator.generate_image_report(
                analysis_result,
                group_id,
                self._html_render_func,
                avatar_url_getter=avatar_url_getter,
            )
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to generate image report: {e}")
            # image_url and html_content remain None

        # 4. 发送图片
        sent = False
        if image_url:
            caption = TraceContext.make_report_caption()
            sent = await self.message_sender.send_image_smart(
                group_id, image_url, caption, platform_id
            )

            # 5. 尝试上传到群文件/群相册（静默处理）
            # 无论消息发送是否成功（如超时回退），只要图片生成了，就尝试备份到群文件
            await self._try_upload_image(group_id, image_url, platform_id)

        if sent:
            return True

        # 6. 最终回退：如果图片发送失败（包括生成失败或发送接口报错），直接尝试发送文本报告
        logger.warning(
            f"[{trace_id}] Image dispatch failed, falling back to text report."
        )
        return await self._dispatch_text(group_id, analysis_result, platform_id)

    async def _dispatch_pdf(
        self, group_id: str, analysis_result: dict[str, Any], platform_id: str | None
    ) -> bool:
        trace_id = TraceContext.get()
        # 1. 检查 Playwright
        if not self.config_manager.playwright_available:
            logger.warning(
                f"[{trace_id}] Playwright not available, falling back to text."
            )
            return await self._dispatch_text(group_id, analysis_result, platform_id)

        # 2. 生成 PDF
        pdf_path = None
        try:
            pdf_path = await self.report_generator.generate_pdf_report(
                analysis_result, group_id
            )
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to generate PDF report: {e}")

        # 3. 发送 PDF
        if pdf_path:
            sent = await self.message_sender.send_file(
                group_id,
                pdf_path,
                caption="📊 每日群聊分析报告已生成：",
                platform_id=platform_id,
            )
            if sent:
                return True

        # 4. 回退：文本报告
        logger.warning(
            f"[{trace_id}] PDF dispatch failed, falling back to text report."
        )
        return await self._dispatch_text(group_id, analysis_result, platform_id)

    async def _dispatch_html(
        self, group_id: str, analysis_result: dict[str, Any], platform_id: str | None
    ) -> bool:
        trace_id = TraceContext.get()

        html_path = None
        try:
            html_path, json_path = await self.report_generator.generate_html_report(
                analysis_result, group_id
            )
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to generate HTML report: {e}")

        if html_path:
            caption = self.report_generator.build_html_caption(html_path)

            sent = await self.message_sender.send_file(
                group_id,
                html_path,
                caption=caption,
                platform_id=platform_id,
            )
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
        text_report = self.report_generator.generate_text_report(analysis_result)
        adapter = self.message_sender.bot_manager.get_adapter(platform_id)
        # 尝试通过适配器发送文本报告
        logger.info(f"[分发器] 正在尝试通过适配器发送文本报告。群: {group_id}")
        try:
            if adapter and await adapter.send_text_report(group_id, text_report):
                return True
            return await self.message_sender.send_text(
                group_id, f"📊 每日群聊分析报告：\n\n{text_report}", platform_id
            )
        except Exception as e:
            logger.error(f"[分发器] 发送文本报告最终失败。群: {group_id}, 错误: {e}")
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
