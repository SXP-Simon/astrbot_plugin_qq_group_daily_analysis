from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import httpx

from ....utils.logger import logger

if TYPE_CHECKING:
    from .context import DrawingRequestContext


async def call_google_api(
    context: DrawingRequestContext,
    prompt: str,
    images_data: list[tuple[bytes, str]] | None,
    provider: dict,
) -> bytes | None:
    """调用 Google Gemini generateContent 官方接口。"""
    api_base = str(context.get_provider_value("api_url", provider)).rstrip("/")
    model = context.get_provider_value("model", provider)
    if ":generateContent" in api_base:
        target_url = api_base
    else:
        if not api_base:
            api_base = "https://generativelanguage.googleapis.com/v1beta"
        if not api_base.endswith(("/v1", "/v1beta")):
            api_base = f"{api_base}/v1beta"
        target_url = f"{api_base}/models/{model}:generateContent"

    image_size = str(context.get_provider_value("image_size", provider)).upper()
    parts: list[dict[str, object]] = [{"text": prompt}]
    for image_bytes, mime in (images_data or [])[:14]:
        parts.append(
            {
                "inlineData": {
                    "mimeType": mime if mime.startswith("image/") else "image/png",
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                }
            }
        )
    timeout_val = context.get_provider_value("timeout", provider)
    try:
        timeout = (
            float(str(timeout_val))
            if timeout_val is not None and str(timeout_val).strip()
            else 60.0
        )
    except (ValueError, TypeError):
        timeout = 60.0
    api_key = str(context.get_provider_value("api_key", provider) or "")
    aspect_ratio = str(context.get_provider_value("aspect_ratio", provider) or "16:9")

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {
                "image_size": image_size if image_size in {"1K", "2K", "4K"} else "2K",
                "aspect_ratio": aspect_ratio,
            },
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
    logger.info(
        f"[Comic] 发起 Google Gemini 图片请求 -> {context.sanitize_url(target_url)}"
    )
    async with httpx.AsyncClient(
        timeout=api_timeout, proxy=context.get_request_proxy(provider)
    ) as client:
        response = await client.post(target_url, headers=headers, json=payload)
    if not 200 <= response.status_code < 300:
        message = response.text[:500] if response.text else "(空响应)"
        raise Exception(
            f"Google Gemini API 请求失败 [HTTP {response.status_code}]: {message}"
        )
    try:
        data: object = response.json()
    except ValueError as exc:
        raise Exception("Google Gemini API 未返回合法 JSON") from exc

    # 只读取 generateContent 的最终图片字段，避免把思考签名当作图片。
    candidates = data.get("candidates") if isinstance(data, dict) else None
    for candidate in candidates if isinstance(candidates, list) else []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        response_parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(response_parts, list):
            continue
        for part in response_parts:
            if not isinstance(part, dict) or part.get("thought") is True:
                continue
            inline_data = part.get("inlineData", part.get("inline_data"))
            if not isinstance(inline_data, dict):
                continue
            mime_type = inline_data.get("mimeType", inline_data.get("mime_type"))
            encoded = inline_data.get("data")
            if not isinstance(mime_type, str) or not mime_type.lower().startswith(
                "image/"
            ):
                continue
            if not isinstance(encoded, str) or not encoded.strip():
                continue
            try:
                return context.decode_base64(encoded)
            except ValueError as exc:
                logger.debug(f"[Comic] 跳过无效 Google Gemini 最终图片: {exc}")
    raise Exception(
        f"Google Gemini API 未返回有效的最终图片: {context.summarize_response(data)}"
    )
