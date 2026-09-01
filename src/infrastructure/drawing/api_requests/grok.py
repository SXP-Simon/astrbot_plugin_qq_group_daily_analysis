import base64
from typing import Any

import httpx

from ....utils.logger import logger
from .context import DrawingRequestContext


async def call_grok_api(
    context: DrawingRequestContext,
    prompt: str,
    images_data: list[tuple[bytes, str]] | None = None,
    provider: dict | None = None,
) -> bytes | None:
    """调用 xAI Grok Imagine 官方图片接口。

    Args:
        prompt: 图片生成或编辑提示词。
        images_data: 可选参考图片及其 MIME 类型列表，当前只使用第一张。

    Returns:
        API 返回的图片二进制数据。

    Raises:
        Exception: 请求失败、响应不是 JSON 或响应中没有有效图片。
    """
    provider = provider or {}
    raw_url = context.get_provider_value("api_url", provider)
    target_url = context.build_target_url(raw_url, "grok")
    api_key = context.get_provider_value("api_key", provider)
    model = context.get_provider_value("model", provider)
    timeout = context.get_provider_value("timeout", provider)
    aspect_ratio = context.get_provider_value("aspect_ratio", provider)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response_format = (
        context.get_provider_value("response_format", provider) or "b64_json"
    )
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "response_format": response_format,
    }
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio

    reference_bytes = 0
    if images_data:
        if target_url.endswith("/generations"):
            target_url = target_url.removesuffix("/generations") + "/edits"
        image_bytes, mime = images_data[0]
        image_mime = mime if mime.startswith("image/") else "image/png"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload["image"] = {
            "type": "image_url",
            "url": f"data:{image_mime};base64,{encoded}",
        }
        reference_bytes = len(image_bytes)
    elif target_url.endswith("/edits"):
        target_url = target_url.removesuffix("/edits") + "/generations"

    logger.info(
        f"[Comic] 发起 Grok Images API 请求 -> {context.sanitize_url(target_url)} "
        f"(model={model}, aspect_ratio={aspect_ratio}, "
        f"reference_bytes={reference_bytes})..."
    )
    api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
    async with httpx.AsyncClient(
        timeout=api_timeout, proxy=context.get_request_proxy(provider)
    ) as client:
        resp = await client.post(target_url, headers=headers, json=payload)

    if not 200 <= resp.status_code < 300:
        error_summary = resp.text[:500] if resp.text else "(空响应)"
        raise Exception(f"Grok API 请求失败 [HTTP {resp.status_code}]: {error_summary}")

    try:
        data = resp.json()
    except Exception:
        raise Exception(
            f"Grok API 未返回合法的 JSON [HTTP {resp.status_code}]: "
            f"<body len={len(resp.content)}>"
        )

    image = await context.extract_image(data, context.get_request_proxy(provider))
    if image:
        return image

    raise Exception(f"Grok API 返回格式异常: {context.summarize_response(data)}")
