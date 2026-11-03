"""Typst 的插件数据目录字体与 CDN 素材缓存。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import time
import uuid
from io import BytesIO
from typing import TYPE_CHECKING, TypedDict

import aiohttp
from PIL import Image, ImageChops, ImageDraw, ImageOps

from ...utils.logger import logger

if TYPE_CHECKING:
    from pathlib import Path

# 字体始终写入插件 data 目录；来源是固定上游，不接受任意下载 URL 或目标路径。
FONT_SOURCES = {
    "NotoSansSC.ttf": "gh/google/fonts@main/ofl/notosanssc/NotoSansSC[wght].ttf",
    "NotoSansTC.ttf": "gh/google/fonts@main/ofl/notosanstc/NotoSansTC[wght].ttf",
    "NotoSansJP.ttf": "gh/google/fonts@main/ofl/notosansjp/NotoSansJP[wght].ttf",
    "Outfit.ttf": "gh/google/fonts@main/ofl/outfit/Outfit[wght].ttf",
    "ShareTechMono.ttf": "gh/google/fonts@main/ofl/sharetechmono/ShareTechMono-Regular.ttf",
    "Inter.ttf": "gh/google/fonts@main/ofl/inter/Inter[opsz,wght].ttf",
    "JetBrainsMono.ttf": "gh/google/fonts@main/ofl/jetbrainsmono/JetBrainsMono[wght].ttf",
    "Oswald.ttf": "gh/google/fonts@main/ofl/oswald/Oswald[wght].ttf",
    "PatrickHand.ttf": "gh/google/fonts@main/ofl/patrickhand/PatrickHand-Regular.ttf",
    "ZCOOLKuaiLe.ttf": "gh/google/fonts@main/ofl/zcoolkuaile/ZCOOLKuaiLe-Regular.ttf",
    "ZCOOLXiaoWei.ttf": "gh/google/fonts@main/ofl/zcoolxiaowei/ZCOOLXiaoWei-Regular.ttf",
    "MaShanZheng.ttf": "gh/google/fonts@main/ofl/mashanzheng/MaShanZheng-Regular.ttf",
    # 完整可变宋体提供与 HTML 一致的字体名和全部字重，文件超过 CDN 体积限制。
    "NotoSerifSC.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC[wght].ttf",
    "NotoSerifTC.ttf": "gh/google/fonts@main/ofl/notoseriftc/NotoSerifTC[wght].ttf",
    "Cinzel.ttf": "gh/google/fonts@main/ofl/cinzel/Cinzel[wght].ttf",
    "CormorantGaramond.ttf": "gh/google/fonts@main/ofl/cormorantgaramond/CormorantGaramond[wght].ttf",
    "CormorantGaramond-Italic.ttf": "gh/google/fonts@main/ofl/cormorantgaramond/CormorantGaramond-Italic[wght].ttf",
    # 与原 ATRI 字体相同的 1.522 版；单文件超过 CDN 体积限制，直接读取固定官方源。
    "LXGWWenKai.ttf": "https://raw.githubusercontent.com/lxgw/LxgwWenKai/v1.522/fonts/TTF/LXGWWenKai-Regular.ttf",
    "LXGWWenKaiMono.ttf": "https://raw.githubusercontent.com/lxgw/LxgwWenKai/v1.522/fonts/TTF/LXGWWenKaiMono-Regular.ttf",
}


class TypstFontStatus(TypedDict):
    """WebUI 使用的受管理字体状态。"""

    directory: str
    files: list[str]
    missing: list[str]
    ready: bool


def typst_font_status(data_dir: Path) -> TypstFontStatus:
    """检查插件自己的字体目录，不扫描系统路径。

    Args:
        data_dir: 插件数据根目录。

    Returns:
        已安装的字体和仍需下载的预设文件。
    """
    directory = data_dir / "typst" / "fonts"
    files = sorted(
        p.name
        for p in directory.glob("*")
        if p.suffix.lower() in {".ttf", ".otf", ".ttc"} and p.is_file()
    )
    missing = [name for name in FONT_SOURCES if name not in files]
    return {
        "directory": str(directory),
        "files": files,
        "missing": missing,
        "ready": not missing,
    }


async def download_typst_fonts(data_dir: Path, cdn_base_url: str) -> TypstFontStatus:
    """将固定预设字体下载到插件目录，校验头部并原子替换。

    Args:
        data_dir: 插件数据根目录。
        cdn_base_url: 当前配置的 CDN 根地址。

    Returns:
        下载后的字体状态；已存在的预设不会重复下载。

    Raises:
        ValueError: CDN 返回的内容过大或不是字体。
        aiohttp.ClientError: 下载失败，已经成功的文件仍可复用。
    """
    directory = data_dir / "typst" / "fonts"
    directory.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=180), trust_env=True
    ) as session:
        for name in typst_font_status(data_dir)["missing"]:
            target = directory / name
            temporary = directory / f".{name}.{uuid.uuid4().hex}.part"
            try:
                source = FONT_SOURCES[name]
                url = (
                    source
                    if source.startswith("https://")
                    else f"{cdn_base_url.rstrip('/')}/{source}"
                )
                async with session.get(url) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        payload.extend(chunk)
                        if len(payload) > 32 * 1024 * 1024:
                            raise ValueError("字体下载超过 32 MiB，请检查 CDN 响应")
                if len(payload) < 1024 or bytes(payload[:4]) not in (
                    b"ttcf",
                    b"OTTO",
                    b"\x00\x01\x00\x00",
                ):
                    raise ValueError("CDN 返回的内容不是有效字体")
                await asyncio.to_thread(temporary.write_bytes, payload)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
    return typst_font_status(data_dir)


class TypstAssets:
    """单次任务的图片本地化，CDN 缓存与编译目录彼此隔离。"""

    def __init__(self, data_dir: Path, job_dir: Path, session: aiohttp.ClientSession):
        self.cache = data_dir / "typst" / "assets"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.job_dir = job_dir
        self.session = session
        self.semaphore = asyncio.Semaphore(6)
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
        if not source or source in self.failed:
            return ""
        variant = "oval:" if oval else ""
        key = hashlib.sha256(f"{variant}{opacity}:{source}".encode()).hexdigest()
        target = self.job_dir / f"{key}.png"
        if target.is_file():
            return target.name
        cached = self.cache / f"{key}.png"
        async with self.semaphore:
            try:
                if source.startswith("data:"):
                    payload = base64.b64decode(source.split(",", 1)[1], validate=True)
                elif source.startswith(("https://", "http://")):
                    if (
                        cached.is_file()
                        and time.time() - cached.stat().st_mtime < 7 * 86400
                    ):
                        cached_data = await asyncio.to_thread(cached.read_bytes)
                        await asyncio.to_thread(target.write_bytes, cached_data)
                        return target.name
                    async with self.session.get(source) as response:
                        response.raise_for_status()
                        data = bytearray()
                        async for chunk in response.content.iter_chunked(65536):
                            data.extend(chunk)
                            if len(data) > 8 * 1024 * 1024:
                                raise ValueError("图片超过 8 MiB")
                        payload = bytes(data)
                else:
                    return ""
                await asyncio.to_thread(
                    self._save_image, payload, target, cached, opacity, oval
                )
                return target.name
            except (aiohttp.ClientError, TimeoutError, ValueError, OSError):
                self.failed.add(source)
                if cached.is_file():
                    cached_data = await asyncio.to_thread(cached.read_bytes)
                    await asyncio.to_thread(target.write_bytes, cached_data)
                    return target.name
                logger.warning("Typst 素材获取失败，本次使用占位装饰")
                return ""

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
