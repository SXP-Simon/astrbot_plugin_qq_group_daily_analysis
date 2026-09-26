"""Web API 兼容层 (Web Compatibility Layer)

封装 AstrBot 核心 Web 接口导入与单测环境回退实现，并提供动态测试 Mock 代理与请求协议契约。
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Protocol, TypeAlias, runtime_checkable

if TYPE_CHECKING:
    from fastapi.responses import FileResponse, JSONResponse, Response
    from starlette.responses import StreamingResponse

    WebApiResponse: TypeAlias = (
        JSONResponse | StreamingResponse | FileResponse | Response | dict[str, object]
    )
else:
    try:
        from fastapi.responses import FileResponse, JSONResponse, Response
        from starlette.responses import StreamingResponse

        WebApiResponse = (
            JSONResponse
            | StreamingResponse
            | FileResponse
            | Response
            | dict[str, object]
        )
    except ImportError:
        WebApiResponse = dict[str, object]


_real_json_response: object = None
_real_error_response: object = None
_real_request: object = None
_real_stream_response: object = None

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


@runtime_checkable
class RequestProtocol(Protocol):
    """Web 请求对象结构化契约协议。"""

    @property
    def query(self) -> dict[str, str]:
        """查询参数字典。"""
        ...

    @property
    def headers(self) -> dict[str, str]:
        """HTTP 请求标头字典。"""
        ...

    @property
    def query_params(self) -> dict[str, str]:
        """Starlette/FastAPI 查询参数兼容字典。"""
        ...

    @property
    def files(self) -> dict[str, object]:
        """上传文件映射字典。"""
        ...

    async def json(self) -> dict[str, object]:
        """异步解析 JSON 请求体。"""
        ...


class _RequestProxy:
    """动态 Request 代理对象，自动路由至真实环境或测试 Mock 目标。"""

    def _get_target(self) -> object:
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

    @property
    def query(self) -> dict[str, str]:
        """获取查询参数字典。"""
        target = self._get_target()
        if target is None:
            return {}
        res = getattr(target, "query", None)
        if res is not None:
            if isinstance(res, dict):
                return dict(res)
            if hasattr(res, "items"):
                return {str(k): str(v) for k, v in res.items()}
            if hasattr(res, "_pairs"):
                pairs = getattr(res, "_pairs", [])
                return {str(k): str(v) for k, v in pairs}
            try:
                return dict(res)
            except Exception:
                pass
        res_params = getattr(target, "query_params", None)
        if res_params is not None:
            if isinstance(res_params, dict):
                return dict(res_params)
            if hasattr(res_params, "items"):
                return {str(k): str(v) for k, v in res_params.items()}
            try:
                return dict(res_params)
            except Exception:
                pass
        return {}

    @property
    def query_params(self) -> dict[str, str]:
        """获取兼容的查询参数字典。"""
        return self.query

    @property
    def headers(self) -> dict[str, str]:
        """获取请求标头字典。"""
        target = self._get_target()
        if target is None:
            return {}
        res = getattr(target, "headers", None)
        if res is not None:
            if isinstance(res, dict):
                return dict(res)
            if hasattr(res, "items"):
                return {str(k): str(v) for k, v in res.items()}
            try:
                return dict(res)
            except Exception:
                pass
        return {}

    @property
    def files(self) -> dict[str, object]:
        """获取上传文件映射字典。"""
        target = self._get_target()
        if target is None:
            return {}
        res = getattr(target, "files", None)
        if res is not None:
            if isinstance(res, dict):
                return dict(res)
            if hasattr(res, "items") and not callable(res):
                return dict(res.items())
        return {}

    async def json(self) -> dict[str, object]:
        """异步读取 JSON 请求体。"""
        target = self._get_target()
        if target is None:
            return {}
        fn = getattr(target, "json", None)
        if callable(fn):
            import inspect

            try:
                res = fn()
                if inspect.isawaitable(res):
                    res = await res
                if isinstance(res, dict):
                    return dict(res)
            except Exception:
                pass
        body_attr = getattr(target, "body", None) or getattr(target, "_body", None)
        if body_attr is not None:
            try:
                import inspect
                import json

                if callable(body_attr):
                    b = body_attr()
                    if inspect.isawaitable(b):
                        b = await b
                else:
                    b = body_attr
                if isinstance(b, bytes):
                    b = b.decode("utf-8", errors="replace")
                if isinstance(b, str) and b.strip():
                    parsed = json.loads(b)
                    if isinstance(parsed, dict):
                        return parsed
            except Exception:
                pass
        return {}

    def __getattr__(self, name: str) -> object:
        """拦截并代理请求对象的未知属性访问。

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


request: RequestProtocol = _RequestProxy()


def json_response(
    data: object = None,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> WebApiResponse:
    """构造 JSON HTTP 响应。

    Args:
        data: 响应数据载荷。
        status_code: HTTP 状态码。
        headers: 附加 HTTP 响应标头字典。

    Returns:
        AstrBot Web 响应对象或兼容字典结构。
    """
    if _real_json_response is not None and callable(_real_json_response):
        try:
            return _real_json_response(data, status_code=status_code, headers=headers)  # type: ignore[no-any-return, return-value]
        except TypeError:
            return _real_json_response(data)  # type: ignore[no-any-return, return-value]
    return {"status_code": status_code, "data": data}


def error_response(
    message: str = "",
    *,
    status_code: int = 400,
    data: object = None,
    headers: dict[str, str] | None = None,
) -> WebApiResponse:
    """构造 Error HTTP 响应。

    Args:
        message: 错误描述文本。
        status_code: HTTP 错误状态码。
        data: 可选的附加错误载荷。
        headers: 附加 HTTP 响应标头字典。

    Returns:
        AstrBot Web 错误响应对象或兼容字典结构。
    """
    if _real_error_response is not None and callable(_real_error_response):
        try:
            return _real_error_response(  # type: ignore[no-any-return, return-value]
                message, status_code=status_code, data=data, headers=headers
            )
        except TypeError:
            return _real_error_response(message)  # type: ignore[no-any-return, return-value]
    return {"status_code": status_code, "message": message, "data": data}


def stream_response(
    content: object = None,
    *,
    content_type: str = "text/event-stream",
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> WebApiResponse:
    """构造流式 HTTP 响应（如 SSE 事件流）。

    Args:
        content: 异步生成器或流式迭代数据源。
        content_type: MIME 类型，默认为 text/event-stream。
        status_code: HTTP 状态码。
        headers: 附加 HTTP 响应标头字典。

    Returns:
        AstrBot Web 流式响应对象或原始数据源。
    """
    if _real_stream_response is not None and callable(_real_stream_response):
        try:
            return _real_stream_response(  # type: ignore[no-any-return, return-value]
                content,
                content_type=content_type,
                status_code=status_code,
                headers=headers,
            )
        except TypeError:
            return _real_stream_response(content)  # type: ignore[no-any-return, return-value]
    return {"status_code": status_code, "content": content}
