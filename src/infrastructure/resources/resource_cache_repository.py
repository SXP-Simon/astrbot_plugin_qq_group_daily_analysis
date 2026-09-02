"""基于本地文件系统的静态资源与字体持久化缓存仓储实现（按模板分类组织）。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

from ...domain.repositories.resource_cache_repository import (
    IResourceCacheRepository,
)
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
    """用于下载与持久化管理静态资源的本地文件系统缓存仓储，支持按模板分组存储与排障。"""

    def __init__(self, base_cache_dir: Path | str):
        """初始化资源缓存目录体系。

        Args:
            base_cache_dir: 根缓存目录路径（如 plugin_data/cache/resources）。
        """
        self.base_dir = Path(base_cache_dir)
        self.templates_dir = self.base_dir / "templates"
        self.meta_dir = self.base_dir / "meta"

        # 兼容旧版顶层分类目录
        self.legacy_fonts_dir = self.base_dir / "fonts"
        self.legacy_css_dir = self.base_dir / "css"
        self.legacy_images_dir = self.base_dir / "images"
        self.legacy_scripts_dir = self.base_dir / "scripts"

        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)

        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()
        self._download_locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _get_url_hash(self, url: str) -> str:
        """计算 URL 的 SHA256 十六进制哈希值。"""
        return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()

    def _sanitize_template_name(self, template: str | None) -> str:
        """格式化模板名称作为安全合法的目录名。"""
        if not template or not template.strip():
            return "global"
        safe = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in template.strip()
        )
        return safe.strip("_") or "global"

    def _determine_category_and_extension(
        self, url: str, mime_type: str | None = None
    ) -> tuple[str, str, str]:
        """确定资源所属的分类名（fonts, css, images, scripts）、文件扩展名与 MIME 类型。

        Args:
            url: 资源远程链接。
            mime_type: 可选的已知 MIME 类型。

        Returns:
            (分类名category, 文件扩展名ext, 解析后的MIME类型) 元组。
        """
        parsed = urlparse(url)
        path = parsed.path.lower()

        # 优先按文件扩展名判断
        for ext, mime in MIME_TYPE_OVERRIDES.items():
            if path.endswith(ext):
                if ext in {".woff2", ".woff", ".ttf", ".otf", ".eot"}:
                    return "fonts", ext, mime
                if ext == ".css":
                    return "css", ext, mime
                if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
                    return "images", ext, mime
                if ext in {".js", ".mjs"}:
                    return "scripts", ext, mime

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
                return "fonts", ext, mime_type
            if "css" in mime_lower:
                return "css", ".css", "text/css"
            if "image" in mime_lower:
                ext = mimetypes.guess_extension(mime_type) or ".png"
                return "images", ext, mime_type
            if "javascript" in mime_lower:
                return "scripts", ".js", "application/javascript"

        # 根据 URL 特征识别（如 google fonts css2）
        if "css2" in path or "css" in path or "fonts.googleapis.com" in parsed.netloc:
            return "css", ".css", "text/css"

        # 根据域名或路径特征回退
        if "font" in path or "font" in parsed.netloc:
            return "fonts", ".woff2", "font/woff2"

        return "images", ".bin", mime_type or "application/octet-stream"

    def _get_cache_file_path(
        self,
        url: str,
        mime_type: str | None = None,
        template: str | None = None,
    ) -> tuple[Path, str, str, str]:
        """计算给定 URL 的按模板组织的本地存储路径、分类、扩展名与 MIME 类型。"""
        url_hash = self._get_url_hash(url)
        template_name = self._sanitize_template_name(template)
        category, ext, resolved_mime = self._determine_category_and_extension(
            url, mime_type
        )
        target_dir = self.templates_dir / template_name / category
        file_path = target_dir / f"{url_hash}{ext}"
        return file_path, category, ext, resolved_mime

    def _get_meta_path(self, url_hash: str) -> Path:
        """获取哈希对应的元数据文件路径。"""
        return self.meta_dir / f"{url_hash}.json"

    async def get(self, url: str, template: str | None = None) -> bytes | None:
        """从本地磁盘读取已缓存的资源二进制。

        Args:
            url: 远程资源链接。
            template: 关联的模板主题名称。

        Returns:
            文件二进制字节流，未命中则返回 None。
        """
        file_path = await self.get_path(url, template=template)
        if file_path and file_path.is_file():
            try:
                return await asyncio.to_thread(file_path.read_bytes)
            except Exception as e:
                logger.warning(f"读取本地缓存资源文件失败 {file_path}: {e}")
        return None

    async def set(
        self,
        url: str,
        data: bytes,
        mime_type: str | None = None,
        template: str | None = None,
    ) -> Path:
        """将二进制数据按模板结构持久化保存到本地缓存。

        Args:
            url: 远程资源链接。
            data: 待缓存的二进制数据。
            mime_type: 可选的 MIME 类型。
            template: 关联模板名称。

        Returns:
            保存后的本地文件 Path。
        """
        url_hash = self._get_url_hash(url)
        template_name = self._sanitize_template_name(template)
        file_path, category, ext, resolved_mime = self._get_cache_file_path(
            url, mime_type, template=template_name
        )
        meta_path = self._get_meta_path(url_hash)

        # 确保模板分类目录存在
        await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(file_path.write_bytes, data)

        now_ts = time.time()
        existing_meta = {}
        if meta_path.is_file():
            try:
                meta_raw = await asyncio.to_thread(
                    meta_path.read_text, encoding="utf-8"
                )
                existing_meta = json.loads(meta_raw)
            except Exception:
                pass

        access_count = existing_meta.get("access_count", 0) + 1
        created_at = existing_meta.get("created_at", now_ts)

        meta_info = {
            "url": url,
            "hash": url_hash,
            "template": template_name,
            "category": category,
            "mime_type": resolved_mime,
            "size": len(data),
            "file_path": str(file_path),
            "relative_path": str(file_path.relative_to(self.base_dir)).replace(
                "\\", "/"
            ),
            "created_at": created_at,
            "last_accessed_at": now_ts,
            "access_count": access_count,
        }
        await asyncio.to_thread(
            meta_path.write_text,
            json.dumps(meta_info, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return file_path

    async def get_path(self, url: str, template: str | None = None) -> Path | None:
        """获取已缓存资源的本地文件路径（优先匹配指定模板，其次跨模板共享查找）。"""
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

        # 1. 优先在指定模板子目录查找
        if template:
            template_name = self._sanitize_template_name(template)
            t_dir = self.templates_dir / template_name
            if t_dir.is_dir():
                matches = list(t_dir.rglob(f"{url_hash}.*"))
                if matches and matches[0].is_file() and matches[0].stat().st_size > 0:
                    return matches[0]

        # 2. 扫描 templates 全局/其他模板目录查找
        if self.templates_dir.is_dir():
            matches = list(self.templates_dir.rglob(f"{url_hash}.*"))
            if matches and matches[0].is_file() and matches[0].stat().st_size > 0:
                return matches[0]

        # 3. 扫描旧版扁平目录兜底
        for cat_dir in [
            self.legacy_fonts_dir,
            self.legacy_css_dir,
            self.legacy_images_dir,
            self.legacy_scripts_dir,
        ]:
            if cat_dir.is_dir():
                matches = list(cat_dir.glob(f"{url_hash}.*"))
                if matches and matches[0].is_file() and matches[0].stat().st_size > 0:
                    return matches[0]

        return None

    async def has(self, url: str, template: str | None = None) -> bool:
        """检查资源是否已在本地缓存。"""
        path = await self.get_path(url, template=template)
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
        template: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """优先读取本地缓存，未命中则异步从网络下载并持久化缓存。

        Args:
            url: 远程资源链接。
            custom_headers: 可选自定义请求头。
            timeout: 下载超时时间（秒）。
            template: 关联模板名称。

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
            cached_path = await self.get_path(clean_url, template=template)
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
                            # 更新访问计数与时间
                            meta["access_count"] = meta.get("access_count", 0) + 1
                            meta["last_accessed_at"] = time.time()
                            await asyncio.to_thread(
                                meta_path.write_text,
                                json.dumps(meta, ensure_ascii=False, indent=2),
                                encoding="utf-8",
                            )
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
                                await self.set(
                                    clean_url,
                                    content,
                                    mime_type,
                                    template=template,
                                )
                                logger.info(
                                    f"[资源缓存] 成功下载并缓存静态资源 (模板: {template or 'global'}): {clean_url} ({len(content)} 字节)"
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
        """获取本地缓存文件汇总统计（支持按模板和分类聚合分析）。"""
        stats: dict[str, Any] = {
            "total_files": 0,
            "total_bytes": 0,
            "total_access_count": 0,
            "by_category": {
                "fonts": {"files": 0, "bytes": 0},
                "css": {"files": 0, "bytes": 0},
                "images": {"files": 0, "bytes": 0},
                "scripts": {"files": 0, "bytes": 0},
            },
            "by_template": {},
        }

        # 扫描 meta 目录提取详细统计
        if self.meta_dir.is_dir():
            for meta_file in self.meta_dir.glob("*.json"):
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    size = meta.get("size", 0)
                    category = meta.get("category", "images")
                    t_name = meta.get("template", "global")
                    access_count = meta.get("access_count", 1)

                    stats["total_files"] += 1
                    stats["total_bytes"] += size
                    stats["total_access_count"] += access_count

                    if category in stats["by_category"]:
                        stats["by_category"][category]["files"] += 1
                        stats["by_category"][category]["bytes"] += size

                    if t_name not in stats["by_template"]:
                        stats["by_template"][t_name] = {
                            "files": 0,
                            "bytes": 0,
                            "access_count": 0,
                            "categories": {},
                        }
                    stats["by_template"][t_name]["files"] += 1
                    stats["by_template"][t_name]["bytes"] += size
                    stats["by_template"][t_name]["access_count"] += access_count

                    if category not in stats["by_template"][t_name]["categories"]:
                        stats["by_template"][t_name]["categories"][category] = 0
                    stats["by_template"][t_name]["categories"][category] += 1
                except Exception:
                    pass

        # 若 meta 为空则扫描磁盘文件作为兜底
        if stats["total_files"] == 0 and self.templates_dir.is_dir():
            for p in self.templates_dir.rglob("*"):
                if p.is_file():
                    stats["total_files"] += 1
                    stats["total_bytes"] += p.stat().st_size

        return stats

    async def list_resources(
        self, template: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        """获取所有缓存资源的详细列表，支持按模板和分类过滤。"""
        resources: list[dict[str, Any]] = []
        if not self.meta_dir.is_dir():
            return resources

        filter_template = self._sanitize_template_name(template) if template else None

        for meta_file in sorted(
            self.meta_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        ):
            try:
                raw = await asyncio.to_thread(meta_file.read_text, encoding="utf-8")
                meta = json.loads(raw)
                item_template = meta.get("template", "global")
                item_category = meta.get("category", "images")

                if (
                    filter_template
                    and item_template != filter_template
                    and filter_template != "all"
                ):
                    continue
                if category and item_category != category and category != "all":
                    continue

                # 检查文件是否实际存在
                f_path = Path(meta.get("file_path", ""))
                meta["exists"] = f_path.is_file()
                if meta["exists"]:
                    meta["size_formatted"] = f"{meta.get('size', 0) / 1024:.1f} KB"
                resources.append(meta)
            except Exception:
                pass

        return resources

    async def clear_cache(
        self, template: str | None = None, category: str | None = None
    ) -> dict[str, Any]:
        """清理满足条件的缓存文件及对应元数据。"""
        filter_template = self._sanitize_template_name(template) if template else None
        deleted_files = 0
        freed_bytes = 0

        if self.meta_dir.is_dir():
            for meta_file in list(self.meta_dir.glob("*.json")):
                try:
                    raw = await asyncio.to_thread(meta_file.read_text, encoding="utf-8")
                    meta = json.loads(raw)
                    item_template = meta.get("template", "global")
                    item_category = meta.get("category", "images")

                    should_delete = True
                    if (
                        filter_template
                        and filter_template != "all"
                        and item_template != filter_template
                    ):
                        should_delete = False
                    if category and category != "all" and item_category != category:
                        should_delete = False

                    if should_delete:
                        f_path = Path(meta.get("file_path", ""))
                        if f_path.is_file():
                            freed_bytes += f_path.stat().st_size
                            await asyncio.to_thread(f_path.unlink, True)
                            deleted_files += 1
                        await asyncio.to_thread(meta_file.unlink, True)
                except Exception as e:
                    logger.warning(f"清理缓存元数据文件失败 {meta_file}: {e}")

        # 如果全量清空，也清理整个 templates 目录与旧版目录
        if (not filter_template or filter_template == "all") and (
            not category or category == "all"
        ):
            for legacy_dir in [
                self.legacy_fonts_dir,
                self.legacy_css_dir,
                self.legacy_images_dir,
                self.legacy_scripts_dir,
            ]:
                if legacy_dir.is_dir():
                    for f in legacy_dir.glob("*"):
                        if f.is_file():
                            freed_bytes += f.stat().st_size
                            await asyncio.to_thread(f.unlink, True)
                            deleted_files += 1

        return {
            "deleted_files": deleted_files,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        }

    async def close(self) -> None:
        """关闭底层的 HTTP 客户端会话。"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
