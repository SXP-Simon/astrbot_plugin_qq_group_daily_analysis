"""漫画绘图供应商预设的请求体构造。

本模块只处理各家官方接口不兼容的字段、端点和能力约束；通用 HTTP
发送、重试以及图片响应提取仍由上层服务统一负责。这样新增预设时只需
在对应分支描述其请求格式，不会把服务商细节重新堆回 DrawingClient。
"""

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
    """调用使用专有请求格式的绘图供应商预设。

    Args:
        context: 由绘图客户端提供的公共配置、代理和响应处理能力。
        prompt: 本次漫画分镜的提示词。
        images_data: 已读取的角色参考图片二进制数据。
        provider: 当前供应商模板保存后的配置。
        provider_type: 预设类型，用于选择官方接口格式。

    Returns:
        成功时返回图片二进制数据，没有图片时返回 ``None``。

    Raises:
        ValueError: 供应商预设类型不受支持时抛出。
    """
    api_key = context.get_provider_value("api_key", provider)
    api_base = str(context.get_provider_value("api_url", provider)).rstrip("/")
    model = context.get_provider_value("model", provider)
    timeout = context.get_provider_value("timeout", provider)
    image_size = str(context.get_provider_value("image_size", provider))
    aspect_ratio = context.get_provider_value("aspect_ratio", provider)
    output_format = context.get_provider_value("output_format", provider)
    # 各个原生 JSON 接口都可接收 data URI。这里统一转换一次，后续分支只
    # 负责自己的字段语义和参考图数量上限。
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
            "size": context.resolve_size(image_size, aspect_ratio),
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
        configured_model = str(provider.get("endpoint_id") or model).strip()
        model = configured_model or model
        size_mode = str(provider.get("size_mode") or "preset").strip().lower()
        configured_size = (
            provider.get("custom_size")
            if size_mode == "custom"
            else provider.get("size") or image_size
        )
        resolved_doubao_size = str(configured_size or image_size).strip()
        if "x" in resolved_doubao_size.lower() or "×" in resolved_doubao_size:
            resolved_doubao_size = resolved_doubao_size.lower().replace("×", "x")
        elif resolved_doubao_size.upper() not in {"1K", "2K", "3K", "4K"}:
            resolved_doubao_size = context.resolve_size(
                resolved_doubao_size, aspect_ratio
            )
        is_seedream_5_pro = (
            str(provider.get("model_capability") or "").lower() == "seedream_5_pro"
            or "seedream-5.0-pro" in model.lower()
            or "seedream-5-0-pro" in model.lower()
        )
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "response_format": "url",
            "output_format": output_format or "png",
            "watermark": bool(provider.get("watermark", False)),
            "size": resolved_doubao_size,
        }
        if data_uris:
            max_references = 10 if is_seedream_5_pro else 14
            try:
                max_references = min(
                    max_references,
                    max(0, int(provider.get("max_reference_images", max_references))),
                )
            except (TypeError, ValueError):
                pass
            selected_images = data_uris[:max_references]
            if selected_images:
                payload["image"] = (
                    selected_images[0] if len(selected_images) == 1 else selected_images
                )
        optimize_mode = str(provider.get("optimize_prompt_mode") or "").strip()
        if optimize_mode in {"standard", "fast"}:
            payload["optimize_prompt_options"] = {"mode": optimize_mode}
        sequential_mode = provider.get("sequential_image_generation")
        if sequential_mode == "auto" and not is_seedream_5_pro:
            payload["sequential_image_generation"] = "auto"
            try:
                sequential_max_images = int(provider.get("sequential_max_images", 0))
            except (TypeError, ValueError):
                sequential_max_images = 0
            if 1 <= sequential_max_images <= 12:
                payload["sequential_image_generation_options"] = {
                    "max_images": sequential_max_images
                }
        elif sequential_mode == "auto":
            logger.info("[Comic] 豆包 Seedream 5.0 Pro 不支持组图生成，已忽略该配置。")
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
        # U1 Fast 仅接受官方枚举尺寸，宽高比不能映射时使用用户配置的默认
        # 尺寸，仍不合法时再回退到官方横版默认值。
        size_map = {
            "1:1": "2048x2048",
            "2:3": "1664x2496",
            "3:2": "2496x1664",
            "16:9": "2752x1536",
            "9:16": "1536x2752",
            "4:3": "2368x1760",
            "3:4": "1760x2368",
            "4:5": "1824x2272",
            "5:4": "2272x1824",
            "21:9": "3072x1376",
            "9:21": "1344x3136",
        }
        default_size = str(provider.get("default_size") or "2752x1536").lower()
        allowed_sizes = set(size_map.values())
        resolved_sensenova_size = size_map.get(str(aspect_ratio), default_size)
        if resolved_sensenova_size not in allowed_sizes:
            logger.warning(
                "[Comic] SenseNova 默认尺寸 %s 不受支持，回退为 2752x1536。",
                resolved_sensenova_size,
            )
            resolved_sensenova_size = "2752x1536"
        try:
            sensenova_n = max(1, min(4, int(provider.get("n", 1))))
        except (TypeError, ValueError):
            sensenova_n = 1
        payload = {
            "model": model,
            "prompt": prompt,
            "size": resolved_sensenova_size,
            "n": sensenova_n,
        }
        provider_name = "SenseNova"
    elif provider_type == "dashscope":
        endpoint_mode = str(provider.get("endpoint_mode", "dashscope"))
        base = api_base or (
            "https://token-plan.cn-beijing.maas.aliyuncs.com"
            if endpoint_mode == "token_plan"
            else "https://dashscope.aliyuncs.com"
        )
        clean_base = base.rstrip("/")
        if clean_base.endswith("/api/v1"):
            clean_base = clean_base[:-7].rstrip("/")
        elif clean_base.endswith("/v1"):
            clean_base = clean_base[:-3].rstrip("/")
        target_url = (
            f"{clean_base}/api/v1/services/aigc/multimodal-generation/generation"
        )
        content: list[dict[str, str]] = [{"text": prompt}]
        try:
            dashscope_max_references = min(
                9, max(0, int(provider.get("max_reference_images", 9)))
            )
        except (TypeError, ValueError):
            dashscope_max_references = 9
        content.extend(
            {"image": data_uri} for data_uri in data_uris[:dashscope_max_references]
        )
        size_mode = str(provider.get("size_mode") or "preset").strip().lower()
        custom_size = str(provider.get("custom_size") or "").strip()
        if size_mode == "custom" and custom_size:
            normalized_size = custom_size.upper()
            if normalized_size not in {"1K", "2K", "4K"}:
                normalized_size = (
                    custom_size.lower().replace("×", "*").replace("x", "*")
                )
            dashscope_size = normalized_size
        else:
            dashscope_size = resolve_dashscope_size(image_size, aspect_ratio)
        is_wan27 = str(model).startswith("wan2.7")
        enable_sequential = is_wan27 and bool(provider.get("enable_sequential", False))
        if enable_sequential:
            dashscope_n_limit = 12
        elif is_wan27:
            dashscope_n_limit = 4
        elif str(model).startswith("qwen-image-2.0"):
            dashscope_n_limit = 6
        else:
            dashscope_n_limit = 1
        try:
            dashscope_n = max(1, min(dashscope_n_limit, int(provider.get("n", 1))))
        except (TypeError, ValueError):
            dashscope_n = 1
        parameters: dict[str, Any] = {
            "size": dashscope_size,
            "n": dashscope_n,
            "watermark": bool(provider.get("watermark", False)),
        }
        negative_prompt = str(provider.get("negative_prompt") or "").strip()
        if negative_prompt and not is_wan27:
            parameters["negative_prompt"] = negative_prompt
        elif negative_prompt:
            logger.info("[Comic] DashScope wan2.7 不支持负面提示词，已忽略该配置。")
        if is_wan27:
            if enable_sequential:
                parameters["enable_sequential"] = True
            else:
                parameters["thinking_mode"] = bool(provider.get("thinking_mode", True))
        else:
            parameters["prompt_extend"] = bool(provider.get("prompt_extend", False))
        payload = {
            "model": model,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": parameters,
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
                context.get_provider_value("image_size", provider),
                context.get_provider_value("aspect_ratio", provider),
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
