"""DashScope 绘图请求体与模型能力差异。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....utils.logger import logger

if TYPE_CHECKING:
    from .context import DrawingRequestContext


def build_dashscope_payload(
    context: DrawingRequestContext,
    prompt: str,
    data_uris: list[str],
    provider: dict[str, object],
) -> dict[str, object]:
    """构造 DashScope 请求体，并应用当前模型的组图及提示词限制。

    Args:
        context: 提供服务商配置回退的绘图上下文。
        prompt: 漫画生成提示词。
        data_uris: 已编码的角色参考图。
        provider: 当前服务商配置。

    Returns:
        使用多模态消息结构的 JSON 请求体。
    """
    model = str(context.get_provider_value("model", provider) or "")
    image_size = str(context.get_provider_value("image_size", provider) or "")
    aspect_ratio = str(context.get_provider_value("aspect_ratio", provider) or "")
    content: list[dict[str, str]] = [{"text": prompt}]
    reference_limit = provider.get("max_reference_images", 9)
    if not isinstance(reference_limit, (int, float, str)):
        reference_limit = 9
    try:
        dashscope_max_references = min(9, max(0, int(reference_limit)))
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
            normalized_size = custom_size.lower().replace("×", "*").replace("x", "*")
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
    image_count = provider.get("n", 1)
    if not isinstance(image_count, (int, float, str)):
        image_count = 1
    try:
        dashscope_n = max(1, min(dashscope_n_limit, int(image_count)))
    except (TypeError, ValueError):
        dashscope_n = 1
    parameters: dict[str, object] = {
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
    return {
        "model": model,
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": parameters,
    }


def resolve_dashscope_size(image_size: str, aspect_ratio: str) -> str:
    """将漫画尺寸和比例换算为 DashScope 的 size 格式。

    Args:
        image_size: 目标长边尺寸档位。
        aspect_ratio: 宽高比字符串；非法比例使用方形。

    Returns:
        以星号连接的宽高像素字符串。
    """
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
