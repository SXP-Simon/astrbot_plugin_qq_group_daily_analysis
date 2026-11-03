"""Typst 图片本地化、像素预算与派生 PNG 缓存。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import shutil
import uuid
from io import BytesIO
from typing import TYPE_CHECKING

import aiohttp
from PIL import Image, ImageChops, ImageDraw, ImageOps

from ...utils.logger import logger
from .template_asset_catalog import RESOURCE_FILES

if TYPE_CHECKING:
    from pathlib import Path

    from .template_resources import TemplateResourceStore


class TypstAssets:
    """单次任务的图片本地化，CDN 缓存与编译目录彼此隔离。"""

    def __init__(
        self,
        data_dir: Path,
        job_dir: Path,
        session: aiohttp.ClientSession,
        *,
        resource_store: TemplateResourceStore | None = None,
    ):
        self.cache = data_dir / "typst" / "assets"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.job_dir = job_dir
        self.session = session
        self.resource_store = resource_store
        self.network_deadline = (
            resource_store.network_deadline if resource_store else None
        )
        self.network_budget_exhausted = False
        self.semaphore = asyncio.Semaphore(6)
        self.image_semaphore = asyncio.Semaphore(1)
        self.failed: set[str] = set()

    async def localize(
        self, source: str, opacity: float = 1.0, *, oval: bool = False
    ) -> str:
        """将图片解码为本次任务内的 PNG，缺图返回空路径。

        Args:
            source: 可信配置或头像服务给出的 HTTP(S) 地址、Data URI。
            opacity: 人格水印的透明度，不影响头像或角色装饰。
            oval: Maria 肖像需要与原版一致的 5:6 椭圆裁切。

        Returns:
            相对编译根目录的路径；缺失图片由模板绘制占位。
        """
        if not source:
            return ""
        variant = "oval:" if oval else ""
        key = hashlib.sha256(f"{variant}{opacity}:{source}".encode()).hexdigest()
        target = self.job_dir / f"{key}.png"
        if target.is_file():
            return target.name
        cached = self.cache / f"{key}.png"
        async with self.semaphore:
            try:
                if cached.is_file():
                    await asyncio.to_thread(shutil.copyfile, cached, target)
                    return target.name
                if source in self.failed:
                    return ""
                payload = await self._read_source(source)
                await self._process_image(payload, target, cached, opacity, oval)
                return target.name
            except (
                aiohttp.ClientError,
                TimeoutError,
                ValueError,
                OSError,
                Image.DecompressionBombError,
            ) as error:
                self.failed.add(source)
                if (
                    isinstance(error, TimeoutError)
                    and self.network_deadline is not None
                    and asyncio.get_running_loop().time() >= self.network_deadline
                ):
                    self.network_budget_exhausted = True
                if cached.is_file():
                    await asyncio.to_thread(shutil.copyfile, cached, target)
                    return target.name
                logger.warning("Typst 素材获取失败，本次使用占位装饰")
                return ""

    async def _process_image(
        self, payload: bytes, target: Path, cached: Path, opacity: float, oval: bool
    ) -> None:
        """逐图持有像素预算，取消时等待解码结束并保留取消语义。

        Args:
            payload: 尚未解码的图片字节。
            target: 本次任务的目标文件。
            cached: 派生图片缓存路径。
            opacity: 水印透明度。
            oval: 是否需要椭圆裁切。

        Raises:
            asyncio.CancelledError: 图像线程退出后继续传递取消请求。
        """
        async with self.image_semaphore:
            processing = asyncio.create_task(
                asyncio.to_thread(
                    self._save_image, payload, target, cached, opacity, oval
                )
            )
            try:
                await asyncio.shield(processing)
            except asyncio.CancelledError:
                # 解码错误不能覆盖取消请求，也不能在清理目录后继续写入。
                await asyncio.shield(asyncio.gather(processing, return_exceptions=True))
                raise

    async def _read_source(self, source: str) -> bytes:
        """解析图片来源，仓库装饰优先读取本地资源，头像保持独立缓存策略。

        Args:
            source: 已由业务层解析的图片地址或 Data URI。

        Returns:
            待像素校验和转换的图片字节。

        Raises:
            ValueError: 来源类型无效或超过字节预算。
            aiohttp.ClientError: 远程素材获取失败。
        """
        if source.startswith("data:"):
            return base64.b64decode(source.split(",", 1)[1], validate=True)
        if not source.startswith(("https://", "http://")):
            raise ValueError("不支持的图片来源")
        if self.resource_store and source.startswith(
            self.resource_store.base_url + "/"
        ):
            name = source.removeprefix(self.resource_store.base_url + "/")
            if name in RESOURCE_FILES:
                path = await self.resource_store.ensure(name, self.session)
                return await asyncio.to_thread(path.read_bytes)
        if (
            self.network_deadline is not None
            and asyncio.get_running_loop().time() >= self.network_deadline
        ):
            raise TimeoutError("图片网络预算已耗尽")
        async with (
            asyncio.timeout_at(self.network_deadline),
            self.session.get(source) as response,
        ):
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                data.extend(chunk)
                if len(data) > 8 * 1024 * 1024:
                    raise ValueError("图片超过 8 MiB")
            return bytes(data)

    @staticmethod
    def _save_image(
        payload: bytes, target: Path, cached: Path, opacity: float, oval: bool = False
    ) -> None:
        """在工作线程中检查图片像素并原子写入缓存和任务目录。

        Args:
            payload: 网络或头像字节。
            target: 任务内图片路径。
            cached: 持久缓存路径。
            opacity: 人格水印的不透明度。
            oval: 预先生成与浮雕框一致的透明椭圆头像。

        Raises:
            ValueError: 输入图片超出允许像素或字节范围。
        """
        if len(payload) > 8 * 1024 * 1024:
            raise ValueError("图片超过 8 MiB")
        with Image.open(BytesIO(payload)) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("素材图片像素过多")
            # 先缩小原生 RGB/RGBA，避免复制完整大图；调色板及透明色先解析。
            if image.mode not in ("RGB", "RGBA") or "transparency" in image.info:
                image = image.convert("RGBA")
            # 保持原 RGBA 分支的一次重采样，不使用 JPEG draft 或整倍缩小。
            image.thumbnail((1600, 1600), reducing_gap=None)
            if image.mode != "RGBA":
                image = image.convert("RGBA")
            if oval:
                image = ImageOps.fit(image, (200, 240), method=Image.Resampling.LANCZOS)
                mask = Image.new("L", image.size)
                ImageDraw.Draw(mask).ellipse((0, 0, 199, 239), fill=255)
                image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
            if opacity < 1:
                image.putalpha(
                    image.getchannel("A").point(
                        lambda alpha: int(alpha * max(0, opacity))
                    )
                )
            output = BytesIO()
            image.save(output, format="PNG")
        result = output.getvalue()
        temporary = cached.with_name(f".{cached.stem}.{uuid.uuid4().hex}.part")
        try:
            temporary.write_bytes(result)
            temporary.replace(cached)
            target.write_bytes(result)
        finally:
            temporary.unlink(missing_ok=True)
