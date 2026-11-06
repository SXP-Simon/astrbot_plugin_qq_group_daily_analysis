"""AstrBot HTML 渲染回调的会话配置兼容适配。"""

from __future__ import annotations

from functools import partial
from inspect import Parameter, ismethod, signature
from typing import TYPE_CHECKING, TypedDict, TypeVar
from urllib.parse import urlsplit, urlunsplit

from ...shared.type_guards import is_string_mapping

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from astrbot.api.star import Context

RenderResult = TypeVar("RenderResult")


class RenderServiceInfo(TypedDict):
    """宿主渲染配置的只读诊断信息。"""

    config_lookup: str
    configured_endpoint: str


def describe_html_renderer(
    render_func: Callable[..., Awaitable[object]],
) -> RenderServiceInfo:
    """只读查询宿主渲染配置，提供日志与任务详情所需的诊断信息。

    Args:
        render_func: 可能已通过 partial 绑定群聊会话的宿主回调。

    Returns:
        配置查询方式和脱敏后的配置地址。默认地址池不推断实际请求地址；
        旧版或第三方回调无法查询时仅说明限制，不影响后续渲染。
    """
    info: RenderServiceInfo = {
        "config_lookup": "无法读取此回调的宿主配置",
        "configured_endpoint": "未知，请查看 AstrBot 日志中的实际请求地址",
    }
    try:
        umo = None
        if isinstance(render_func, partial):
            umo = render_func.keywords.get("umo")
            render_func = render_func.func
        if not ismethod(render_func):
            return info
        # 只在宿主接口边界读取 Context，不修改配置或额外发起请求。
        context: Context | None = getattr(render_func.__self__, "context", None)
        if context is None or not callable(getattr(context, "get_config", None)):
            return info
        if "umo" not in signature(render_func).parameters:
            info["config_lookup"] = "旧版渲染接口，由宿主选择服务地址"
            return info
        session = umo if isinstance(umo, str) and umo else None
        config = context.get_config(session)
        info["config_lookup"] = (
            "按群聊会话查询，未绑定时由宿主回退默认配置" if session else "默认配置"
        )
        endpoint = config.get("t2i_endpoint") if is_string_mapping(config) else None
        if not endpoint:
            info["configured_endpoint"] = (
                "未单独配置，使用宿主默认地址池；实际请求地址由宿主选择"
            )
        elif isinstance(endpoint, str):
            parsed = urlsplit(endpoint)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                info["configured_endpoint"] = "配置地址格式异常，请检查 T2I 地址"
            else:
                # 保留定位服务所需的主机、端口和路径，隐藏认证与查询参数。
                host = parsed.hostname
                if ":" in host:
                    host = f"[{host}]"
                if parsed.port is not None:
                    host += f":{parsed.port}"
                address = urlunsplit((parsed.scheme, host, parsed.path, "", ""))
                info["configured_endpoint"] = "".join(
                    char for char in address if char.isprintable()
                )[:300]
        else:
            info["configured_endpoint"] = "配置地址不是字符串，请检查 T2I 地址"
    except Exception as exc:
        info["configured_endpoint"] = (
            f"无法读取配置地址（{type(exc).__name__}），仍按原方式调用宿主渲染接口"
        )
    return info


def bind_group_html_renderer(
    render_func: Callable[..., Awaitable[RenderResult]] | None,
    group_id: str,
    platform_id: str | None,
) -> Callable[..., Awaitable[RenderResult]] | None:
    """按群聊绑定渲染配置，兼容不接受 umo 的旧版 AstrBot。

    Args:
        render_func: 宿主提供的 HTML 渲染回调。
        group_id: 目标群组标识。
        platform_id: 平台实例标识；缺失时沿用宿主默认配置。

    Returns:
        仅为本次报告绑定会话的回调；旧版或无法检查签名时返回原回调。
    """
    if render_func is None or not group_id or not platform_id:
        return render_func
    try:
        parameters = signature(render_func).parameters
    except (TypeError, ValueError):
        return render_func
    umo_parameter = parameters.get("umo")
    if (
        umo_parameter is not None
        and umo_parameter.kind
        in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
    ) or any(p.kind == Parameter.VAR_KEYWORD for p in parameters.values()):
        return partial(render_func, umo=f"{platform_id}:GroupMessage:{group_id}")
    return render_func
