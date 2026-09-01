import base64
from math import gcd
from typing import Any

import httpx

from ....utils.logger import logger
from .context import DrawingRequestContext


async def call_chat_api(
    context: DrawingRequestContext,
    prompt: str,
    images_data: list[tuple[bytes, str]] | None = None,
    provider: dict | None = None,
) -> bytes | None:
    provider = provider or {}
    raw_url = context.get_provider_value("api_url", provider)
    target_url = context.build_target_url(raw_url, "chat")

    api_key = context.get_provider_value("api_key", provider)
    model = context.get_provider_value("model", provider)

    timeout = context.get_provider_value("timeout", provider)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    raw_size = context.get_provider_value("image_size", provider)
    ar = context.get_provider_value("aspect_ratio", provider)
    resolved_size = context.resolve_size(raw_size, ar)

    # 将长宽比与分辨率要求显式追加到 prompt 结尾，防止 Chat 协议模型忽略
    width, height = map(int, resolved_size.split("x", 1))
    divisor = gcd(width, height)
    effective_aspect_ratio = f"{width // divisor}:{height // divisor}"
    if width > height:
        orientation = "Horizontal Landscape Orientation"
    elif width < height:
        orientation = "Vertical Portrait Orientation"
    else:
        orientation = "Square Orientation"
    full_prompt = f"{prompt}\n\n[Image Layout & Spec Requirements: Aspect Ratio {effective_aspect_ratio}, Resolution {resolved_size}, {orientation}]"

    content = []
    for img_bytes, mime in images_data or []:
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        )

    content.append({"type": "text", "text": full_prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }

    logger.info(
        f"[Comic] 发起 Chat API 请求 -> {context.sanitize_url(target_url)} (model={model}, size={resolved_size}, aspect_ratio={ar})..."
    )

    api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
    async with httpx.AsyncClient(
        timeout=api_timeout, proxy=context.get_request_proxy(provider)
    ) as client:
        resp = await client.post(target_url, headers=headers, json=payload)

        if resp.status_code != 200:
            snippet = resp.text[:500] if resp.text else "(空响应)"
            raise Exception(f"API 请求失败 [HTTP {resp.status_code}]: {snippet}")

        try:
            data = resp.json()
        except Exception:
            snippet = resp.text[:500] if resp.text else "(空正文)"
            raise Exception(
                f"API 未返回合法的 JSON [HTTP {resp.status_code}]: {snippet}"
            )

        image = await context.extract_image(data, context.get_request_proxy(provider))
        if image:
            return image

        raise Exception(
            f"无法从 Chat API 的回复中提取到图片: {context.summarize_response(data)}"
        )
