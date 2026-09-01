"""漫画绘图客户端的高层调度入口。

``DrawingClient`` 保留插件既有的私有兼容入口，供调用方和扩展继续使用；实际
供应商请求与图片响应分别委托给两个组合服务。客户端只保留供应商回退、重试和
全局配置读取，避免 HTTP 协议细节再次集中到一个过大的类中。
"""

import asyncio
import re
from typing import Any

import httpx

from ...utils.logger import logger
from ..config.config_manager import ConfigManager
from .api_requests import DrawingApiRequestService
from .api_requests.context import DrawingRequestContext
from .api_requests.presets import resolve_dashscope_size
from .drawing_image_response import (
    DrawingImageResponseService,
    ImageDownloadFailedError,
)

__all__ = ["DrawingClient", "ImageDownloadFailedError"]


# 供应商条目是唯一的连接配置来源。这里的默认值只用于兼容手工编辑的缺失字段，
# 不再读取配置面板中已移除的外层绘图参数。
DRAWING_PROVIDER_DEFAULTS: dict[str, Any] = {
    "api_url": "",
    "api_key": "",
    "model": "gpt-image-2",
    "api_protocol": "images",
    "image_size": "1024x1024",
    "aspect_ratio": "16:9",
    "image_quality": "high",
    "background": "auto",
    "output_format": "png",
    "timeout": 600,
}


class DrawingClient:
    """协调绘图供应商选择、重试、请求服务和图片响应处理。

    服务对象通过 ``DrawingRequestContext`` 显式获取所需能力，而不是继承
    客户端内部状态。私有兼容入口仍保留为薄转发层，确保既有扩展和测试替换
    ``_post_json_for_image`` 等方法时能够继续生效。
    """

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._image_response_service = DrawingImageResponseService(
            hooks=self,
            # 保持实例替换下载方法时，响应服务也会使用替换后的实现。
            download_image=lambda url, proxy: self.download_public_image(url, proxy),
        )
        self._request_service = DrawingApiRequestService(
            DrawingRequestContext(
                hooks=self,
                # 保持既有测试和扩展对兼容入口的动态替换能力。
                request_json=lambda *args: self._post_json_for_image(*args),
                extract_image=lambda data, proxy: self._extract_image_from_response(
                    data, proxy
                ),
            )
        )

    def _build_target_url(self, raw_url: str, protocol: str) -> str:
        """智能解析补全用户配置的 API URL。"""
        url = (raw_url or "").strip().rstrip("/")
        if not url:
            if protocol == "grok":
                url = "https://api.x.ai"
            elif protocol == "gemini":
                url = "https://generativelanguage.googleapis.com"
            else:
                url = "https://api.openai.com/v1"

        if protocol == "images":
            if url.endswith("/images/generations"):
                return url
            if url.endswith("/v1"):
                return f"{url}/images/generations"
            if "/v1/" in url:
                return url if "images" in url else f"{url}/images/generations"
            return f"{url}/v1/images/generations"
        if protocol == "chat":
            if url.endswith("/chat/completions"):
                return url
            if url.endswith("/v1"):
                return f"{url}/chat/completions"
            if "/v1/" in url:
                return url if "chat" in url else f"{url}/chat/completions"
            return f"{url}/v1/chat/completions"
        if protocol == "grok":
            if url.endswith(("/images/generations", "/images/edits")):
                return url
            if url.endswith("/v1"):
                return f"{url}/images/generations"
            if "/v1/" in url:
                return url if "/images/" in url else f"{url}/images/generations"
            return f"{url}/v1/images/generations"
        if protocol == "gemini":
            if url.endswith("/interactions"):
                return url
            if url.endswith(("/v1beta", "/v1")):
                return f"{url}/interactions"
            return f"{url}/v1beta/interactions"
        raise ValueError(f"不支持的绘图 API 协议: {protocol}")

    async def generate_image(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        disable_retry: bool = False,
    ) -> tuple[bytes | None, str | None]:
        """调用候选供应商生成单张图片。

        Args:
            prompt: 用于生成图片的提示词。
            images_data: 可选参考图片及其 MIME 类型。
            disable_retry: 是否禁用请求失败后的重试。

        Returns:
            图片二进制数据与最后一次错误信息组成的元组。
        """
        provider_configs = self.config_manager.get_drawing_provider_configs()
        if not provider_configs:
            message = "未配置有效的漫画绘图供应商，请在绘图供应商配置表中添加条目。"
            logger.warning("[Comic] %s", message)
            return None, message

        last_error_msg = None
        last_download_error: ImageDownloadFailedError | None = None
        for provider in provider_configs:
            try:
                result, last_error_msg = await self._generate_image_with_provider(
                    prompt, images_data, disable_retry, provider
                )
            except ImageDownloadFailedError as exc:
                # 图片已经由上游生成，但当前候选返回的 URL 无法下载；继续尝试后备供应商。
                last_download_error = exc
                last_error_msg = str(exc)
                result = None
            if result:
                return result, None
            provider_name = str(provider.get("name", "unnamed")).strip()
            logger.warning(
                "[Comic] 绘图供应商 %s 失败，尝试下一个候选。",
                provider_name or "unnamed",
            )
        if last_download_error:
            raise last_download_error
        return None, last_error_msg

    async def _generate_image_with_provider(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None,
        disable_retry: bool,
        provider: dict,
    ) -> tuple[bytes | None, str | None]:
        """使用一个已配置供应商执行生成并处理重试。"""
        api_protocol = self._get_provider_value("api_protocol", provider)
        max_retries = self.config_manager.get_drawing_network_retries()
        output_exception_retries = (
            0
            if disable_retry
            else self.config_manager.get_drawing_output_exception_retries()
        )
        exception_keywords = (
            self.config_manager.get_drawing_output_exception_retry_keywords()
        )
        retry_delay = self.config_manager.get_drawing_retry_delay()
        exception_retry_count = 0
        network_retry_count = 0
        last_error_msg = None

        while True:
            try:
                if api_protocol == "images":
                    result = await self._call_images_api(prompt, images_data, provider)
                elif api_protocol == "chat":
                    result = await self._call_chat_api(prompt, images_data, provider)
                elif api_protocol == "google":
                    result = await self._call_google_api(prompt, images_data, provider)
                elif api_protocol == "grok":
                    result = await self._call_grok_api(prompt, images_data, provider)
                elif api_protocol == "gemini":
                    result = await self._call_gemini_api(prompt, images_data, provider)
                elif api_protocol in {
                    "agnes_ai",
                    "xai",
                    "minimax",
                    "doubao",
                    "sensenova",
                    "dashscope",
                    "stepfun",
                }:
                    result = await self._call_preset_api(
                        prompt, images_data, provider, api_protocol
                    )
                else:
                    raise ValueError(f"不支持的绘图 API 协议: {api_protocol}")
                if result:
                    return result, None
                break
            except Exception as exc:
                if isinstance(exc, ImageDownloadFailedError):
                    raise
                last_error_msg = str(exc)
                logger.error(
                    "[Comic] 画图报错 (%s): %s", type(exc).__name__, last_error_msg
                )
                if disable_retry:
                    break
                is_exception = any(
                    keyword in last_error_msg
                    for keyword in exception_keywords
                    if keyword
                )
                if is_exception:
                    if exception_retry_count < output_exception_retries:
                        exception_retry_count += 1
                        logger.info(
                            "[Comic] 命中异常关键词，开始第 %d 次内容重试...",
                            exception_retry_count,
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    break
                status_match = re.search(r"HTTP (\d{3})", last_error_msg)
                status_code = int(status_match.group(1)) if status_match else None
                is_retryable_network_error = isinstance(exc, httpx.RequestError) or (
                    status_code in {408, 409, 429}
                    or status_code is not None
                    and status_code >= 500
                )
                if not is_retryable_network_error or network_retry_count >= max_retries:
                    break
                network_retry_count += 1
                logger.info(
                    "[Comic] 网络或服务报错，开始第 %d 次网络重试...",
                    network_retry_count,
                )
                await asyncio.sleep(retry_delay)

        logger.debug("[Comic] 画图重试次数耗尽或请求失败，任务终止。")
        return None, last_error_msg

    def _get_provider_value(self, name: str, provider: dict) -> Any:
        """读取供应商条目字段，并为缺失字段提供安全默认值。

        绘图连接参数只允许来自当前条目，避免删除面板外层字段后仍出现不可见的
        回退来源。模板正常保存时会提供完整字段，默认值仅保护旧数据或手工配置。
        """
        value = provider.get(name)
        if value not in (None, ""):
            return value
        return DRAWING_PROVIDER_DEFAULTS.get(name, "")

    def _get_request_proxy(self, provider: dict | None = None) -> str | None:
        """获取当前绘图请求的代理，供应商配置优先于全局配置。"""
        provider_proxy = str((provider or {}).get("proxy", "")).strip()
        if provider_proxy:
            return provider_proxy
        getter = getattr(self.config_manager, "get_drawing_proxy", None)
        global_proxy = getter() if callable(getter) else ""
        return str(global_proxy).strip() or None

    def _resolve_size(self, size_or_ratio: str, aspect_ratio: str) -> str:
        """按当前供应商条目的比例解析 API 支持的 WxH 尺寸。"""
        size = (size_or_ratio or "").strip().lower()
        aspect_ratio = (aspect_ratio or "").strip().lower()
        if not aspect_ratio:
            aspect_ratio = "16:9"
        size_aliases = {"1k": 1024, "2k": 2560, "4k": 3840}
        if size in size_aliases:
            result = self._build_size_from_ratio(size_aliases[size], aspect_ratio)
        elif size in {"auto", ""}:
            result = self._build_size_from_ratio(1792, aspect_ratio)
        elif ":" in size and re.fullmatch(r"\d+:\d+", size):
            result = self._build_size_from_ratio(1792, size)
        elif re.fullmatch(r"\d+x\d+", size):
            result = size
        else:
            result = self._build_size_from_ratio(1792, aspect_ratio)
        if re.fullmatch(r"\d+x\d+", result):
            try:
                width, height = map(int, result.split("x"))
                result = (
                    f"{max(16, ((width + 15) // 16) * 16)}"
                    f"x{max(16, ((height + 15) // 16) * 16)}"
                )
            except ValueError:
                pass
        return result

    @staticmethod
    def _build_size_from_ratio(long_edge: int, aspect_ratio: str) -> str:
        """按长边和宽高比构建 16 的倍数尺寸。"""
        if not aspect_ratio or ":" not in aspect_ratio:
            aspect_ratio = "16:9"
        try:
            width_ratio, height_ratio = map(int, aspect_ratio.split(":", 1))
        except ValueError:
            width_ratio, height_ratio = 16, 9
        if width_ratio >= height_ratio:
            width = long_edge
            height = max(2, round(long_edge * height_ratio / width_ratio))
        else:
            height = long_edge
            width = max(2, round(long_edge * width_ratio / height_ratio))
        width = max(16, ((width + 15) // 16) * 16)
        height = max(16, ((height + 15) // 16) * 16)
        return f"{width}x{height}"

    async def _call_google_api(
        self, prompt: str, images_data: list[tuple[bytes, str]] | None, provider: dict
    ) -> bytes | None:
        return await self._request_service.call_google_api(
            prompt, images_data, provider
        )

    async def _call_preset_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None,
        provider: dict,
        provider_type: str,
    ) -> bytes | None:
        return await self._request_service.call_preset_api(
            prompt, images_data, provider, provider_type
        )

    async def _call_stepfun_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None,
        provider: dict,
        api_key: str,
        model: str,
        timeout: int | float,
    ) -> bytes | None:
        return await self._request_service.call_stepfun_api(
            prompt, images_data, provider, api_key, model, timeout
        )

    async def _post_json_for_image(
        self,
        target_url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int | float,
        provider_name: str,
        provider: dict,
    ) -> bytes | None:
        return await self._request_service.post_json_for_image(
            target_url, headers, payload, timeout, provider_name, provider
        )

    def _resolve_dashscope_size(self, image_size: str, aspect_ratio: str) -> str:
        return resolve_dashscope_size(image_size, aspect_ratio)

    async def _call_images_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        provider: dict | None = None,
    ) -> bytes | None:
        return await self._request_service.call_images_api(
            prompt, images_data, provider
        )

    async def _call_grok_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        provider: dict | None = None,
    ) -> bytes | None:
        return await self._request_service.call_grok_api(prompt, images_data, provider)

    async def _call_gemini_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        provider: dict | None = None,
    ) -> bytes | None:
        return await self._request_service.call_gemini_api(
            prompt, images_data, provider
        )

    async def _call_chat_api(
        self,
        prompt: str,
        images_data: list[tuple[bytes, str]] | None = None,
        provider: dict | None = None,
    ) -> bytes | None:
        return await self._request_service.call_chat_api(prompt, images_data, provider)

    async def _extract_image_from_response(
        self, data: Any, proxy: str | None = None
    ) -> bytes | None:
        return await self._image_response_service.extract_image_from_response(
            data, proxy
        )

    @staticmethod
    def _decode_data_uri(data_uri: str) -> bytes:
        return DrawingImageResponseService.decode_data_uri(data_uri)

    @staticmethod
    def _decode_base64(encoded: str) -> bytes:
        return DrawingImageResponseService.decode_base64(encoded)

    @staticmethod
    def _validate_image_bytes(data: bytes) -> None:
        DrawingImageResponseService.validate_image_bytes(data)

    async def download_public_image(
        self, url: str, proxy: str | None = None
    ) -> bytes | None:
        return await self._image_response_service.download_public_image(url, proxy)

    @staticmethod
    def _sanitize_url(url: str) -> str:
        return DrawingImageResponseService.sanitize_url(url)

    @staticmethod
    def _summarize_response(data: Any) -> str:
        return DrawingImageResponseService.summarize_response(data)
