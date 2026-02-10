from collections.abc import Callable
from typing import Any

from ...utils.logger import logger
from ...utils.trace_context import TraceContext


class ReportDispatcher:
    """
    报告分发器
    负责协调报告生成、格式选择、消息发送和失败重试
    """

    def __init__(self, config_manager, report_generator, message_sender, retry_manager):
        self.config_manager = config_manager
        self.report_generator = report_generator
        self.message_sender = message_sender
        self.retry_manager = retry_manager
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
            f"[{trace_id}] Dispatching report for group {group_id} (Format: {output_format})"
        )

        success = False
        if output_format == "image":
            success = await self._dispatch_image(group_id, analysis_result, platform_id)
        elif output_format == "pdf":
            success = await self._dispatch_pdf(group_id, analysis_result, platform_id)
        else:
            success = await self._dispatch_text(group_id, analysis_result, platform_id)

        if success:
            logger.info(
                f"[{trace_id}] Report dispatched successfully for group {group_id}"
            )
        else:
            logger.warning(
                f"[{trace_id}] Failed to dispatch report for group {group_id}"
            )

    async def _dispatch_image(
        self, group_id: str, analysis_result: dict[str, Any], platform_id: str | None
    ) -> bool:
        trace_id = TraceContext.get()
        # 1. 检查渲染函数
        if not self._html_render_func:
            logger.warning(
                f"[{trace_id}] HTML render function not set, falling back to text."
            )
            return await self._dispatch_text(group_id, analysis_result, platform_id)

        # 2. 生成图片
        image_url = None
        html_content = None
        try:
            # 定义头像获取回调，请求小尺寸头像以优化性能
            async def avatar_getter(user_id: str):
                if not platform_id:
                    return None
                adapter = self.message_sender.bot_manager.get_adapter(platform_id)
                if adapter and hasattr(adapter, "get_user_avatar_url"):
                    return await adapter.get_user_avatar_url(user_id, size=40)
                return None

            image_url, html_content = await self.report_generator.generate_image_report(
                analysis_result, group_id, self._html_render_func, avatar_getter=avatar_getter
            )
        except Exception as e:
            logger.error(f"[{trace_id}] Failed to generate image report: {e}")
            # image_url and html_content remain None

        # 3. 发送图片
        if image_url:
            sent = await self.message_sender.send_image_smart(
                group_id, image_url, "📊 每日群聊分析报告已生成：", platform_id
            )
            if sent:
                return True

        # 4. 发送失败或生成失败的处理 -> 加入重试队列
        if html_content:
            logger.warning(
                f"[{trace_id}] Image dispatch failed, adding to retry queue..."
            )
            # 尝试获取 platform_id 如果没有提供
            if not platform_id:
                # 这里假设 MessageSender 能帮忙或者我们需要自己查
                # 由于 Dispatcher 不直接持有 BotManager (除了通过 MessageSender 间接持有)
                # 原有逻辑：AutoScheduler 调用 get_platform_id_for_group
                # 我们这里暂时依赖传入的 platform_id，如果没有，RetryManager 可能处理不了?
                # 实际上 RetryManager 需要 platform_id。
                # 让我们尝试通过 MessageSender 的 bot_manager 获取一个
                # 或者更简单：如果 platform_id 为空，我们尝试获取第一个可用的 (MessageSender._get_available_platforms Logic)
                platforms = self.message_sender._get_available_platforms(group_id)
                if platforms:
                    platform_id = platforms[0][0]  # use first available

            if platform_id:
                await self.retry_manager.add_task(
                    html_content, analysis_result, group_id, platform_id
                )
                return True  # 已加入队列视作处理成功 (不在此处报错)
            else:
                logger.error(
                    f"[{trace_id}] Cannot add to retry queue: No platform_id available."
                )

        # 5. 最终回退：文本报告
        logger.warning(f"[{trace_id}] Falling back to text report.")
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
            sent = await self.message_sender.send_pdf(
                group_id, pdf_path, "📊 每日群聊分析报告已生成：", platform_id
            )
            if sent:
                return True

        # 4. 回退：文本报告
        logger.warning(
            f"[{trace_id}] PDF dispatch failed, falling back to text report."
        )
        return await self._dispatch_text(group_id, analysis_result, platform_id)

    async def _dispatch_text(
        self, group_id: str, analysis_result: dict[str, Any], platform_id: str | None
    ) -> bool:
        try:
            text_report = self.report_generator.generate_text_report(analysis_result)
            return await self.message_sender.send_text(
                group_id, f"📊 每日群聊分析报告：\n\n{text_report}", platform_id
            )
        except Exception as e:
            logger.error(f"[{TraceContext.get()}] Failed to dispatch text report: {e}")
            return False
