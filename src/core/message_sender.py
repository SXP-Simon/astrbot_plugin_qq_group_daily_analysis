import base64

import aiohttp

from ..utils.logger import logger
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
        logger.info(f"[{trace_id}] 开始发送文本消息到群 {group_id}")

        platforms = self._get_available_platforms(group_id, platform_id)
        if not platforms:
            logger.error(f"[{trace_id}] 群 {group_id} 无可用发送平台")
            return False

        for pid, adapter in platforms:
            try:
                logger.info(f"[{trace_id}] 正在尝试平台 {pid}...")

                # 优先使用 Adapter 接口
                if hasattr(adapter, "send_text"):
                    if await adapter.send_text(group_id, text):
                        logger.info(f"[{trace_id}] 成功通过 {pid} 发送文本")
                        return True

                # Fallback to OneBot API (for backward compatibility or if adapter wrapping failed)
                if hasattr(adapter, "api") and hasattr(adapter.api, "call_action"):
                    await adapter.api.call_action(
                        "send_group_msg", group_id=group_id, message=text
                    )
                    logger.info(f"[{trace_id}] 成功通过 {pid} 发送文本 (API)")
                    return True

            except Exception as e:
                self._log_send_error(pid, group_id, "text", e)
                continue

        logger.error(f"[{trace_id}] 所有平台均发送文本失败")
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

        for pid, adapter in platforms:
            try:
                logger.info(f"[{trace_id}] 正在通过 {pid} 发送图片 (URL 模式)...")

                # 优先使用 Adapter 接口
                if hasattr(adapter, "send_image"):
                    if await adapter.send_image(
                        group_id, image_url, caption=text_prefix
                    ):
                        logger.info(f"[{trace_id}] 成功通过 {pid} 发送图片 (URL 模式)")
                        return True

                # Fallback to OneBot API
                if hasattr(adapter, "api") and hasattr(adapter.api, "call_action"):
                    message_chain = []
                    if text_prefix:
                        message_chain.append(
                            {"type": "text", "data": {"text": text_prefix}}
                        )
                    message_chain.append({"type": "image", "data": {"url": image_url}})

                    await adapter.api.call_action(
                        "send_group_msg", group_id=group_id, message=message_chain
                    )
                    logger.info(
                        f"[{trace_id}] 成功通过 {pid} 发送图片 (URL 模式) (API)"
                    )
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
        logger.info(f"[{trace_id}] 正在下载图片以进行 Base64 回退发送...")

        image_bytes = await self._download_image(image_url)
        if not image_bytes:
            logger.error(f"[{trace_id}] 下载图片进行 Base64 转换失败")
            return False

        image_b64 = base64.b64encode(image_bytes).decode()
        # file URI for Base64 (OneBot style)
        base64_uri = f"base64://{image_b64}"

        platforms = self._get_available_platforms(group_id, platform_id)
        if not platforms:
            return False

        for pid, adapter in platforms:
            try:
                logger.info(f"[{trace_id}] 正在通过 {pid} 发送图片 (Base64 模式)...")

                # 优先使用 Adapter 接口 (注意 Adapter 接口通常接受 path/url，这里我们传 base64 uri 它是支持的吗？)
                # 大多数 Adapter 的 send_image 如果识别 base64:// 应该能处理
                # 如果是 DiscordAdapter, 它需要特殊处理 local file.
                # 但这里是 Base64 string.
                # 为了稳妥，我们可以先尝试 Adapter，如果 Adapter 明确支持 base64://

                if hasattr(adapter, "send_image"):
                    # 尝试发送 base64 URI
                    if await adapter.send_image(
                        group_id, base64_uri, caption=text_prefix
                    ):
                        logger.info(
                            f"[{trace_id}] 成功通过 {pid} 发送图片 (Base64 模式)"
                        )
                        return True

                # Fallback to OneBot API
                if hasattr(adapter, "api") and hasattr(adapter.api, "call_action"):
                    message_chain = []
                    if text_prefix:
                        message_chain.append(
                            {"type": "text", "data": {"text": text_prefix}}
                        )
                    message_chain.append(
                        {"type": "image", "data": {"file": base64_uri}}
                    )

                    await adapter.api.call_action(
                        "send_group_msg", group_id=group_id, message=message_chain
                    )
                    logger.info(
                        f"[{trace_id}] 成功通过 {pid} 发送图片 (Base64 模式) (API)"
                    )
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
            f"[{TraceContext.get()}] URL 发送失败，正在回退至 Base64 模式..."
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

        for pid, adapter in platforms:
            try:
                logger.info(f"[{trace_id}] 正在通过 {pid} 发送 PDF...")

                if hasattr(adapter, "send_file"):
                    if await adapter.send_file(group_id, pdf_path):
                        logger.info(f"[{trace_id}] 成功通过 {pid} 发送 PDF")
                        return True

                # Fallback to OneBot API
                if hasattr(adapter, "api") and hasattr(adapter.api, "call_action"):
                    message_chain = []
                    if text_prefix:
                        message_chain.append(
                            {"type": "text", "data": {"text": text_prefix}}
                        )
                    message_chain.append({"type": "file", "data": {"file": pdf_path}})

                    await adapter.api.call_action(
                        "send_group_msg", group_id=group_id, message=message_chain
                    )
                    logger.info(f"[{trace_id}] 成功通过 {pid} 发送 PDF (API)")
                    return True

            except Exception as e:
                self._log_send_error(pid, group_id, "pdf", e)
                continue
        return False

    def _get_available_platforms(
        self, group_id: str, specific_platform_id: str | None = None
    ) -> list[tuple]:
        """
        获取可用的发送平台列表 (返回 Adapter 实例)
        """
        from ..infrastructure.platform.base import PlatformAdapter
        from ..infrastructure.platform.factory import PlatformAdapterFactory

        instances = []

        if specific_platform_id:
            bot = self.bot_manager.get_bot_instance(specific_platform_id)
            if bot:
                instances.append((specific_platform_id, bot))
            else:
                logger.warning(f"找不到指定的平台 {specific_platform_id}")
        else:
            # 获取所有已发现的平台
            all_instances = self.bot_manager.get_all_bot_instances()
            if all_instances:
                instances = list(all_instances.items())

        # Wrap instances with Adapters if needed
        adapters = []
        for pid, bot in instances:
            # Check if it's already an adapter
            if isinstance(bot, PlatformAdapter):
                adapters.append((pid, bot))
                continue

            # If not, try to create an adapter
            # We need to detect platform name first
            platform_name = self.bot_manager._detect_platform_name(bot)
            if not platform_name:
                # If cannot detect, assume it's a OneBot raw object if it has api
                if hasattr(bot, "api"):
                    adapters.append((pid, bot))  # Return raw bot for backward compat
                continue

            # Create adapter
            try:
                # We need config for adapter, here we use empty config or try to fetch from somewhere
                # Ideally config_manager should provide it but it's complex.
                # Passing empty config is fine for basic sending tasks as long as bot instance is valid.
                adapter = PlatformAdapterFactory.create(platform_name, bot, config={})
                if adapter:
                    adapters.append((pid, adapter))
                else:
                    # Fallback: return raw bot
                    adapters.append((pid, bot))
            except Exception as e:
                logger.warning(f"为 {pid} 创建适配器失败: {e}")
                adapters.append((pid, bot))

        return adapters

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
            logger.error(f"图片下载失败: {e}")
            return None

    def _log_send_error(
        self, platform_id: str, group_id: str, msg_type: str, error: Exception
    ):
        """统一错误日志"""
        logger.debug(
            f"[{TraceContext.get()}] 通过 {platform_id} 向 {group_id} 发送 {msg_type} 失败: {error}"
        )
