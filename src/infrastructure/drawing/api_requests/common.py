from typing import Any

import httpx

from ....utils.logger import logger
from .context import DrawingRequestContext


async def post_json_for_image(
    context: DrawingRequestContext,
    target_url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int | float,
    provider_name: str,
    provider: dict,
) -> bytes | None:
    """发送 JSON 图片生成请求，并从响应中提取图片。"""
    headers["Content-Type"] = "application/json"
    api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
    logger.info(
        f"[Comic] 发起 {provider_name} 图片请求 -> {context.sanitize_url(target_url)}"
    )
    async with httpx.AsyncClient(
        timeout=api_timeout, proxy=context.get_request_proxy(provider)
    ) as client:
        response = await client.post(target_url, headers=headers, json=payload)
    if not 200 <= response.status_code < 300:
        message = response.text[:500] if response.text else "(空响应)"
        raise Exception(
            f"{provider_name} API 请求失败 [HTTP {response.status_code}]: {message}"
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise Exception(f"{provider_name} API 未返回合法 JSON") from exc
    image = await context.extract_image(data, context.get_request_proxy(provider))
    if image:
        return image
    raise Exception(
        f"{provider_name} API 返回格式异常: {context.summarize_response(data)}"
    )
