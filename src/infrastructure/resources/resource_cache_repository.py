"""基于本地文件系统的静态资源与字体持久化缓存仓储实现。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

from ...domain.repositories.resource_cache_repository import IResourceCacheRepository
from ...utils.logger import logger

# 现代浏览器 User-Agent，确保 Google Fonts 等字体服务返回 WOFF2 格式
DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# 常见静态资源 MIME 类型映射覆盖表
MIME_TYPE_OVERRIDES = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
    ".css": "text/css",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


class FileSystemResourceCacheRepository(IResourceCacheRepository):
    """用于下载静态资源的本地文件系统持久化缓存仓储。"""

    def __init__(self, base_cache_dir: Path | str):
        """初始化资源缓存目录。

        Args:
            base_cache_dir: 根缓存目录路径（如 plugin_data/cache/resources）。
        """
        self.base_dir = Path(base_cache_dir)
        self.fonts_dir = self.base_dir / "fonts"
        self.css_dir = self.base_dir / "css"
        self.images_dir = self.base_dir / "images"
        self.scripts_dir = self.base_dir / "scripts"
        self.meta_dir = self.base_dir / "meta"

        for directory in [
            self.fonts_dir,
            self.css_dir,
            self.images_dir,
            self.scripts_dir,
            self.meta_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()
        self._download_locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _get_url_hash(self, url: str) -> str:
        """计算 URL 的 SHA256 十六进制哈希值。"""
        return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()

    def _determine_category_and_extension(
        self, url: str, mime_type: str | None = None
    ) -> tuple[Path, str, str]:
        """确定资源所属的目录分类、扩展名与 MIME 类型。

        Args:
            url: 资源远程链接。
            mime_type: 可选的已知 MIME 类型。

        Returns:
            (分类目录Path, 文件扩展名, 解析后的MIME类型) 元组。
        """
        parsed = urlparse(url)
        path = parsed.path.lower()

        # 优先按文件扩展名判断
        for ext, mime in MIME_TYPE_OVERRIDES.items():
            if path.endswith(ext):
                if ext in {".woff2", ".woff", ".ttf", ".otf", ".eot"}:
                    return self.fonts_dir, ext, mime
                if ext == ".css":
                    return self.css_dir, ext, mime
                if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
                    return self.images_dir, ext, mime
                if ext in {".js", ".mjs"}:
                    return self.scripts_dir, ext, mime

        # 其次按传入的 MIME 类型判断
        if mime_type:
            mime_lower = mime_type.lower()
            if "font" in mime_lower or "woff" in mime_lower or "truetype" in mime_lower:
                ext = (
                    ".woff2"
                    if "woff2" in mime_lower
                    else ".woff"
                    if "woff" in mime_lower
                    else ".ttf"
                )
                return self.fonts_dir, ext, mime_type
            if "css" in mime_lower:
                return self.css_dir, ".css", "text/css"
            if "image" in mime_lower:
                ext = mimetypes.guess_extension(mime_type) or ".png"
                return self.images_dir, ext, mime_type
            if "javascript" in mime_lower:
                return self.scripts_dir, ".js", "application/javascript"

        # 根据 URL 特征识别（如 google fonts css2）
        if "css2" in path or "css" in path or "fonts.googleapis.com" in parsed.netloc:
            return self.css_dir, ".css", "text/css"

        # 根据域名或路径特征回退
        if "font" in path or "font" in parsed.netloc:
            return self.fonts_dir, ".woff2", "font/woff2"

        return self.images_dir, ".bin", mime_type or "application/octet-stream"

    def _get_cache_file_path(
        self, url: str, mime_type: str | None = None
    ) -> tuple[Path, str]:
        """计算给定 URL 的本地存储路径与 MIME 类型。"""
        url_hash = self._get_url_hash(url)
        category_dir, ext, resolved_mime = self._determine_category_and_extension(
            url, mime_type
        )
        file_path = category_dir / f"{url_hash}{ext}"
        return file_path, resolved_mime

    def _get_meta_path(self, url_hash: str) -> Path:
        """获取哈希对应的元数据文件路径。"""
        return self.meta_dir / f"{url_hash}.json"

    async def get(self, url: str) -> bytes | None:
        """从本地磁盘读取已缓存的资源二进制。

        Args:
            url: 远程资源链接。

        Returns:
            文件二进制字节流，未命中则返回 None。
        """
        file_path = await self.get_path(url)
        if file_path and file_path.is_file():
            try:
                return await asyncio.to_thread(file_path.read_bytes)
            except Exception as e:
                logger.warning(f"读取本地缓存资源文件失败 {file_path}: {e}")
        return None

    async def set(self, url: str, data: bytes, mime_type: str | None = None) -> Path:
        """将二进制数据持久化保存到本地缓存。

        Args:
            url: 远程资源链接。
            data: 待缓存的二进制数据。
            mime_type: 可选的 MIME 类型。

        Returns:
            保存后的本地文件 Path。
        """
        url_hash = self._get_url_hash(url)
        file_path, resolved_mime = self._get_cache_file_path(url, mime_type)
        meta_path = self._get_meta_path(url_hash)

        await asyncio.to_thread(file_path.write_bytes, data)

        meta_info = {
            "url": url,
            "hash": url_hash,
            "mime_type": resolved_mime,
            "size": len(data),
            "file_path": str(file_path),
        }
        await asyncio.to_thread(
            meta_path.write_text,
            json.dumps(meta_info, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return file_path

    async def get_path(self, url: str) -> Path | None:
        """获取已缓存资源的本地文件路径。"""
        url_hash = self._get_url_hash(url)
        meta_path = self._get_meta_path(url_hash)

        if meta_path.is_file():
            try:
                meta_raw = await asyncio.to_thread(
                    meta_path.read_text, encoding="utf-8"
                )
                meta_info = json.loads(meta_raw)
                target_path = Path(meta_info.get("file_path", ""))
                if target_path.is_file() and target_path.stat().st_size > 0:
                    return target_path
            except Exception:
                pass

        # 扫描各分类子目录作为兜底检查
        for category_dir in [
            self.fonts_dir,
            self.css_dir,
            self.images_dir,
            self.scripts_dir,
        ]:
            matches = list(category_dir.glob(f"{url_hash}.*"))
            if matches and matches[0].is_file() and matches[0].stat().st_size > 0:
                return matches[0]

        return None

    async def has(self, url: str) -> bool:
        """检查资源是否已在本地缓存。"""
        path = await self.get_path(url)
        return path is not None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp 异步网络客户端会话。"""
        if self._session is None or self._session.closed:
            async with self._session_lock:
                if self._session is None or self._session.closed:
                    timeout = aiohttp.ClientTimeout(total=10, connect=5)
                    self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _get_url_lock(self, url_hash: str) -> asyncio.Lock:
        """获取指定 URL 的下载并发锁，避免高并发下重复请求同一资源。"""
        async with self._global_lock:
            if url_hash not in self._download_locks:
                self._download_locks[url_hash] = asyncio.Lock()
            return self._download_locks[url_hash]

    async def get_or_download(
        self,
        url: str,
        custom_headers: dict[str, str] | None = None,
        timeout: float = 5.0,
    ) -> tuple[bytes | None, str | None]:
        """优先读取本地缓存，未命中则异步从网络下载并固化缓存。

        Args:
            url: 远程资源链接。
            custom_headers: 可选自定义请求头。
            timeout: 下载超时时间（秒）。

        Returns:
            (二进制字节流, MIME 类型) 元组。
        """
        clean_url = url.strip()
        if not clean_url:
            return None, None

        # 补全协议相对链接（如 //cdn.example.com/foo.css）
        if clean_url.startswith("//"):
            clean_url = f"https:{clean_url}"

        url_hash = self._get_url_hash(clean_url)
        url_lock = await self._get_url_lock(url_hash)

        async with url_lock:
            # 1. 检查本地缓存
            cached_path = await self.get_path(clean_url)
            if cached_path and cached_path.is_file():
                try:
                    data = await asyncio.to_thread(cached_path.read_bytes)
                    meta_path = self._get_meta_path(url_hash)
                    mime = None
                    if meta_path.is_file():
                        try:
                            meta = json.loads(
                                await asyncio.to_thread(
                                    meta_path.read_text, encoding="utf-8"
                                )
                            )
                            mime = meta.get("mime_type")
                        except Exception:
                            pass
                    if not mime:
                        _, _, mime = self._determine_category_and_extension(clean_url)
                    return data, mime
                except Exception as e:
                    logger.warning(f"读取本地资源缓存失败 {clean_url}: {e}")

            # 2. 异步下载远程资源
            headers = {"User-Agent": DEFAULT_BROWSER_UA}
            if custom_headers:
                headers.update(custom_headers)

            # 构建候选镜像源列表（Google Fonts 自动回退）
            candidate_urls = [clean_url]
            if "fonts.googleapis.com" in clean_url:
                candidate_urls.append(
                    clean_url.replace("fonts.googleapis.com", "fonts.font.im")
                )
                candidate_urls.append(
                    clean_url.replace("fonts.googleapis.com", "fonts.loli.net")
                )
            elif "fonts.gstatic.com" in clean_url:
                candidate_urls.append(
                    clean_url.replace("fonts.gstatic.com", "gstatic.loli.net")
                )

            session = await self._get_session()
            for target_url in candidate_urls:
                try:
                    req_timeout = aiohttp.ClientTimeout(
                        total=timeout, connect=min(3.0, timeout)
                    )
                    async with session.get(
                        target_url, headers=headers, timeout=req_timeout
                    ) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            if content:
                                content_type = resp.headers.get("Content-Type", "")
                                mime_type = (
                                    content_type.split(";")[0].strip()
                                    if content_type
                                    else None
                                )
                                await self.set(clean_url, content, mime_type)
                                logger.info(
                                    f"[资源缓存] 成功下载并缓存静态资源: {clean_url} ({len(content)} 字节)"
                                )
                                return content, mime_type
                        else:
                            logger.warning(
                                f"[资源缓存] 下载 {target_url} 失败，HTTP 状态码: {resp.status}"
                            )
                except Exception as e:
                    logger.debug(f"[资源缓存] 尝试下载 {target_url} 异常: {e}")

            logger.warning(
                f"[资源缓存] 尝试所有候选镜像源后仍无法下载资源: {clean_url}"
            )
            return None, None

    def get_stats(self) -> dict[str, Any]:
        """获取本地缓存文件汇总统计。"""
        stats = {
            "total_files": 0,
            "total_bytes": 0,
            "fonts": 0,
            "css": 0,
            "images": 0,
            "scripts": 0,
        }
        for category, folder in [
            ("fonts", self.fonts_dir),
            ("css", self.css_dir),
            ("images", self.images_dir),
            ("scripts", self.scripts_dir),
        ]:
            if folder.is_dir():
                files = [f for f in folder.iterdir() if f.is_file()]
                stats[category] = len(files)
                stats["total_files"] += len(files)
                stats["total_bytes"] += sum(f.stat().st_size for f in files)
        return stats

    async def close(self) -> None:
        """关闭底层的 HTTP 客户端会话。"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
