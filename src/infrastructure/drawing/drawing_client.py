import asyncio
import base64
import binascii
import ipaddress
import re
import socket
from math import gcd
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from ...utils.logger import logger
from ..config.config_manager import ConfigManager


class ImageDownloadFailedError(Exception):
    """图片下载失败，但保留了最后一次尝试的原始 URL 供兜底发送。"""

    def __init__(self, message: str, fallback_url: str | None = None):
        super().__init__(message)
        self.fallback_url = fallback_url


class DrawingClient:
    """调用已配置的绘图 API 生成图片。"""

    MAX_IMAGE_BYTES = 100 * 1024 * 1024
    MAX_IMAGE_REDIRECTS = 5

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def _build_target_url(self, raw_url: str, protocol: str) -> str:
        """智能解析补全用户配置的 API URL"""
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
        """
        调用 API 根据提示词生成单张图片 (支持参考图)
        返回图片的二进制数据和最后一次异常信息
        """
        api_protocol = self.config_manager.get_drawing_api_protocol()
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

        # 首次尝试 + 最多 max_retries 次网络重试，异常重试独立计数
        while True:
            try:
                if api_protocol == "images":
                    result = await self._call_images_api(prompt, images_data)
                elif api_protocol == "chat":
                    result = await self._call_chat_api(prompt, images_data)
                elif api_protocol == "grok":
                    result = await self._call_grok_api(prompt, images_data)
                elif api_protocol == "gemini":
                    result = await self._call_gemini_api(prompt, images_data)
                else:
                    raise ValueError(f"不支持的绘图 API 协议: {api_protocol}")

                if result:
                    return result, None
                break

            except Exception as e:
                last_error_msg = str(e)
                logger.error(f"[Comic] 画图报错 ({type(e).__name__}): {last_error_msg}")

                if disable_retry:
                    break

                # 检查是否命中输出异常触发关键词
                is_exception = any(
                    kw in last_error_msg for kw in exception_keywords if kw
                )
                if is_exception:
                    if exception_retry_count < output_exception_retries:
                        exception_retry_count += 1
                        logger.info(
                            f"[Comic] 命中异常关键词，开始第 {exception_retry_count} 次内容重试..."
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    # 内容重试耗尽
                    break
                else:
                    status_match = re.search(r"HTTP (\d{3})", last_error_msg)
                    status_code = int(status_match.group(1)) if status_match else None
                    is_retryable_network_error = isinstance(e, httpx.RequestError) or (
                        status_code in {408, 409, 429}
                        or status_code is not None
                        and status_code >= 500
                    )
                    if not is_retryable_network_error:
                        break
                    if network_retry_count < max_retries:
                        network_retry_count += 1
                        logger.info(
                            f"[Comic] 网络或服务报错，开始第 {network_retry_count} 次网络重试..."
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    # 网络重试耗尽
                    break

        logger.debug("[Comic] 画图重试次数耗尽或请求失败，任务终止。")
        return None, last_error_msg

    async def _call_images_api(
        self, prompt: str, images_data: list[tuple[bytes, str]] | None = None
    ) -> bytes | None:
        raw_url = self.config_manager.get_drawing_api_url()
        target_url = self._build_target_url(raw_url, "images")

        api_key = self.config_manager.get_drawing_api_key()
        model = self.config_manager.get_drawing_model()
        timeout = self.config_manager.get_drawing_timeout()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        raw_size = self.config_manager.get_drawing_image_size()
        resolved_size = self._resolve_size(raw_size)
        ar = self.config_manager.get_drawing_aspect_ratio()
        output_format = self.config_manager.get_drawing_output_format()

        payload: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "n": 1,
            "size": resolved_size,
            "output_format": output_format,
        }

        # 添加可选控制参数
        quality = self.config_manager.get_drawing_image_quality()
        if quality in {"low", "medium", "high"}:
            payload["quality"] = quality

        bg = self.config_manager.get_drawing_background()
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

            img_bytes, mime = images_data[0]
            ext = mime.split("/")[-1] if "/" in mime else "png"

            files = {"image[]": (f"image.{ext}", img_bytes, mime)}

            logger.info(
                f"[Comic] 发起 Images API 请求 (含图) -> {self._sanitize_url(target_url)} "
                f"(model={model}, size={resolved_size}, aspect_ratio={ar}, "
                f"reference_bytes={len(img_bytes)})..."
            )
            api_timeout = httpx.Timeout(
                connect=20.0, read=timeout, write=20.0, pool=20.0
            )
            async with httpx.AsyncClient(timeout=api_timeout) as client:
                resp = await client.post(
                    target_url, headers=headers, data=multipart_data, files=files
                )
        else:
            logger.info(
                f"[Comic] 发起 Images API 请求 -> {self._sanitize_url(target_url)} (model={model}, size={resolved_size}, aspect_ratio={ar})..."
            )
            api_timeout = httpx.Timeout(
                connect=20.0, read=timeout, write=20.0, pool=20.0
            )
            async with httpx.AsyncClient(timeout=api_timeout) as client:
                resp = await client.post(target_url, headers=headers, json=payload)

        if resp.status_code != 200:
            snippet = resp.text[:500] if resp.text else "(Empty Response)"
            raise Exception(f"API 请求失败 [HTTP {resp.status_code}]: {snippet}")

        try:
            data = resp.json()
        except Exception:
            snippet = resp.text[:500] if resp.text else "(Empty Body)"
            raise Exception(
                f"API 未返回合法的 JSON [HTTP {resp.status_code}]: {snippet}"
            )

        image = await self._extract_image_from_response(data)
        if image:
            return image

        raise Exception(f"API 返回格式异常: {self._summarize_response(data)}")

    async def _call_grok_api(
        self, prompt: str, images_data: list[tuple[bytes, str]] | None = None
    ) -> bytes | None:
        """调用 xAI Grok Imagine 官方图片接口。

        Args:
            prompt: 图片生成或编辑提示词。
            images_data: 可选参考图片及其 MIME 类型列表，当前只使用第一张。

        Returns:
            API 返回的图片二进制数据。

        Raises:
            Exception: 请求失败、响应不是 JSON 或响应中没有有效图片。
        """
        raw_url = self.config_manager.get_drawing_api_url()
        target_url = self._build_target_url(raw_url, "grok")
        api_key = self.config_manager.get_drawing_api_key()
        model = self.config_manager.get_drawing_model()
        timeout = self.config_manager.get_drawing_timeout()
        aspect_ratio = self.config_manager.get_drawing_aspect_ratio()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"model": model, "prompt": prompt}

        reference_bytes = 0
        if images_data:
            if target_url.endswith("/generations"):
                target_url = target_url.removesuffix("/generations") + "/edits"
            image_bytes, mime = images_data[0]
            image_mime = mime if mime.startswith("image/") else "image/png"
            encoded = base64.b64encode(image_bytes).decode("ascii")
            payload["image"] = {
                "type": "image_url",
                "url": f"data:{image_mime};base64,{encoded}",
            }
            reference_bytes = len(image_bytes)
        elif target_url.endswith("/edits"):
            target_url = target_url.removesuffix("/edits") + "/generations"

        logger.info(
            f"[Comic] 发起 Grok Images API 请求 -> {self._sanitize_url(target_url)} "
            f"(model={model}, aspect_ratio={aspect_ratio}, "
            f"reference_bytes={reference_bytes})..."
        )
        api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
        async with httpx.AsyncClient(timeout=api_timeout) as client:
            resp = await client.post(target_url, headers=headers, json=payload)

        if not 200 <= resp.status_code < 300:
            error_summary = resp.text[:500] if resp.text else "(Empty Response)"
            raise Exception(
                f"Grok API 请求失败 [HTTP {resp.status_code}]: {error_summary}"
            )

        try:
            data = resp.json()
        except Exception:
            raise Exception(
                f"Grok API 未返回合法的 JSON [HTTP {resp.status_code}]: "
                f"<body len={len(resp.content)}>"
            )

        image = await self._extract_image_from_response(data)
        if image:
            return image

        raise Exception(f"Grok API 返回格式异常: {self._summarize_response(data)}")

    async def _call_gemini_api(
        self, prompt: str, images_data: list[tuple[bytes, str]] | None = None
    ) -> bytes | None:
        """调用 Google Gemini Interactions 图片接口。

        Args:
            prompt: 图片生成或编辑提示词。
            images_data: 可选参考图片及其 MIME 类型列表，当前只使用第一张。

        Returns:
            最后一个模型输出中的图片二进制数据。

        Raises:
            Exception: 请求失败、响应不是 JSON 或响应中没有最终图片。
        """
        raw_url = self.config_manager.get_drawing_api_url()
        target_url = self._build_target_url(raw_url, "gemini")
        api_key = self.config_manager.get_drawing_api_key()
        model = self.config_manager.get_drawing_model()
        timeout = self.config_manager.get_drawing_timeout()
        aspect_ratio = self.config_manager.get_drawing_aspect_ratio()

        raw_size = self.config_manager.get_drawing_image_size().strip()
        if raw_size.upper() in {"1K", "2K", "4K"}:
            image_size = raw_size.upper()
        elif re.fullmatch(r"\d+x\d+", raw_size.lower()):
            width, height = map(int, raw_size.lower().split("x", 1))
            longest_edge = max(width, height)
            if longest_edge <= 1024:
                image_size = "1K"
            elif longest_edge <= 2048:
                image_size = "2K"
            else:
                image_size = "4K"
        else:
            image_size = "1K"

        output_format = self.config_manager.get_drawing_output_format().lower()
        output_mime = {
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
        }.get(output_format)

        input_content: list[dict[str, str]] = [{"type": "text", "text": prompt}]
        reference_bytes = 0
        if images_data:
            image_bytes, mime = images_data[0]
            image_mime = mime if mime.startswith("image/") else "image/png"
            input_content.append(
                {
                    "type": "image",
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                    "mime_type": image_mime,
                }
            )
            reference_bytes = len(image_bytes)

        response_format: dict[str, str] = {
            "type": "image",
            "aspect_ratio": aspect_ratio,
            "image_size": image_size,
        }
        if output_mime:
            response_format["mime_type"] = output_mime

        payload: dict[str, Any] = {
            "model": model,
            "input": input_content,
            "response_format": response_format,
            "store": False,
        }
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

        logger.info(
            f"[Comic] 发起 Gemini Interactions API 请求 -> {self._sanitize_url(target_url)} "
            f"(model={model}, image_size={image_size}, "
            f"aspect_ratio={aspect_ratio}, reference_bytes={reference_bytes})..."
        )
        api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
        async with httpx.AsyncClient(timeout=api_timeout) as client:
            resp = await client.post(target_url, headers=headers, json=payload)

        if not 200 <= resp.status_code < 300:
            error_summary = resp.text[:500] if resp.text else "(Empty Response)"
            raise Exception(
                f"Gemini API 请求失败 [HTTP {resp.status_code}]: {error_summary}"
            )

        try:
            data = resp.json()
        except Exception:
            raise Exception(
                f"Gemini API 未返回合法的 JSON [HTTP {resp.status_code}]: "
                f"<body len={len(resp.content)}>"
            )

        steps = data.get("steps") if isinstance(data, dict) else None
        model_outputs = (
            [
                step
                for step in steps
                if isinstance(step, dict) and step.get("type") == "model_output"
            ]
            if isinstance(steps, list)
            else []
        )
        for step in reversed(model_outputs):
            content = step.get("content")
            if not isinstance(content, list):
                continue
            for item in reversed(content):
                if not isinstance(item, dict) or item.get("type") != "image":
                    continue
                encoded = item.get("data")
                if not isinstance(encoded, str) or not encoded.strip():
                    continue
                try:
                    return self._decode_base64(encoded)
                except (ValueError, TypeError, binascii.Error) as exc:
                    logger.debug(f"[Comic] 跳过无效 Gemini 最终图片: {exc}")

        # When steps are present, limit compatibility parsing to model outputs so
        # temporary thought images cannot be selected as final output.
        fallback_data: Any = model_outputs if isinstance(steps, list) else data
        image = await self._extract_image_from_response(fallback_data)
        if image:
            return image

        status = data.get("status") if isinstance(data, dict) else None
        raise Exception(
            f"Gemini API 未返回最终图片 (status={status or 'unknown'}): "
            f"{self._summarize_response(data)}"
        )

    async def _call_chat_api(
        self, prompt: str, images_data: list[tuple[bytes, str]] | None = None
    ) -> bytes | None:
        raw_url = self.config_manager.get_drawing_api_url()
        target_url = self._build_target_url(raw_url, "chat")

        api_key = self.config_manager.get_drawing_api_key()
        model = self.config_manager.get_drawing_model()

        timeout = self.config_manager.get_drawing_timeout()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        raw_size = self.config_manager.get_drawing_image_size()
        resolved_size = self._resolve_size(raw_size)
        ar = self.config_manager.get_drawing_aspect_ratio()

        # 将长宽比与分辨率要求显式追加到 prompt 结尾，防止 Chat 协议模型忽略
        width, height = map(int, resolved_size.split("x", 1))
        divisor = gcd(width, height)
        effective_aspect_ratio = f"{width // divisor}:{height // divisor}"
        if width > height:
            orientation = "Horizontal Landscape Orientation"
        elif width < height:
            orientation = "Vertical Portrait Orientation"
        else:
            orientation = "Square Orientation"
        full_prompt = f"{prompt}\n\n[Image Layout & Spec Requirements: Aspect Ratio {effective_aspect_ratio}, Resolution {resolved_size}, {orientation}]"

        content = []
        if images_data and len(images_data) > 0:
            img_bytes, mime = images_data[0]
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            )

        content.append({"type": "text", "text": full_prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
        }

        logger.info(
            f"[Comic] 发起 Chat API 请求 -> {self._sanitize_url(target_url)} (model={model}, size={resolved_size}, aspect_ratio={ar})..."
        )

        api_timeout = httpx.Timeout(connect=20.0, read=timeout, write=20.0, pool=20.0)
        async with httpx.AsyncClient(timeout=api_timeout) as client:
            resp = await client.post(target_url, headers=headers, json=payload)

            if resp.status_code != 200:
                snippet = resp.text[:500] if resp.text else "(Empty Response)"
                raise Exception(f"API 请求失败 [HTTP {resp.status_code}]: {snippet}")

            try:
                data = resp.json()
            except Exception:
                snippet = resp.text[:500] if resp.text else "(Empty Body)"
                raise Exception(
                    f"API 未返回合法的 JSON [HTTP {resp.status_code}]: {snippet}"
                )

            image = await self._extract_image_from_response(data)
            if image:
                return image

            raise Exception(
                f"无法从 Chat API 的回复中提取到图片: {self._summarize_response(data)}"
            )

    async def _extract_image_from_response(self, data: Any) -> bytes | None:
        """递归提取中转站响应中的图片数据。"""
        encoded: list[tuple[str, str]] = []
        image_fields: list[tuple[str, str]] = []
        content_images: list[tuple[str, str]] = []
        content_urls: list[tuple[str, str]] = []
        fallback_urls: list[tuple[str, str]] = []

        def collect(value: Any, path: tuple[str, ...] = ()) -> None:
            if isinstance(value, dict):
                for name, item in value.items():
                    collect(item, (*path, name.lower()))
            elif isinstance(value, list):
                for item in value:
                    collect(item, path)
            elif isinstance(value, str):
                text = value.strip()
                if not text:
                    return
                key = path[-1] if path else ""
                if key in {"b64_json", "base64"}:
                    encoded.append(("base64", text))
                    return
                if key in {"image_url", "image"} or (
                    key == "url"
                    and any(
                        name in {"image", "images", "image_url"} for name in path[:-1]
                    )
                ):
                    image_fields.append(("value", text))
                    return

                data_uris = re.findall(
                    r"data:image/[^\s,;]+(?:;[^\s,;]+)*;base64,[A-Za-z0-9+/=_-]+",
                    text,
                    re.IGNORECASE,
                )
                content_images.extend(("value", item) for item in data_uris)

                markdown_urls = re.findall(
                    r"!\[[^\]]*\]\((https?://[^\s<>\"')\]]+)", text
                )
                content_images.extend(
                    ("url", item.rstrip(".,;`")) for item in markdown_urls
                )

                urls = re.findall(r"https?://[^\s<>\"')\]]+", text)
                markdown_url_set = set(markdown_urls)
                target = content_urls if key in {"content", "text"} else fallback_urls
                target.extend(
                    ("url", item.rstrip(".,;`"))
                    for item in urls
                    if item not in markdown_url_set
                )

                if not data_uris and not urls and len(text) >= 100:
                    encoded.append(("base64", text))

        collect(data)
        last_download_error: Exception | None = None
        last_download_url: str | None = None
        candidates = (
            encoded + image_fields + content_images + content_urls + fallback_urls
        )
        for candidate_type, candidate in candidates:
            try:
                if candidate_type == "url" or candidate.startswith(
                    ("http://", "https://")
                ):
                    last_download_url = candidate
                    image = await self.download_public_image(candidate)
                elif candidate.startswith("data:image/"):
                    image = self._decode_data_uri(candidate)
                elif candidate.startswith("base64://"):
                    image = self._decode_base64(candidate[len("base64://") :])
                else:
                    image = self._decode_base64(candidate)
                if image:
                    return image
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning(f"[Comic] 图片下载失败 ({type(exc).__name__}): {exc}")
                last_download_error = exc
            except (ValueError, TypeError, binascii.Error) as exc:
                logger.warning(f"[Comic] 跳过无效图片候选内容: {exc}")

        if last_download_error:
            raise ImageDownloadFailedError(
                str(last_download_error), fallback_url=last_download_url
            )
        return None

    @staticmethod
    def _decode_data_uri(data_uri: str) -> bytes:
        """解码 image/* Data URI。"""
        header, encoded = data_uri.split(",", 1)
        if ";base64" not in header.lower():
            raise ValueError("Data URI 不是 Base64 图片")
        return DrawingClient._decode_base64(encoded)

    @staticmethod
    def _decode_base64(encoded: str) -> bytes:
        """解码标准或 URL-safe Base64，并确认结果是图片。"""
        normalized = re.sub(r"\s+", "", encoded).replace("-", "+").replace("_", "/")
        # 含非 ASCII 字符的字符串不可能是合法 Base64，提前拒绝
        try:
            normalized.encode("ascii")
        except UnicodeEncodeError:
            raise ValueError("Base64 候选内容含非 ASCII 字符，跳过")
        if len(normalized) > DrawingClient.MAX_IMAGE_BYTES * 4 // 3 + 4:
            raise ValueError("Base64 图片负载超过 100MB")
        normalized += "=" * (-len(normalized) % 4)
        decoded = base64.b64decode(normalized, validate=True)
        DrawingClient._validate_image_bytes(decoded)
        return decoded

    @staticmethod
    def _validate_image_bytes(data: bytes) -> None:
        """拒绝 HTML、JSON 等非图片响应。"""
        if not data:
            raise ValueError("响应内容为空")

        # 扫描前 32 字节，兼容部分代理在图片前附加少量额外字节的情况
        probe = data[:32]

        is_webp = len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        is_avif = (
            len(data) >= 12
            and data[4:8] == b"ftyp"
            and data[8:12]
            in {
                b"avif",
                b"avis",
            }
        )
        # JPEG 2000 / JP2
        is_jp2 = len(data) >= 12 and data[4:8] == b"ftyp" and b"jp2" in data[8:12]

        signatures = (
            b"\x89PNG\r\n\x1a\n",
            b"\xff\xd8\xff",
            b"GIF87a",
            b"GIF89a",
            b"BM",
            b"II*\x00",
            b"MM\x00*",
            b"\x00\x00\x00\x0cjP  ",  # JPEG 2000
        )
        starts_with_sig = any(probe.find(sig) < 4 for sig in signatures)

        if not (starts_with_sig or is_webp or is_avif or is_jp2):
            # 最后兜底：检查 Content-Type 无法识别的情况下，确认不是 HTML/JSON 文本
            try:
                head = data[:64].decode("ascii", errors="ignore").lower()
                if head.startswith(("<!doctype", "<html", "{", "[")):
                    raise ValueError("响应内容不是图片（检测到 HTML/JSON）")
            except UnicodeDecodeError:
                pass  # 无法解码为 ASCII，说明是二进制内容，允许通过
            # 若内容是未知二进制格式（可能是不常见图片格式），放行而不是强制拒绝
            return
        # 已匹配已知图片签名，直接通过

    # 图片下载整体超时（秒），防止代理服务器慢速发送导致无限等待
    IMAGE_DOWNLOAD_TOTAL_TIMEOUT = 90

    async def download_public_image(self, url: str) -> bytes | None:
        """从公网 URL 下载已校验且大小受限的图片。"""
        try:
            return await asyncio.wait_for(
                self._download_image_inner(url),
                timeout=self.IMAGE_DOWNLOAD_TOTAL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise httpx.TimeoutException(
                f"图片下载超过 {self.IMAGE_DOWNLOAD_TOTAL_TIMEOUT}s 总超时限制: {self._sanitize_url(url)}"
            )

    async def _download_image_inner(self, url: str) -> bytes | None:
        """实际下载逻辑（由 _download_image 包裹超时）。"""
        current_url = url
        # connect/write 超时 20s，read 超时 60s（单次 socket read）
        download_timeout = httpx.Timeout(connect=20.0, read=60.0, write=20.0, pool=20.0)
        proxy = self.config_manager.get_drawing_download_proxy() or None
        if proxy:
            logger.debug(f"[Comic] 图片下载使用代理: {self._sanitize_url(proxy)}")
        async with httpx.AsyncClient(
            timeout=download_timeout,
            follow_redirects=False,
            proxy=proxy,
        ) as client:
            for redirect_count in range(self.MAX_IMAGE_REDIRECTS + 1):
                await self._validate_public_image_url(current_url)
                logger.info(
                    f"[Comic] 正在下载图片 URL: {self._sanitize_url(current_url)}"
                )
                resp = await client.get(current_url)
                if resp.status_code in {301, 302, 303, 307, 308}:
                    location = resp.headers.get("Location")
                    if not location:
                        raise httpx.HTTPStatusError(
                            f"图片重定向缺少地址 [HTTP {resp.status_code}]",
                            request=resp.request,
                            response=resp,
                        )
                    if redirect_count >= self.MAX_IMAGE_REDIRECTS:
                        raise ValueError("图片下载重定向次数超过限制")
                    current_url = str(resp.url.join(location))
                    continue

                if resp.status_code != 200:
                    raise httpx.HTTPStatusError(
                        f"图片下载失败 [HTTP {resp.status_code}]",
                        request=resp.request,
                        response=resp,
                    )

                image_bytes = resp.content
                if len(image_bytes) > self.MAX_IMAGE_BYTES:
                    raise ValueError("图片下载内容超过 100MB")

                self._validate_image_bytes(image_bytes)
                return image_bytes

        raise ValueError("图片下载失败")

    async def _validate_public_image_url(self, url: str) -> None:
        """拒绝非 HTTP 协议及解析到本机或私网的图片地址。"""
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("图片地址必须是有效的 HTTP/HTTPS URL")
        if parsed.username or parsed.password:
            raise ValueError("图片地址不允许包含用户凭据")

        hostname = parsed.hostname.rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError("图片地址不允许访问本机或私网")

        try:
            addresses = await asyncio.to_thread(
                socket.getaddrinfo,
                hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            request = httpx.Request("GET", url)
            raise httpx.ConnectError("图片地址 DNS 解析失败", request=request) from exc

        if not addresses or any(
            not ipaddress.ip_address(item[4][0]).is_global for item in addresses
        ):
            raise ValueError("图片地址不允许访问本机或私网")

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """移除日志中的查询参数、片段和用户凭据。"""
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))

    @staticmethod
    def _summarize_response(data: Any) -> str:
        """生成不包含响应正文和 Base64 的结构摘要。"""

        def summarize(value: Any, depth: int = 0) -> str:
            if isinstance(value, str):
                return f"<str len={len(value)}>"
            if depth >= 3:
                return type(value).__name__
            if isinstance(value, dict):
                items = list(value.items())[:10]
                body = ", ".join(
                    f"{str(key)[:64]}: {summarize(item, depth + 1)}"
                    for key, item in items
                )
                suffix = ", ..." if len(value) > len(items) else ""
                return f"{{{body}{suffix}}}"
            if isinstance(value, list):
                items = value[:3]
                body = ", ".join(summarize(item, depth + 1) for item in items)
                suffix = ", ..." if len(value) > len(items) else ""
                return f"[{body}{suffix}] (len={len(value)})"
            return f"<{type(value).__name__}>"

        return summarize(data)

    def _resolve_size(self, size_or_ratio: str) -> str:
        """将比例（如 16:9）或尺寸别名解析为 API 支持的 WxH 格式"""
        s = (size_or_ratio or "").strip().lower()
        ar = self.config_manager.get_drawing_aspect_ratio().strip().lower()
        if not ar:
            ar = "16:9"

        # 别名映射到长边像素
        size_aliases = {
            "1k": 1024,
            "2k": 2560,
            "4k": 3840,
        }

        if s in size_aliases:
            long_edge = size_aliases[s]
            res = self._build_size_from_ratio(long_edge, ar)
        elif s in ["auto", ""]:
            res = self._build_size_from_ratio(1792, ar)
        elif ":" in s and re.fullmatch(r"\d+:\d+", s):
            res = self._build_size_from_ratio(1792, s)
        elif re.fullmatch(r"\d+x\d+", s):
            res = s
        else:
            res = self._build_size_from_ratio(1792, ar)

        if re.fullmatch(r"\d+x\d+", res):
            try:
                w, h = map(int, res.split("x"))
                w = max(16, ((w + 15) // 16) * 16)
                h = max(16, ((h + 15) // 16) * 16)
                res = f"{w}x{h}"
            except Exception:
                pass

        return res

    @staticmethod
    def _build_size_from_ratio(long_edge: int, aspect_ratio: str) -> str:
        if not aspect_ratio or ":" not in aspect_ratio:
            aspect_ratio = "16:9"
        try:
            w_r, h_r = map(int, aspect_ratio.split(":", 1))
        except Exception:
            w_r, h_r = 16, 9

        if w_r >= h_r:
            width = long_edge
            height = max(2, round(long_edge * h_r / w_r))
        else:
            height = long_edge
            width = max(2, round(long_edge * w_r / h_r))

        width = max(16, ((width + 15) // 16) * 16)
        height = max(16, ((height + 15) // 16) * 16)
        return f"{width}x{height}"
