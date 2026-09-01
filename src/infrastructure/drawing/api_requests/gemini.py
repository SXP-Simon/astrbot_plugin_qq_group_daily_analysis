import base64
import binascii
import re
from typing import Any

import httpx

from ....utils.logger import logger
from .context import DrawingRequestContext


async def call_gemini_api(
    context: DrawingRequestContext,
    prompt: str,
    images_data: list[tuple[bytes, str]] | None = None,
    provider: dict | None = None,
) -> bytes | None:
    """调用 Google Gemini Interactions 图片接口。

    Args:
        prompt: 图片生成或编辑提示词。
        images_data: 可选参考图片及其 MIME 类型列表，当前只使用第一张。

    Returns:
        最后一个模型输出中的图片二进制数据。

    Raises:
        Exception: 请求失败、响应不是 JSON 或响应中没有最终图片。
    """
    provider = provider or {}
    raw_url = context.get_provider_value("api_url", provider)
    target_url = context.build_target_url(raw_url, "gemini")
    api_key = context.get_provider_value("api_key", provider)
    model = context.get_provider_value("model", provider)
    timeout = context.get_provider_value("timeout", provider)
    aspect_ratio = context.get_provider_value("aspect_ratio", provider)

    raw_size = str(context.get_provider_value("image_size", provider)).strip()
    if raw_size.upper() in {"1K", "2K", "4K"}:
        image_size = raw_size.upper()
    elif re.fullmatch(r"\d+x\d+", raw_size.lower()):
        width, height = map(int, raw_size.lower().split("x", 1))
        longest_edge = max(width, height)
        if longest_edge <= 1024:
            image_size = "1K"
        elif longest_edge <= 2048:
            image_size = "2K"
        else:
            image_size = "4K"
    else:
        image_size = "1K"

    output_format = str(context.get_provider_value("output_format", provider)).lower()
    output_mime = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
    }.get(output_format)

    input_content: list[dict[str, str]] = [{"type": "text", "text": prompt}]
    reference_bytes = 0
    for image_bytes, mime in images_data or []:
        image_mime = mime if mime.startswith("image/") else "image/png"
        input_content.append(
            {
                "type": "image",
                "data": base64.b64encode(image_bytes).decode("ascii"),
                "mime_type": image_mime,
            }
        )
        reference_bytes += len(image_bytes)

    response_format: dict[str, str] = {
        "type": "image",
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
    }
    if output_mime:
        response_format["mime_type"] = output_mime

    payload: dict[str, Any] = {
        "model": model,
        "input": input_content,
        "response_format": response_format,
        "store": False,
    }
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    logger.info(
        f"[Comic] 发起 Gemini Interactions API 请求 -> {context.sanitize_url(target_url)} "
        f"(model={model}, image_size={image_size}, "
        f"aspect_ratio={aspect_ratio}, reference_bytes={reference_bytes})..."
    )
    api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
    async with httpx.AsyncClient(
        timeout=api_timeout, proxy=context.get_request_proxy(provider)
    ) as client:
        resp = await client.post(target_url, headers=headers, json=payload)

    if not 200 <= resp.status_code < 300:
        error_summary = resp.text[:500] if resp.text else "(空响应)"
        raise Exception(
            f"Gemini API 请求失败 [HTTP {resp.status_code}]: {error_summary}"
        )

    try:
        data = resp.json()
    except Exception:
        raise Exception(
            f"Gemini API 未返回合法的 JSON [HTTP {resp.status_code}]: "
            f"<body len={len(resp.content)}>"
        )

    steps = data.get("steps") if isinstance(data, dict) else None
    model_outputs = (
        [
            step
            for step in steps
            if isinstance(step, dict) and step.get("type") == "model_output"
        ]
        if isinstance(steps, list)
        else []
    )
    for step in reversed(model_outputs):
        content = step.get("content")
        if not isinstance(content, list):
            continue
        for item in reversed(content):
            if not isinstance(item, dict) or item.get("type") != "image":
                continue
            encoded = item.get("data")
            if not isinstance(encoded, str) or not encoded.strip():
                continue
            try:
                return context.decode_base64(encoded)
            except (ValueError, TypeError, binascii.Error) as exc:
                logger.debug(f"[Comic] 跳过无效 Gemini 最终图片: {exc}")

    # 当响应包含 steps 时，只在最终模型输出中回退提取图片，避免误取中间推理图。
    fallback_data: Any = model_outputs if isinstance(steps, list) else data
    image = await context.extract_image(
        fallback_data, context.get_request_proxy(provider)
    )
    if image:
        return image

    status = data.get("status") if isinstance(data, dict) else None
    raise Exception(
        f"Gemini API 未返回最终图片 (status={status or 'unknown'}): "
        f"{context.summarize_response(data)}"
    )
