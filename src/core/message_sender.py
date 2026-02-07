import base64

import aiohttp

from astrbot.api import logger

from ..utils.trace_context import TraceContext


class MessageSender:
    """
    负责消息发送的核心组件
    封装了多平台发送、格式转换 (URL/Base64)、失败重试等逻辑
    """

    def __init__(self, bot_manager, config_manager, retry_manager=None):
        self.bot_manager = bot_manager
        self.config_manager = config_manager
        self.retry_manager = retry_manager

    async def send_text(
        self, group_id: str, text: str, platform_id: str | None = None
    ) -> bool:
        """
        发送文本消息
        """
        trace_id = TraceContext.get()
        logger.info(f"[{trace_id}] Start sending text to group {group_id}")

        platforms = self._get_available_platforms(group_id, platform_id)
        if not platforms:
            logger.error(f"[{trace_id}] No available platforms for group {group_id}")
            return False

        for pid, bot in platforms:
            try:
                logger.info(f"[{trace_id}] Trying platform {pid}...")
                await bot.api.call_action(
                    "send_group_msg", group_id=group_id, message=text
                )
                logger.info(f"[{trace_id}] Successfully sent text via {pid}")
                return True
            except Exception as e:
                self._log_send_error(pid, group_id, "text", e)
                continue

        logger.error(f"[{trace_id}] Failed to send text via all platforms")
        return False

    async def send_image_url(
        self,
        group_id: str,
        image_url: str,
        text_prefix: str = "",
        platform_id: str | None = None,
    ) -> bool:
        """
        发送图片 (URL 模式)
        """
        trace_id = TraceContext.get()
        platforms = self._get_available_platforms(group_id, platform_id)
        if not platforms:
            return False

        message_chain = []
        if text_prefix:
            message_chain.append({"type": "text", "data": {"text": text_prefix}})
        message_chain.append({"type": "image", "data": {"url": image_url}})

        for pid, bot in platforms:
            try:
                logger.info(f"[{trace_id}] Trying sending image (URL) via {pid}...")
                await bot.api.call_action(
                    "send_group_msg", group_id=group_id, message=message_chain
                )
                logger.info(f"[{trace_id}] Successfully sent image (URL) via {pid}")
                return True
            except Exception as e:
                self._log_send_error(pid, group_id, "image_url", e)
                continue
        return False

    async def send_image_base64(
        self,
        group_id: str,
        image_url: str,
        text_prefix: str = "",
        platform_id: str | None = None,
    ) -> bool:
        """
        发送图片 (Base64 模式) - 需先下载图片
        """
        trace_id = TraceContext.get()
        logger.info(f"[{trace_id}] Downloading image for Base64 fallback...")

        image_bytes = await self._download_image(image_url)
        if not image_bytes:
            logger.error(f"[{trace_id}] Failed to download image for Base64 conversion")
            return False

        image_b64 = base64.b64encode(image_bytes).decode()

        platforms = self._get_available_platforms(group_id, platform_id)
        if not platforms:
            return False

        message_chain = []
        if text_prefix:
            message_chain.append({"type": "text", "data": {"text": text_prefix}})
        message_chain.append(
            {"type": "image", "data": {"file": f"base64://{image_b64}"}}
        )

        for pid, bot in platforms:
            try:
                logger.info(f"[{trace_id}] Trying sending image (Base64) via {pid}...")
                await bot.api.call_action(
                    "send_group_msg", group_id=group_id, message=message_chain
                )
                logger.info(f"[{trace_id}] Successfully sent image (Base64) via {pid}")
                return True
            except Exception as e:
                self._log_send_error(pid, group_id, "image_base64", e)
                continue
        return False

    async def send_image_smart(
        self,
        group_id: str,
        image_url: str,
        text_prefix: str = "",
        platform_id: str | None = None,
    ) -> bool:
        """
        智能发送图片：先尝试 URL，失败则回退到 Base64
        """
        if await self.send_image_url(group_id, image_url, text_prefix, platform_id):
            return True

        logger.warning(
            f"[{TraceContext.get()}] URL send failed, falling back to Base64..."
        )
        return await self.send_image_base64(
            group_id, image_url, text_prefix, platform_id
        )

    async def send_pdf(
        self,
        group_id: str,
        pdf_path: str,
        text_prefix: str = "",
        platform_id: str | None = None,
    ) -> bool:
        """
        发送 PDF 文件
        """
        trace_id = TraceContext.get()
        platforms = self._get_available_platforms(group_id, platform_id)
        if not platforms:
            return False

        message_chain = []
        if text_prefix:
            message_chain.append({"type": "text", "data": {"text": text_prefix}})
        message_chain.append({"type": "file", "data": {"file": pdf_path}})

        for pid, bot in platforms:
            try:
                logger.info(f"[{trace_id}] Trying sending PDF via {pid}...")
                await bot.api.call_action(
                    "send_group_msg", group_id=group_id, message=message_chain
                )
                logger.info(f"[{trace_id}] Successfully sent PDF via {pid}")
                return True
            except Exception as e:
                self._log_send_error(pid, group_id, "pdf", e)
                continue
        return False

    def _get_available_platforms(
        self, group_id: str, specific_platform_id: str | None = None
    ) -> list[tuple]:
        """
        获取可用的发送平台列表
        """
        if specific_platform_id:
            bot = self.bot_manager.get_bot_instance(specific_platform_id)
            if bot:
                return [(specific_platform_id, bot)]
            logger.warning(f"Specified platform {specific_platform_id} not found")

        # 获取所有已发现的平台
        all_instances = self.bot_manager.get_all_bot_instances()
        if all_instances:
            # 这里可以加入逻辑判断哪些平台在该群中，目前简单返回所有
            return list(all_instances.items())

        return []

    async def _download_image(self, url: str) -> bytes | None:
        """下载图片 helper"""
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.read()
        except Exception as e:
            logger.error(f"Image download failed: {e}")
            return None

    def _log_send_error(
        self, platform_id: str, group_id: str, msg_type: str, error: Exception
    ):
        """统一错误日志"""
        logger.debug(
            f"[{TraceContext.get()}] Failed to send {msg_type} via {platform_id} to {group_id}: {error}"
        )
