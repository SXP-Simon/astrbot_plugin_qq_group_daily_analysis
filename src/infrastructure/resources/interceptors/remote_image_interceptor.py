"""HTML 标签与 CSS 背景属性中的远程图片拦截器。"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from ....utils.logger import logger
from .base import BaseResourceInterceptor

# 匹配 <img src="http..."> 正则
IMG_TAG_SRC_PATTERN = re.compile(
    r"""<img\s+[^>]*?src=["'](?P<url>(?:https?:)?//[^\'")\s>]+)["'][^>]*?>""",
    re.IGNORECASE,
)

# 匹配 CSS 中 background / background-image: url(...) 图片正则
CSS_IMAGE_URL_PATTERN = re.compile(
    r"""(?P<prefix>(?:background|background-image|--[\w-]+-image)\s*:\s*[^;]*?)url\(["']?(?P<url>(?:https?:)?//[^\'")\s]+\.(?:png|jpg|jpeg|gif|webp|svg|avif)(?:\?[^\'")\s]*)?)["']?\)""",
    re.IGNORECASE,
)


class RemoteImageInterceptor(BaseResourceInterceptor):
    """拦截 HTML 与 CSS 中的远程图片，支持本地插件 assets 零网络直读与网络下载持久化缓存并转 Base64。"""

    def __init__(self, cache_repo, plugin_root: Path | str | None = None):
        super().__init__(cache_repo)
        self.plugin_root = Path(plugin_root) if plugin_root else None

    def _try_resolve_local_asset(self, url: str) -> bytes | None:
        """尝试直接从本地插件 assets 目录读取同名资源，完全免去网络请求。"""
        if not self.plugin_root:
            return None

        # 匹配 URL 路径中包含的 /assets/
        if "/assets/" in url:
            subpath = url.split("/assets/", 1)[1].split("?")[0]
            local_candidate = self.plugin_root / "assets" / subpath
            if local_candidate.is_file():
                try:
                    return local_candidate.read_bytes()
                except Exception:
                    pass
        return None

    def _guess_image_mime(self, url: str, mime: str | None = None) -> str:
        """根据 URL 扩展名或传入的 MIME 推导图片 MIME 类型。"""
        if mime and mime.startswith("image/"):
            return mime
        lower = url.lower()
        if ".png" in lower:
            return "image/png"
        if ".webp" in lower:
            return "image/webp"
        if ".jpg" in lower or ".jpeg" in lower:
            return "image/jpeg"
        if ".gif" in lower:
            return "image/gif"
        if ".svg" in lower:
            return "image/svg+xml"
        return "image/png"

    async def intercept(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """拦截并内联 HTML 与 CSS 中的远程图片。

        Args:
            content: HTML 字符串。
            context: 可选上下文参数。

        Returns:
            完成图片本地化内联后的 HTML 字符串。
        """
        timeout = float((context or {}).get("timeout", 5.0))
        result = content

        urls_to_replace: set[str] = set()

        for match in IMG_TAG_SRC_PATTERN.finditer(result):
            u = match.group("url").strip()
            if not u.startswith("data:"):
                urls_to_replace.add(u)

        for match in CSS_IMAGE_URL_PATTERN.finditer(result):
            u = match.group("url").strip()
            if not u.startswith("data:"):
                urls_to_replace.add(u)

        if not urls_to_replace:
            return result

        for img_url in urls_to_replace:
            # 1. 优先尝试本地静态资源直接读取
            local_data = await asyncio.to_thread(self._try_resolve_local_asset, img_url)
            if local_data:
                mime_type = self._guess_image_mime(img_url)
                data_uri = self.to_base64_data_uri(local_data, mime_type)
                result = result.replace(img_url, data_uri)
                logger.debug(f"[图片拦截器] 从本地插件目录直读静态图片: {img_url}")
                continue

            # 2. 从本地缓存获取或异步下载
            full_url = img_url
            if full_url.startswith("//"):
                full_url = f"https:{full_url}"

            data, mime = await self.cache_repo.get_or_download(
                full_url, timeout=timeout
            )
            if data:
                mime_type = self._guess_image_mime(full_url, mime)
                data_uri = self.to_base64_data_uri(data, mime_type)
                result = result.replace(img_url, data_uri)
                logger.debug(f"[图片拦截器] 成功本地化并内联远程图片: {img_url}")
            else:
                logger.warning(f"[图片拦截器] 下载或内联远程图片失败: {img_url}")

        return result
