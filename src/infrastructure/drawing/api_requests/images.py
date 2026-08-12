from typing import Any

import httpx

from ....utils.logger import logger
from .context import DrawingRequestContext


async def call_images_api(
    context: DrawingRequestContext,
    prompt: str,
    images_data: list[tuple[bytes, str]] | None = None,
    provider: dict | None = None,
) -> bytes | None:
    provider = provider or {}
    raw_url = context.get_provider_value("api_url", provider)
    target_url = context.build_target_url(raw_url, "images")

    api_key = context.get_provider_value("api_key", provider)
    model = context.get_provider_value("model", provider)
    timeout = context.get_provider_value("timeout", provider)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    raw_size = context.get_provider_value("image_size", provider)
    resolved_size = context.resolve_size(raw_size)
    ar = context.get_provider_value("aspect_ratio", provider)
    output_format = context.get_provider_value("output_format", provider)

    payload: dict[str, Any] = {
        "prompt": prompt,
        "model": model,
        "n": 1,
        "size": resolved_size,
        "output_format": output_format,
    }

    # 添加可选控制参数
    quality = context.get_provider_value("image_quality", provider)
    if quality in {"low", "medium", "high"}:
        payload["quality"] = quality

    bg = context.get_provider_value("background", provider)
    if bg and bg != "auto":
        payload["background"] = bg

    if images_data and len(images_data) > 0:
        if target_url.endswith("/generations"):
            target_url = target_url.replace("/generations", "/edits")

        headers.pop(
            "Content-Type", None
        )  # 移除 JSON 的 Content-Type，让 httpx 自动设置为 multipart/form-data

        multipart_data = {
            "prompt": prompt,
            "model": model,
            "n": "1",
            "size": resolved_size,
            "output_format": output_format,
        }
        if quality in {"low", "medium", "high"}:
            multipart_data["quality"] = quality
        if bg and bg != "auto":
            multipart_data["background"] = bg

        files = []
        for index, (img_bytes, mime) in enumerate(images_data, start=1):
            ext = mime.split("/")[-1] if "/" in mime else "png"
            files.append(("image[]", (f"image_{index}.{ext}", img_bytes, mime)))

        logger.info(
            f"[Comic] 发起 Images API 请求 (含图) -> {context.sanitize_url(target_url)} "
            f"(model={model}, size={resolved_size}, aspect_ratio={ar}, "
            f"references={len(images_data)}, reference_bytes={sum(len(image[0]) for image in images_data)})..."
        )
        api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
        async with httpx.AsyncClient(
            timeout=api_timeout, proxy=context.get_request_proxy(provider)
        ) as client:
            resp = await client.post(
                target_url, headers=headers, data=multipart_data, files=files
            )
    else:
        logger.info(
            f"[Comic] 发起 Images API 请求 -> {context.sanitize_url(target_url)} (model={model}, size={resolved_size}, aspect_ratio={ar})..."
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
        raise Exception(f"API 未返回合法的 JSON [HTTP {resp.status_code}]: {snippet}")

    image = await context.extract_image(data, context.get_request_proxy(provider))
    if image:
        return image

    raise Exception(f"API 返回格式异常: {context.summarize_response(data)}")
