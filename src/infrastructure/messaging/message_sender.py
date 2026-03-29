"""
消息发送器 - 基础设施层
提供高层消息发送接口，支持跨平台智能路由。
"""

from typing import Protocol

from ...utils.logger import logger


class _AdapterLike(Protocol):
    async def send_text(self, group_id: str, text: str) -> bool: ...
    async def send_image(
        self, group_id: str, image_url: str, caption: str = ""
    ) -> bool: ...
    async def send_file(self, group_id: str, file_path: str) -> bool: ...


class _BotManagerLike(Protocol):
    def get_adapter(self, platform_id: str | None = None) -> _AdapterLike | None: ...
    def get_platform_ids(self) -> list[str]: ...


class MessageSender:
    """
    消息发送器
    封装了 PlatformAdapter 的底层调用，提供更高层的发送接口
    """

    def __init__(
        self,
        bot_manager: _BotManagerLike,
        config_manager: object,
        retry_manager: object,
    ) -> None:
        self.bot_manager = bot_manager
        self.config_manager = config_manager
        self.retry_manager = retry_manager

    async def send_text(
        self, group_id: str, text: str, platform_id: str | None = None
    ) -> bool:
        """发送文本消息"""
        adapter = self.bot_manager.get_adapter(platform_id)
        if not adapter:
            logger.error(f"[MessageSender] 未找到平台 {platform_id} 的适配器")
            return False
        return await adapter.send_text(group_id, text)

    async def send_image_smart(
        self,
        group_id: str,
        image_url: str,
        caption: str = "",
        platform_id: str | None = None,
    ) -> bool:
        """智能发送图片，支持自动选择适配器"""
        adapter = self.bot_manager.get_adapter(platform_id)
        if not adapter:
            logger.error(f"[MessageSender] 未找到平台 {platform_id} 的适配器")
            return False
        return await adapter.send_image(group_id, image_url, caption)

    async def send_pdf(
        self,
        group_id: str,
        pdf_path: str,
        caption: str = "",
        platform_id: str | None = None,
    ) -> bool:
        """发送 PDF 文件"""
        adapter = self.bot_manager.get_adapter(platform_id)
        if not adapter:
            logger.error(f"[MessageSender] 未找到平台 {platform_id} 的适配器")
            return False
        return await adapter.send_file(group_id, pdf_path)

    def _get_available_platforms(self, group_id: str) -> list[tuple[str, object]]:
        """获取可用的平台列表 (Helper for Dispatcher)"""
        # 简单实现：返回所有已加载的平台
        return [(pid, None) for pid in self.bot_manager.get_platform_ids()]
