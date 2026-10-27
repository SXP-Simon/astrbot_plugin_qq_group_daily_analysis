"""机器人预览图的 JPEG 转换与有界磁盘缓存。"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import aiohttp
from PIL import Image, ImageOps

from ....utils.logger import logger


class PreviewImageCache:
    """复用发送用 JPEG，不改动仓库里的 WebP 原图。"""

    MAX_SOURCE_BYTES = 8 * 1024 * 1024
    MAX_PIXELS = 40_000_000
    MAX_ENTRIES = 64
    REMOTE_TTL_SECONDS = 24 * 60 * 60

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = asyncio.Lock()

    async def get_jpeg(self, source: str) -> str:
        """获取本地文件或 HTTP 图片对应的 JPEG 缓存。

        Args:
            source: 原图路径、file URI 或 HTTP(S) 地址。

        Returns:
            可供平台发送的 JPEG 文件绝对路径。

        Raises:
            ValueError: 原图超限、不是可解码图片或地址协议不受支持。
            OSError: 本地原图或缓存无法读写。
            aiohttp.ClientError: 远程图片请求失败。
        """
        parts = urlsplit(source)
        remote = parts.scheme in {"http", "https"}
        started = time.monotonic()
        logger.debug(
            "[模板预览] 图片准备: source_type=%s", "HTTP" if remote else "local"
        )
        local: Path | None = None
        if remote:
            identity = source
        else:
            if parts.scheme == "file":
                path = unquote(parts.path)
                if parts.netloc and parts.netloc.casefold() != "localhost":
                    path = f"//{parts.netloc}{path}"
                elif (
                    os.name == "nt"
                    and len(path) >= 3
                    and path[0] == "/"
                    and path[2] == ":"
                ):
                    path = path[1:]
                local = Path(path)
            elif "://" not in source:
                local = Path(source)
            else:
                raise ValueError("预览图片地址协议不受支持")
            local = local.resolve()
            stat = local.stat()
            if stat.st_size > self.MAX_SOURCE_BYTES:
                raise ValueError("预览图片超过 8 MiB")
            identity = f"{local}:{stat.st_mtime_ns}:{stat.st_size}"
        key = hashlib.sha256(f"jpeg-v1:{identity}".encode()).hexdigest()
        target = self.directory / f"{key}.jpg"
        async with self._lock:
            if (
                target.is_file()
                and target.stat().st_size
                and (
                    not remote
                    or time.time() - target.stat().st_mtime < self.REMOTE_TTL_SECONDS
                )
            ):
                logger.debug("[模板预览] JPEG 缓存命中: key=%s", key[:12])
                return str(target.resolve())
            logger.debug("[模板预览] JPEG 缓存需生成或刷新: key=%s", key[:12])
            if remote:
                async with (
                    aiohttp.ClientSession(
                        trust_env=True, timeout=aiohttp.ClientTimeout(total=20)
                    ) as session,
                    session.get(source) as response,
                ):
                    logger.debug(
                        "[模板预览] 图片 HTTP 响应: key=%s status=%s",
                        key[:12],
                        response.status,
                    )
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        data.extend(chunk)
                        if len(data) > self.MAX_SOURCE_BYTES:
                            raise ValueError("预览图片超过 8 MiB")
                    raw = bytes(data)
            else:
                assert local is not None
                raw = await asyncio.to_thread(local.read_bytes)
            await asyncio.to_thread(self._write_jpeg, raw, target)
            logger.debug(
                "[模板预览] JPEG 准备完成: key=%s source_bytes=%s elapsed_ms=%s",
                key[:12],
                len(raw),
                round((time.monotonic() - started) * 1000),
            )
            return str(target.resolve())

    def _write_jpeg(self, raw: bytes, target: Path) -> None:
        """在线程中解码、转码并原子替换缓存，同时淘汰旧文件。

        Args:
            raw: 已受大小限制的原图内容。
            target: 此原图对应的缓存文件。
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{target.stem}.{uuid4().hex}.tmp")
        try:
            with Image.open(BytesIO(raw)) as image:
                if image.width * image.height > self.MAX_PIXELS:
                    raise ValueError("预览图片像素过大")
                image.seek(0)
                image = ImageOps.exif_transpose(image)
                rgba = image.convert("RGBA")
                result = Image.new("RGB", rgba.size, "white")
                result.paste(rgba, mask=rgba.getchannel("A"))
                result.save(temporary, format="JPEG", quality=88, optimize=True)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        entries = sorted(self.directory.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
        for expired in entries[: -self.MAX_ENTRIES]:
            expired.unlink(missing_ok=True)
