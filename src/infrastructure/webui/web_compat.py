"""
Web API 兼容层 (Web Compatibility Layer)

封装 AstrBot 核心 Web 接口导入与单测环境回退实现，并提供动态测试 Mock 代理。
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from astrbot.api.star import Context
else:
    try:
        from astrbot.api.star import Context
    except (ImportError, AttributeError):

        class Context:
            """AstrBot Context 抽象基类或回退别名。"""


_real_json_response: Any = None
_real_error_response: Any = None
_real_request: Any = None
_real_stream_response: Any = None

try:
    from astrbot.api.web import (
        error_response as _core_error_response,
    )
    from astrbot.api.web import (
        json_response as _core_json_response,
    )
    from astrbot.api.web import (
        request as _core_request,
    )
    from astrbot.api.web import (
        stream_response as _core_stream_response,
    )

    _real_json_response = _core_json_response
    _real_error_response = _core_error_response
    _real_request = _core_request
    _real_stream_response = _core_stream_response
except (ImportError, AttributeError):
    pass


class _RequestProxy:
    """动态 Request 代理对象，自动路由至真实环境或测试 Mock 目标。"""

    def _get_target(self) -> Any:
        """获取当前活跃的底层请求对象。

        Returns:
            若定位到测试 Mock 或核心请求对象则返回其实例，否则返回 None。
        """
        for mod_name, mod in list(sys.modules.items()):
            if mod and "infrastructure.webui" in mod_name:
                req = getattr(mod, "request", None)
                if req is not None and type(req).__name__ != "_RequestProxy":
                    return req
        if (
            _real_request is not None
            and type(_real_request).__name__ != "_RequestProxy"
        ):
            return _real_request
        return None

    def __getattr__(self, name: str) -> Any:
        """拦截并代理请求对象的属性访问。

        Args:
            name: 属性名。

        Returns:
            底层请求对象对应的属性值。

        Raises:
            AttributeError: 当属性名以私有前缀开头或底层目标不存在时抛出。
        """
        if name.startswith("_"):
            raise AttributeError(name)
        target = self._get_target()
        if target is None:
            raise AttributeError(f"'NoneType' object has no attribute '{name}'")
        return getattr(target, name)

    def __bool__(self) -> bool:
        """判定当前代理是否已绑定有效请求目标。

        Returns:
            若目标存在则为 True，否则为 False。
        """
        return bool(self._get_target())


request: Any = _RequestProxy()


def json_response(
    data: Any = None,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> Any:
    """构造 JSON HTTP 响应。

    Args:
        data: 响应数据载荷。
        status_code: HTTP 状态码。
        headers: 附加 HTTP 响应标头字典。

    Returns:
        AstrBot Web 响应对象或兼容字典结构。
    """
    if _real_json_response is not None:
        try:
            return _real_json_response(data, status_code=status_code, headers=headers)
        except TypeError:
            return _real_json_response(data)
    return {"status_code": status_code, "data": data}


def error_response(
    message: str = "",
    *,
    status_code: int = 400,
    data: Any = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """构造 Error HTTP 响应。

    Args:
        message: 错误描述文本。
        status_code: HTTP 错误状态码。
        data: 可选的附加错误载荷。
        headers: 附加 HTTP 响应标头字典。

    Returns:
        AstrBot Web 错误响应对象或兼容字典结构。
    """
    if _real_error_response is not None:
        try:
            return _real_error_response(
                message, status_code=status_code, data=data, headers=headers
            )
        except TypeError:
            return _real_error_response(message)
    return {"status_code": status_code, "message": message, "data": data}


def stream_response(
    content: Any = None,
    *,
    content_type: str = "text/event-stream",
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> Any:
    """构造流式 HTTP 响应（如 SSE 事件流）。

    Args:
        content: 异步生成器或流式迭代数据源。
        content_type: MIME 类型，默认为 text/event-stream。
        status_code: HTTP 状态码。
        headers: 附加 HTTP 响应标头字典。

    Returns:
        AstrBot Web 流式响应对象或原始数据源。
    """
    if _real_stream_response is not None:
        try:
            return _real_stream_response(
                content,
                content_type=content_type,
                status_code=status_code,
                headers=headers,
            )
        except TypeError:
            return _real_stream_response(content)
    return content


__all__ = [
    "Context",
    "error_response",
    "json_response",
    "request",
    "stream_response",
]
