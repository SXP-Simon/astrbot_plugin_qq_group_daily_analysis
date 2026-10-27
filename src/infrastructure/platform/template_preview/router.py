"""模板预览平台路由与协议定义。"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from astrbot.api.message_components import Image, Plain

from ....utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from astrbot.api.event import AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context

    from ....application.services.template_command_service import TemplateCommandService
    from .image_cache import PreviewImageCache


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
        template_name: str = "",
    ) -> (
        Awaitable[tuple[bool, list[MessageEventResult]]]
        | tuple[bool, list[MessageEventResult]]
    ):
        """处理 /查看模板 指令。"""
        ...


class TemplatePreviewRouter:
    """统一分发不同平台的模板预览处理器。"""

    def __init__(
        self,
        handlers: list[TemplatePreviewHandler] | None = None,
        template_service: TemplateCommandService | None = None,
        image_cache: PreviewImageCache | None = None,
    ) -> None:
        self._handlers: list[TemplatePreviewHandler] = handlers or []
        self.template_service = template_service
        self.image_cache = image_cache

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
        template_input: str = "",
    ) -> tuple[bool, list[MessageEventResult]]:
        """处理 /查看模板 交互。

        Args:
            event: AstrBot 消息事件。
            platform_id: 平台实例标识。
            available_templates: 可用模板名称列表。
            template_input: 可选的模板名称或序号。

        Returns:
            (handled, results) 元组。
        """
        selected = ""
        logger.debug(
            "[模板预览] 路由入口: platform_id=%s handlers=%s has_selection=%s",
            platform_id,
            [type(handler).__name__ for handler in self._handlers],
            bool(template_input),
        )
        if template_input and self.template_service:
            selected, error = self.template_service.parse_template_input(
                template_input, available_templates
            )
            if error or selected not in available_templates:
                return True, [
                    event.plain_result(
                        error or "未找到这个模板，请使用列表中的序号或名称。"
                    )
                    .use_markdown(False)
                    .use_t2i(False)
                ]
            selected = selected or ""
        for handler in self._handlers:
            supported = handler.supports(event)
            logger.debug(
                "[模板预览] 路由匹配: handler=%s supported=%s",
                type(handler).__name__,
                supported,
            )
            if not supported:
                continue

            res = handler.handle_view_templates(
                event=event,
                platform_id=platform_id,
                available_templates=available_templates,
                template_name=selected,
            )
            if inspect.isawaitable(res):
                handled, results = await res
            else:
                handled, results = res

            logger.debug(
                "[模板预览] 平台处理完成: handler=%s handled=%s pending_results=%s",
                type(handler).__name__,
                handled,
                len(results),
            )
            return bool(handled), list(results)

        if event.get_platform_name() in {"qq_official", "qq_official_webhook"}:
            logger.warning(
                "[模板预览] QQ 官方预览路由未命中，已阻止发送不支持的 Nodes；请检查插件是否完整更新并重载: platform_id=%s",
                platform_id,
            )
            return True, [
                event.plain_result("QQ 模板预览组件未就绪，请重载插件后重试。")
                .use_markdown(False)
                .use_t2i(False)
            ]

        if self.template_service and self.image_cache:
            logger.debug("[模板预览] 无平台专用处理器命中，使用通用预览: output=Nodes")
            current = self.template_service.config_provider
            nodes = self.template_service.build_template_preview_nodes(
                available_templates,
                current.get_report_template() if current else "",
                event.get_self_id(),
            )
            if selected:
                nodes.nodes = [
                    nodes.nodes[0],
                    nodes.nodes[available_templates.index(selected) + 1],
                ]
            failures = 0
            for node in nodes.nodes:
                for index, component in enumerate(node.content):
                    if not isinstance(component, Image):
                        continue
                    try:
                        source = component.file or component.url or ""
                        path = await self.image_cache.get_jpeg(source)
                        node.content[index] = Image.fromFileSystem(path)
                    except Exception as exc:
                        failures += 1
                        logger.debug(
                            "模板预览图片准备失败: error_type=%s", type(exc).__name__
                        )
                        node.content[index] = Plain(
                            "预览图暂时不可用，可稍后重试或在 WebUI 查看。"
                        )
            if failures:
                logger.warning(
                    "本次模板预览有 %s 张图片无法准备，已保留模板文字。", failures
                )
            return True, [event.chain_result([nodes])]
        logger.debug("[模板预览] 路由未处理: 缺少通用预览服务或图片缓存")
        return False, []
