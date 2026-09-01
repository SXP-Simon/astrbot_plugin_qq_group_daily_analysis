import base64
from typing import Any

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
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for image_bytes, mime in (images_data or [])[:14]:
        parts.append(
            {
                "inlineData": {
                    "mimeType": mime if mime.startswith("image/") else "image/png",
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                }
            }
        )
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {
                "image_size": image_size if image_size in {"1K", "2K", "4K"} else "2K",
                "aspect_ratio": context.get_provider_value("aspect_ratio", provider),
            },
        },
    }
    return await context.request_json(
        target_url,
        {"x-goog-api-key": context.get_provider_value("api_key", provider)},
        payload,
        context.get_provider_value("timeout", provider),
        "Google Gemini",
        provider,
    )
