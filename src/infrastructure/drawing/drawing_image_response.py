"""绘图接口响应的图片提取、下载与安全校验。

不同供应商会把图片放在 Base64、Data URI、Markdown 或 URL 字段中。本服务按
可靠性由高到低依次处理这些候选内容，并对公网下载地址及图片签名做校验，防止
将接口错误页、内网地址或超大内容作为漫画图片继续投递。
"""

import asyncio
import base64
import binascii
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

from ...utils.logger import logger


class ImageDownloadFailedError(Exception):
    """图片下载失败，但保留了最后一次尝试的原始 URL 供兜底发送。"""

    def __init__(self, message: str, fallback_url: str | None = None):
        super().__init__(message)
        self.fallback_url = fallback_url


class DrawingImageResponseHooks(Protocol):
    """描述图片响应服务依赖的宿主能力。"""

    config_manager: Any


@dataclass(slots=True)
class DrawingImageResponseService:
    """封装绘图响应解析、图片下载和安全校验。

    ``hooks`` 只保存下载代理所需的配置访问能力，实际下载函数显式注入，使
    响应处理独立于 ``DrawingClient`` 的具体实现，也允许测试安全地替换下载。
    """

    hooks: DrawingImageResponseHooks
    download_image: Callable[[str, str | None], Awaitable[bytes | None]]

    MAX_IMAGE_BYTES = 100 * 1024 * 1024
    MAX_IMAGE_REDIRECTS = 5
    IMAGE_DOWNLOAD_TOTAL_TIMEOUT = 90

    async def extract_image_from_response(
        self, data: Any, proxy: str | None = None
    ) -> bytes | None:
        """递归提取绘图响应中的图片数据。"""
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
                        name in {"data", "image", "images", "image_url"}
                        for name in path[:-1]
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
                    r"!\[[^\]]*\]\((https?://[^\s<>\"')\]]+)\)", text
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
                    image = await self.download_image(candidate, proxy)
                elif candidate.startswith("data:image/"):
                    image = self.decode_data_uri(candidate)
                elif candidate.startswith("base64://"):
                    image = self.decode_base64(candidate[len("base64://") :])
                else:
                    image = self.decode_base64(candidate)
                if image:
                    return image
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning("[Comic] 图片下载失败 (%s): %s", type(exc).__name__, exc)
                last_download_error = exc
            except (ValueError, TypeError, binascii.Error) as exc:
                logger.warning("[Comic] 跳过无效图片候选内容: %s", exc)

        if last_download_error:
            raise ImageDownloadFailedError(
                str(last_download_error), fallback_url=last_download_url
            )
        return None

    @classmethod
    def decode_data_uri(cls, data_uri: str) -> bytes:
        """解码 image/* Data URI。"""
        header, encoded = data_uri.split(",", 1)
        if ";base64" not in header.lower():
            raise ValueError("Data URI 不是 Base64 图片")
        return cls.decode_base64(encoded)

    @classmethod
    def decode_base64(cls, encoded: str) -> bytes:
        """解码标准或 URL-safe Base64，并确认结果是图片。"""
        normalized = re.sub(r"\s+", "", encoded).replace("-", "+").replace("_", "/")
        try:
            normalized.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("Base64 候选内容含非 ASCII 字符，跳过") from exc
        if len(normalized) > cls.MAX_IMAGE_BYTES * 4 // 3 + 4:
            raise ValueError("Base64 图片负载超过 100MB")
        normalized += "=" * (-len(normalized) % 4)
        decoded = base64.b64decode(normalized, validate=True)
        cls.validate_image_bytes(decoded)
        return decoded

    @staticmethod
    def validate_image_bytes(data: bytes) -> None:
        """拒绝 HTML、JSON 等非图片响应。"""
        if not data:
            raise ValueError("响应内容为空")
        probe = data[:32]
        is_webp = len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        is_avif = (
            len(data) >= 12
            and data[4:8] == b"ftyp"
            and data[8:12] in {b"avif", b"avis"}
        )
        is_jp2 = len(data) >= 12 and data[4:8] == b"ftyp" and b"jp2" in data[8:12]
        signatures = (
            b"\x89PNG\r\n\x1a\n",
            b"\xff\xd8\xff",
            b"GIF87a",
            b"GIF89a",
            b"BM",
            b"II*\x00",
            b"MM\x00*",
            b"\x00\x00\x00\x0cjP  ",
        )
        starts_with_sig = any(probe.find(sig) < 4 for sig in signatures)
        if starts_with_sig or is_webp or is_avif or is_jp2:
            return
        head = data[:64].decode("ascii", errors="ignore").lower()
        if head.startswith(("<!doctype", "<html", "{", "[")):
            raise ValueError("响应内容不是图片（检测到 HTML/JSON）")

    async def download_public_image(
        self, url: str, proxy: str | None = None
    ) -> bytes | None:
        """从公网 URL 下载已校验且大小受限的图片。"""
        try:
            return await asyncio.wait_for(
                self._download_image_inner(url, proxy),
                timeout=self.IMAGE_DOWNLOAD_TOTAL_TIMEOUT,
            )
        except TimeoutError as exc:
            raise httpx.TimeoutException(
                f"图片下载超过 {self.IMAGE_DOWNLOAD_TOTAL_TIMEOUT}s 总超时限制: {self.sanitize_url(url)}"
            ) from exc

    async def _download_image_inner(
        self, url: str, proxy: str | None = None
    ) -> bytes | None:
        """实际下载逻辑。"""
        current_url = url
        download_timeout = httpx.Timeout(connect=20.0, read=60.0, write=20.0, pool=20.0)
        request_proxy = (
            proxy or self.hooks.config_manager.get_drawing_download_proxy() or None
        )
        if request_proxy:
            logger.debug(
                "[Comic] 图片下载使用代理: %s", self.sanitize_url(request_proxy)
            )
        async with httpx.AsyncClient(
            timeout=download_timeout,
            follow_redirects=False,
            proxy=request_proxy,
        ) as client:
            for redirect_count in range(self.MAX_IMAGE_REDIRECTS + 1):
                await self._validate_public_image_url(current_url)
                logger.info(
                    "[Comic] 正在下载图片 URL: %s", self.sanitize_url(current_url)
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
                self.validate_image_bytes(image_bytes)
                return image_bytes
        raise ValueError("图片下载失败")

    async def _validate_public_image_url(self, url: str) -> None:
        """校验图片地址协议与基础合法性，兼容本地与私网自建绘图服务。"""
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("图片地址必须是有效的 HTTP/HTTPS URL")
        if parsed.username or parsed.password:
            raise ValueError("图片地址不允许包含用户凭据")

    @staticmethod
    def sanitize_url(url: str) -> str:
        """移除日志中的查询参数、片段和用户凭据。"""
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path, "", ""))

    @staticmethod
    def summarize_response(data: Any) -> str:
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


__all__ = ["DrawingImageResponseService", "ImageDownloadFailedError"]
