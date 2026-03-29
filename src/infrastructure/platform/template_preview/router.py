# pyright: reportMissingImports=false
"""模板预览平台路由。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


class SupportsTemplatePreviewHandler(Protocol):
    def supports(self, event: AstrMessageEvent) -> bool: ...

    async def ensure_callback_handlers_registered(self, context: object) -> None: ...

    async def unregister_callback_handlers(self) -> None: ...

    async def handle_view_templates(
        self,
        event: AstrMessageEvent,
        platform_id: str,
        available_templates: list[str],
    ) -> tuple[bool, list[object]]: ...


class TemplatePreviewRouter:
    """统一分发不同平台的模板预览处理器。"""

    def __init__(self, handlers: list[SupportsTemplatePreviewHandler] | None = None):
        self._handlers: list[SupportsTemplatePreviewHandler] = handlers or []

    def add_handler(self, handler: SupportsTemplatePreviewHandler) -> None:
        """注册一个平台处理器。"""
        self._handlers.append(handler)

    async def ensure_handlers_registered(self, context: object) -> None:
        """让处理器完成初始化（如注册回调）。"""
        for handler in self._handlers:
            await handler.ensure_callback_handlers_registered(context)

    async def unregister_handlers(self) -> None:
        """统一注销处理器资源。"""
        for handler in self._handlers:
            await handler.unregister_callback_handlers()

    async def handle_view_templates(
        self,
        event: AstrMessageEvent,
        platform_id: str,
        available_templates: list[str],
    ) -> tuple[bool, list[object]]:
        """
        处理 /查看模板 交互。

        返回:
        - handled: 是否已由某个平台处理器接管
        - results: 需要回传给框架的消息结果列表
        """
        for handler in self._handlers:
            if not handler.supports(event):
                continue

            handled, results = await handler.handle_view_templates(
                event=event,
                platform_id=platform_id,
                available_templates=available_templates,
            )
            if handled:
                return handled, results

        return False, []
