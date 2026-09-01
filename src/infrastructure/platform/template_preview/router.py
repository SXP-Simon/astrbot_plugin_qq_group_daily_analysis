"""模板预览平台路由与协议定义。"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context


@runtime_checkable
class TemplatePreviewHandler(Protocol):
    """平台模板预览处理器协议接口。"""

    def supports(self, event: AstrMessageEvent) -> bool:
        """检查该处理器是否支持当前消息事件。"""
        ...

    def ensure_callback_handlers_registered(
        self, context: Context
    ) -> Awaitable[None] | None:
        """确保平台回调处理器已正确注册。"""
        ...

    def unregister_callback_handlers(self) -> Awaitable[None] | None:
        """注销已注册的回调处理器。"""
        ...

    def handle_view_templates(
        self,
        event: AstrMessageEvent,
        platform_id: str,
        available_templates: list[str],
    ) -> (
        Awaitable[tuple[bool, list[MessageEventResult]]]
        | tuple[bool, list[MessageEventResult]]
    ):
        """处理 /查看模板 指令。"""
        ...


class TemplatePreviewRouter:
    """统一分发不同平台的模板预览处理器。"""

    def __init__(self, handlers: list[TemplatePreviewHandler] | None = None) -> None:
        self._handlers: list[TemplatePreviewHandler] = handlers or []

    def add_handler(self, handler: TemplatePreviewHandler) -> None:
        """注册一个平台处理器。"""
        self._handlers.append(handler)

    async def ensure_handlers_registered(self, context: Context) -> None:
        """让处理器完成初始化（如注册回调）。"""
        for handler in self._handlers:
            res = handler.ensure_callback_handlers_registered(context)
            if inspect.isawaitable(res):
                await res

    async def unregister_handlers(self) -> None:
        """统一注销处理器资源。"""
        for handler in self._handlers:
            res = handler.unregister_callback_handlers()
            if inspect.isawaitable(res):
                await res

    async def handle_view_templates(
        self,
        event: AstrMessageEvent,
        platform_id: str,
        available_templates: list[str],
    ) -> tuple[bool, list[MessageEventResult]]:
        """处理 /查看模板 交互。

        Args:
            event: AstrBot 消息事件。
            platform_id: 平台实例标识。
            available_templates: 可用模板名称列表。

        Returns:
            (handled, results) 元组。
        """
        for handler in self._handlers:
            if not handler.supports(event):
                continue

            res = handler.handle_view_templates(
                event=event,
                platform_id=platform_id,
                available_templates=available_templates,
            )
            if inspect.isawaitable(res):
                handled, results = await res
            else:
                handled, results = res

            return bool(handled), list(results)

        return False, []
