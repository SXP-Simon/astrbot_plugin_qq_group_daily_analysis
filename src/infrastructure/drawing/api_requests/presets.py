import base64
from typing import Any

import httpx

from ....utils.logger import logger
from .context import DrawingRequestContext


async def call_preset_api(
    context: DrawingRequestContext,
    prompt: str,
    images_data: list[tuple[bytes, str]] | None,
    provider: dict,
    provider_type: str,
) -> bytes | None:
    """调用使用专有请求格式的绘图供应商预设。"""
    api_key = context.get_provider_value("api_key", provider)
    api_base = str(context.get_provider_value("api_url", provider)).rstrip("/")
    model = context.get_provider_value("model", provider)
    timeout = context.get_provider_value("timeout", provider)
    image_size = str(context.get_provider_value("image_size", provider))
    aspect_ratio = context.get_provider_value("aspect_ratio", provider)
    output_format = context.get_provider_value("output_format", provider)
    data_uris = [
        f"data:{mime if mime.startswith('image/') else 'image/png'};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
        for image_bytes, mime in images_data or []
    ]
    headers = {"Authorization": f"Bearer {api_key}"}

    if provider_type == "agnes_ai":
        base = api_base or "https://apihub.agnes-ai.com"
        target_url = (
            f"{base}/images/generations"
            if "/v1" in base
            else f"{base}/v1/images/generations"
        )
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": context.resolve_size(image_size),
            "extra_body": {"response_format": output_format or "url"},
        }
        if data_uris:
            payload["extra_body"]["image"] = data_uris
        provider_name = "Agnes AI"
    elif provider_type == "xai":
        base = api_base or "https://api.x.ai"
        base = base if base.endswith("/v1") else f"{base}/v1"
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "resolution": image_size.lower()
            if image_size.upper() in {"1K", "2K"}
            else "2k",
            "response_format": output_format or "url",
        }
        target_url = f"{base}/images/generations"
        if data_uris:
            target_url = f"{base}/images/edits"
            image_items = [
                {"type": "image_url", "url": data_uri} for data_uri in data_uris[:5]
            ]
            payload["image" if len(image_items) == 1 else "images"] = (
                image_items[0] if len(image_items) == 1 else image_items
            )
        payload["aspect_ratio"] = aspect_ratio
        provider_name = "xAI"
    elif provider_type == "minimax":
        base = (api_base or "https://api.minimaxi.com").removesuffix("/v1")
        target_url = f"{base}/v1/image_generation"
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": "url",
            "n": 1,
            "aspect_ratio": aspect_ratio,
        }
        if data_uris:
            payload["subject_reference"] = [
                {"type": "character", "image_file": data_uri}
                for data_uri in data_uris[:9]
            ]
        provider_name = "MiniMax"
    elif provider_type == "doubao":
        base = api_base or "https://ark.cn-beijing.volces.com"
        endpoint = (
            "/api/plan/v3/images/generations"
            if provider.get("endpoint_mode") == "agent_plan"
            else "/api/v3/images/generations"
        )
        target_url = f"{base}{endpoint}"
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": "url",
            "output_format": output_format or "png",
            "watermark": False,
            "size": image_size.upper()
            if image_size.upper() in {"1K", "2K", "3K", "4K"}
            else context.resolve_size(image_size),
        }
        if data_uris:
            payload["image"] = data_uris[0] if len(data_uris) == 1 else data_uris[:14]
        provider_name = "豆包"
    elif provider_type == "sensenova":
        base = api_base or "https://token.sensenova.cn"
        target_url = (
            f"{base}/images/generations"
            if base.endswith("/v1")
            else f"{base}/v1/images/generations"
        )
        if data_uris:
            logger.info(
                "[Comic] SenseNova U1 Fast 不支持参考图，已忽略 %d 张。",
                len(data_uris),
            )
        size_map = {
            "1:1": "2048x2048",
            "16:9": "2752x1536",
            "9:16": "1536x2752",
            "4:3": "2368x1760",
            "3:4": "1760x2368",
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size_map.get(aspect_ratio, "2752x1536"),
            "n": 1,
        }
        provider_name = "SenseNova"
    elif provider_type == "dashscope":
        endpoint_mode = str(provider.get("endpoint_mode", "dashscope"))
        base = api_base or (
            "https://token-plan.cn-beijing.maas.aliyuncs.com"
            if endpoint_mode == "token_plan"
            else "https://dashscope.aliyuncs.com"
        )
        target_url = f"{base}/api/v1/services/aigc/multimodal-generation/generation"
        content: list[dict[str, str]] = [{"text": prompt}]
        content.extend({"image": data_uri} for data_uri in data_uris[:9])
        payload = {
            "model": model,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": {
                "size": resolve_dashscope_size(image_size, aspect_ratio),
                "n": 1,
                "watermark": False,
            },
        }
        provider_name = "DashScope"
    elif provider_type == "stepfun":
        return await call_stepfun_api(
            context, prompt, images_data, provider, api_key, model, timeout
        )
    else:
        raise ValueError(f"不支持的绘图供应商预设: {provider_type}")

    return await context.request_json(
        target_url, headers, payload, timeout, provider_name, provider
    )


async def call_stepfun_api(
    context: DrawingRequestContext,
    prompt: str,
    images_data: list[tuple[bytes, str]] | None,
    provider: dict,
    api_key: str,
    model: str,
    timeout: int | float,
) -> bytes | None:
    """调用阶跃星辰图片接口，图生图使用官方 multipart 字段。"""
    target_url = context.build_target_url(
        context.get_provider_value("api_url", provider), "images"
    )
    headers = {"Authorization": f"Bearer {api_key}"}
    api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)

    if images_data:
        target_url = target_url.replace("/generations", "/edits")
        image_bytes, mime = images_data[0]
        extension = mime.split("/")[-1] if "/" in mime else "png"
        form_data = {
            "model": model,
            "prompt": prompt,
            "response_format": "url",
        }
        files = {
            "image": (f"reference.{extension}", image_bytes, mime),
        }
        logger.info(
            f"[Comic] 发起阶跃星辰图生图请求 -> {context.sanitize_url(target_url)}"
        )
        async with httpx.AsyncClient(
            timeout=api_timeout, proxy=context.get_request_proxy(provider)
        ) as client:
            response = await client.post(
                target_url, headers=headers, data=form_data, files=files
            )
    else:
        payload = {
            "model": model,
            "prompt": prompt,
            "size": context.resolve_size(
                context.get_provider_value("image_size", provider)
            ),
            "response_format": "url",
        }
        logger.info(
            f"[Comic] 发起阶跃星辰文生图请求 -> {context.sanitize_url(target_url)}"
        )
        async with httpx.AsyncClient(
            timeout=api_timeout, proxy=context.get_request_proxy(provider)
        ) as client:
            response = await client.post(target_url, headers=headers, json=payload)

    if not 200 <= response.status_code < 300:
        message = response.text[:500] if response.text else "(空响应)"
        raise Exception(
            f"阶跃星辰 API 请求失败 [HTTP {response.status_code}]: {message}"
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise Exception("阶跃星辰 API 未返回合法 JSON") from exc
    image = await context.extract_image(data, context.get_request_proxy(provider))
    if image:
        return image
    raise Exception(f"阶跃星辰 API 返回格式异常: {context.summarize_response(data)}")


def resolve_dashscope_size(image_size: str, aspect_ratio: str) -> str:
    """将漫画尺寸和比例换算为 DashScope 的 size 格式。"""
    long_edge = {"1K": 1280, "2K": 2048, "4K": 4096}.get(image_size.upper(), 2048)
    try:
        width_ratio, height_ratio = (int(value) for value in aspect_ratio.split(":", 1))
        if width_ratio <= 0 or height_ratio <= 0:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        width_ratio, height_ratio = 1, 1
    if width_ratio >= height_ratio:
        width = long_edge
        height = round(long_edge * height_ratio / width_ratio / 16) * 16
    else:
        height = long_edge
        width = round(long_edge * width_ratio / height_ratio / 16) * 16
    return f"{max(512, width)}*{max(512, height)}"
