"""豆包绘图请求体的尺寸、参考图和模型能力约束。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....utils.logger import logger

if TYPE_CHECKING:
    from .context import DrawingRequestContext


def build_doubao_payload(
    context: DrawingRequestContext,
    prompt: str,
    data_uris: list[str],
    provider: dict[str, object],
) -> dict[str, object]:
    """构造豆包请求体，保持端点模型和不同版本的能力限制。

    Args:
        context: 提供配置回退与尺寸换算的绘图上下文。
        prompt: 漫画生成提示词。
        data_uris: 已编码的角色参考图。
        provider: 当前服务商配置。

    Returns:
        可直接交给公共 JSON 请求通道的请求体。
    """
    model = str(context.get_provider_value("model", provider) or "")
    image_size = str(context.get_provider_value("image_size", provider) or "")
    aspect_ratio = str(context.get_provider_value("aspect_ratio", provider) or "")
    output_format = str(context.get_provider_value("output_format", provider) or "")
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
        resolved_doubao_size = context.resolve_size(resolved_doubao_size, aspect_ratio)
    is_seedream_5_pro = (
        str(provider.get("model_capability") or "").lower() == "seedream_5_pro"
        or "seedream-5.0-pro" in model.lower()
        or "seedream-5-0-pro" in model.lower()
    )
    payload: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "response_format": "url",
        "output_format": output_format or "png",
        "watermark": bool(provider.get("watermark", False)),
        "size": resolved_doubao_size,
    }
    if data_uris:
        max_references = 10 if is_seedream_5_pro else 14
        reference_limit = provider.get("max_reference_images", max_references)
        if not isinstance(reference_limit, (int, float, str)):
            reference_limit = max_references
        try:
            max_references = min(
                max_references,
                max(0, int(reference_limit)),
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
        image_count = provider.get("sequential_max_images", 0)
        if not isinstance(image_count, (int, float, str)):
            image_count = 0
        try:
            sequential_max_images = int(image_count)
        except (TypeError, ValueError):
            sequential_max_images = 0
        if 1 <= sequential_max_images <= 12:
            payload["sequential_image_generation_options"] = {
                "max_images": sequential_max_images
            }
    elif sequential_mode == "auto":
        logger.info("[Comic] 豆包 Seedream 5.0 Pro 不支持组图生成，已忽略该配置。")
    return payload
