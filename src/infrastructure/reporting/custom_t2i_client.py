"""通过官方兼容 HTTP 接口调用自定义 T2I 服务。"""

import asyncio
import warnings
from io import BytesIO

import httpx
from PIL import Image

from ..config.rendering_config import (
    DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS,
    ScreenshotOptions,
    normalize_t2i_endpoint,
)
from .render_diagnostics import diagnose_non_image_payload

_MAX_RESPONSE_BYTES = 32 * 1024 * 1024
_ERROR_SAMPLE_BYTES = 4096


def _validate_image(content: bytes) -> None:
    """在线程中验证图片完整性和解码，避免阻塞事件循环。

    Args:
        content: 已限制大小的服务响应。

    Returns:
        无返回值。

    Raises:
        ValueError: 数据损坏、格式不支持或像素数量超过 Pillow 安全阈值。
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in ("PNG", "JPEG"):
                    raise ValueError("不支持的图片格式")
                image.verify()
            # JPEG 的 verify 不解码像素，需要实际加载才能识别截断数据。
            with Image.open(BytesIO(content)) as image:
                image.load()
    except (
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise ValueError(
            "自定义 T2I 服务返回的图片损坏或过大，请查看服务日志"
        ) from None


async def render_custom_t2i(
    endpoint: str,
    html: str,
    options: ScreenshotOptions,
    token: str = "",
    *,
    request_timeout_ms: int = DEFAULT_CUSTOM_T2I_REQUEST_TIMEOUT_MS,
) -> bytes:
    """提交完整 HTML，流式获取并验证图片，不修改宿主配置。

    Args:
        endpoint: 兼容 /text2img/generate 的服务地址。
        html: 已生成的完整报告 HTML。
        options: 当前轮次的强类型T2I选项，包含毫秒超时。
        token: 可选的 Bearer Token；鉴权请求不回显服务错误正文。
        request_timeout_ms: 整次请求的等待上限，独立于传给服务的T2I超时。

    Returns:
        不超过 32 MiB 且验证完整、可解码的 PNG 或 JPEG 图片。

    Raises:
        ValueError: 地址无效、响应过大、不是图片或图片损坏。
        RuntimeError: 连接失败或服务返回非成功 HTTP 状态。
        TimeoutError: 本轮请求超过配置的超时。
    """
    endpoint = normalize_t2i_endpoint(endpoint)
    timeout = request_timeout_ms / 1000
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    content = bytearray()
    status = 0
    success = False
    try:
        # 管理员可指定 Docker 或内网 HTTP 服务；跨网络部署应配置 HTTPS。
        async with (
            asyncio.timeout(timeout),
            httpx.AsyncClient(trust_env=False, timeout=timeout) as client,
        ):
            async with client.stream(
                "POST",
                f"{endpoint}/generate",
                json={"html": html, "json": False, "options": options},
                headers=headers,
            ) as response:
                status = response.status_code
                success = response.is_success
                declared_size = response.headers.get("content-length", "")
                if (
                    success
                    and declared_size.isdecimal()
                    and int(declared_size) > _MAX_RESPONSE_BYTES
                ):
                    raise ValueError("自定义 T2I 服务返回的图片超过 32 MiB，已停止接收")
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    if not success:
                        content.extend(chunk[:_ERROR_SAMPLE_BYTES])
                        break
                    if len(content) + len(chunk) > _MAX_RESPONSE_BYTES:
                        raise ValueError(
                            "自定义 T2I 服务返回的图片超过 32 MiB，已停止接收"
                        )
                    content.extend(chunk)
                    if len(content) >= 8 and not content.startswith(
                        (b"\xff\xd8", b"\x89PNG")
                    ):
                        del content[_ERROR_SAMPLE_BYTES:]
                        break
            data = bytes(content)
            if success and data.startswith((b"\xff\xd8", b"\x89PNG")):
                await asyncio.to_thread(_validate_image, data)
                return data
    except (TimeoutError, httpx.TimeoutException):
        raise TimeoutError(
            f"自定义 T2I 服务等待超过 {timeout:g} 秒，请查看服务日志或调整本轮请求等待上限"
        ) from None
    except httpx.RequestError:
        raise RuntimeError(
            "无法连接自定义 T2I 服务，请检查地址和服务运行状态"
        ) from None
    # 有 Token 时不回显任何服务错误正文，避免转义、截断和编码变化泄漏凭据。
    diagnosis = (
        "服务未返回可用图片，请查看 T2I 服务日志。"
        if token
        else diagnose_non_image_payload(bytes(content[:_ERROR_SAMPLE_BYTES]))
    )
    if not success:
        hint = "，请检查服务 Token" if status in (401, 403) else ""
        raise RuntimeError(f"自定义 T2I 服务返回 HTTP {status}{hint}。{diagnosis}")
    raise ValueError(diagnosis)
