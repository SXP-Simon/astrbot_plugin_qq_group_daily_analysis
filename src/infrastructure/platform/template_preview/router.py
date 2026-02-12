"""模板预览平台路由。"""

from __future__ import annotations

from typing import Any


class TemplatePreviewRouter:
    """统一分发不同平台的模板预览处理器。"""

    def __init__(self, handlers: list[Any] | None = None):
        self._handlers: list[Any] = handlers or []

    def add_handler(self, handler: Any) -> None:
        """注册一个平台处理器。"""
        self._handlers.append(handler)

    async def ensure_handlers_registered(self, context: Any) -> None:
        """让处理器完成初始化（如注册回调）。"""
        for handler in self._handlers:
            register_func = getattr(
                handler, "ensure_callback_handlers_registered", None
            )
            if callable(register_func):
                await register_func(context)

    async def unregister_handlers(self) -> None:
        """统一注销处理器资源。"""
        for handler in self._handlers:
            unregister_func = getattr(handler, "unregister_callback_handlers", None)
            if callable(unregister_func):
                await unregister_func()

    async def handle_view_templates(
        self,
        event: Any,
        platform_id: str,
        available_templates: list[str],
    ) -> tuple[bool, list[Any]]:
        """
        处理 /查看模板 交互。

        返回:
        - handled: 是否已由某个平台处理器接管
        - results: 需要回传给框架的消息结果列表
        """
        for handler in self._handlers:
            supports_func = getattr(handler, "supports", None)
            if not callable(supports_func) or not supports_func(event):
                continue

            handle_func = getattr(handler, "handle_view_templates", None)
            if not callable(handle_func):
                continue

            handled, results = await handle_func(
                event=event,
                platform_id=platform_id,
                available_templates=available_templates,
            )
            return handled, results

        return False, []
