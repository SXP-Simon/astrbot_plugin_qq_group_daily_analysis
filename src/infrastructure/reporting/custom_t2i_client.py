"""通过官方兼容 HTTP 接口调用自定义 T2I 服务。"""

import asyncio

import httpx

from ..config.rendering_config import normalize_t2i_endpoint
from .render_diagnostics import diagnose_non_image_payload


async def render_custom_t2i(
    endpoint: str, html: str, options: dict[str, object], token: str = ""
) -> bytes:
    """提交已生成的 HTML，直接获取图片，不写临时文件或修改宿主配置。

    Args:
        endpoint: 兼容 /text2img/generate 的服务地址。
        html: 已生成的完整报告 HTML。
        options: 当前轮次的截图选项，包含毫秒超时。
        token: 可选的 Bearer Token。

    Returns:
        服务返回的 PNG 或 JPEG 图片数据。

    Raises:
        ValueError: 服务地址无效或响应不是图片。
        RuntimeError: 连接失败或服务返回非成功 HTTP 状态。
        TimeoutError: 本轮请求超过配置的超时。
    """
    endpoint = normalize_t2i_endpoint(endpoint)
    timeout_ms = options.get("timeout", 20000)
    timeout = (
        float(timeout_ms) / 1000
        if isinstance(timeout_ms, (int, float)) and timeout_ms > 0
        else 20.0
    )
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        # 自定义服务直接连接，避免本机请求被环境代理转发；TLS 校验保持开启。
        async with (
            asyncio.timeout(timeout),
            httpx.AsyncClient(trust_env=False, timeout=timeout) as client,
        ):
            response = await client.post(
                f"{endpoint}/generate",
                json={"html": html, "json": False, "options": options},
                headers=headers,
            )
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise TimeoutError(
            "自定义 T2I 服务等待超时，请查看服务日志或调整本轮超时"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError("无法连接自定义 T2I 服务，请检查地址和服务运行状态") from exc
    content = response.content
    if response.is_success and content.startswith((b"\xff\xd8", b"\x89PNG")):
        return content
    sample = content[:4096]
    if token:
        sample = sample.replace(token.encode("ascii"), b"[redacted]")
    diagnosis = diagnose_non_image_payload(sample)
    if not response.is_success:
        hint = "，请检查服务 Token" if response.status_code in (401, 403) else ""
        raise RuntimeError(
            f"自定义 T2I 服务返回 HTTP {response.status_code}{hint}。{diagnosis}"
        )
    raise ValueError(diagnosis)
