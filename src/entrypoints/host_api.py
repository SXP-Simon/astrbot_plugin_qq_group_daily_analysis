"""补全宿主入口中尚未标注的调用契约，运行时仍使用 AstrBot 原方法。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from astrbot.api.event.filter import (
        EventMessageType,
        PermissionType,
        PlatformAdapterType,
    )
    from astrbot.api.star import Context


class HandlerDecorator(Protocol):
    """宿主注册装饰器保留被注册函数的签名。"""

    def __call__[F: Callable[..., object]](self, handler: F) -> F: ...


class EventFilters(Protocol):
    """当前插件使用的 AstrBot 事件注册入口。"""

    EventMessageType: type[EventMessageType]
    PlatformAdapterType: type[PlatformAdapterType]

    def command(self, command_name: str, *, alias: set[str]) -> HandlerDecorator: ...
    def permission_type(self, permission_type: PermissionType) -> HandlerDecorator: ...
    def event_message_type(
        self, event_message_type: EventMessageType, **kwargs: object
    ) -> HandlerDecorator: ...
    def platform_adapter_type(
        self, platform_adapter_type: PlatformAdapterType
    ) -> HandlerDecorator: ...
    def on_platform_loaded(self) -> HandlerDecorator: ...
    def llm_tool(self, name: str) -> HandlerDecorator: ...


class StarInitializer(Protocol):
    """插件仅向 Star 构造器传递 Context。"""

    def __init__(self, context: Context) -> None: ...


class HostHtmlRenderer(Protocol):
    """宿主模板渲染方法；转换类型不会包装函数，保留运行时签名检查。"""

    @property
    def html_render(self) -> Callable[..., Awaitable[str]]: ...
