"""OpenAI Images 兼容接口的请求实现。

该文件负责在同一套 Images API 中区分文生图和图生图请求：没有参考图时使用
JSON 的 ``/images/generations``，有参考图时使用 multipart 的 ``/images/edits``。
它同时将预设中的 GPT Image 专属参数限制在对应模型和输出格式下，避免兼容端点
因未知字段拒绝请求。
"""

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
    """调用 OpenAI Images 兼容接口。

    文生图走 JSON，带参考图时切换为 multipart 的 edits 请求。供应商专属
    参数仅在显式配置时写入，以免把 GPT Image 的参数错误发送给兼容端点。
    """
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
    ar = context.get_provider_value("aspect_ratio", provider)
    resolved_size = context.resolve_size(raw_size, ar)
    output_format = context.get_provider_value("output_format", provider)

    payload: dict[str, Any] = {
        "prompt": prompt,
        "model": model,
        "n": 1,
        "size": resolved_size,
        "output_format": output_format,
    }

    # 优先使用预设中的 quality，保留 image_quality 以兼容旧版全局配置。
    # ``auto`` 只有用户在预设中显式选择时才会发送，避免改变旧版全局配置
    # 中 ``auto`` 表示“让服务端保持默认”的既有语义。
    configured_quality = str(provider.get("quality") or "").strip().lower()
    quality = (
        configured_quality
        or str(context.get_provider_value("image_quality", provider) or "")
        .strip()
        .lower()
    )
    should_send_quality = quality in {"low", "medium", "high"} or (
        configured_quality == "auto"
    )
    if should_send_quality:
        payload["quality"] = quality

    bg = context.get_provider_value("background", provider)
    is_gpt_image = str(model).lower().startswith("gpt-image")
    # background、压缩率和审核策略都是 GPT Image 专属字段。背景为 auto
    # 时不传，交由服务端按其默认策略处理。
    if is_gpt_image and bg and bg != "auto":
        payload["background"] = bg

    # 压缩率仅适用于 JPEG/WebP，审核策略留空时不传，确保其他 OpenAI
    # 兼容服务不会收到未知字段。
    response_format = str(provider.get("response_format") or "").strip()
    if response_format:
        payload["response_format"] = response_format
    try:
        output_compression = int(provider.get("output_compression", 0))
    except (TypeError, ValueError):
        output_compression = 0
    if is_gpt_image and output_compression > 0 and output_format in {"jpeg", "webp"}:
        payload["output_compression"] = min(output_compression, 100)
    moderation = str(provider.get("moderation") or "").strip()
    if is_gpt_image and moderation:
        payload["moderation"] = moderation

    # 某些中转服务只实现 generations；启用后显式丢弃角色参考图，避免请求
    # 被自动改写到不支持的 edits 端点。
    if provider.get("generations_only", False) and images_data:
        logger.info(
            "[Comic] OpenAI Images 已启用仅文生图模式，忽略 %d 张参考图。",
            len(images_data),
        )
        images_data = None

    # 模板的参考图数量是用户侧的主动限制。它在切换为 edits 前执行，因此
    # 设置为 0 会自然退回到文生图；无效输入则使用模板默认值 6。
    if images_data:
        try:
            max_references = max(0, int(provider.get("max_reference_images", 6)))
        except (TypeError, ValueError):
            max_references = 6
        if len(images_data) > max_references:
            logger.info(
                "[Comic] OpenAI Images 参考图数量从 %d 张限制为 %d 张。",
                len(images_data),
                max_references,
            )
        images_data = images_data[:max_references]

    if images_data and len(images_data) > 0:
        if target_url.endswith("/generations"):
            target_url = target_url.replace("/generations", "/edits")

        headers.pop(
            "Content-Type", None
        )  # 移除 JSON 的 Content-Type，让 httpx 自动设置为 multipart/form-data

        multipart_data: dict[str, str] = {
            "prompt": prompt,
            "model": model,
            "n": "1",
            "size": resolved_size,
            "output_format": output_format,
        }
        if should_send_quality:
            multipart_data["quality"] = quality
        if is_gpt_image and bg and bg != "auto":
            multipart_data["background"] = bg
        if response_format:
            multipart_data["response_format"] = response_format
        if (
            is_gpt_image
            and output_compression > 0
            and output_format in {"jpeg", "webp"}
        ):
            multipart_data["output_compression"] = str(min(output_compression, 100))
        if is_gpt_image and moderation:
            multipart_data["moderation"] = moderation

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
