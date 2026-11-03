"""内置主题素材的本地优先存储，不缓存模板代码或任意用户路径。"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from typing import TypedDict
from xml.etree import ElementTree

import aiohttp
from PIL import Image

from ...shared.trace_context import TraceContext
from ...utils.logger import logger
from .template_asset_catalog import RESOURCE_FILES, THEME_FILES, THEME_VECTORS

REPOSITORY_ASSETS = Path(__file__).resolve().parents[3] / "assets"


class TemplateResourceFile(TypedDict):
    """固定清单中的单个资源状态。"""

    name: str
    available: bool


class TemplateResourceGroup(TypedDict):
    """WebUI 按主题展示的本地资源清单。"""

    theme: str
    files: list[TemplateResourceFile]


class TemplateResourceStore:
    """开发仓库与插件 data 目录共用的资源读取规则。"""

    def __init__(self, data_dir: Path, base_url: str) -> None:
        self.directory = data_dir / "typst" / "resources"
        self.base_url = base_url.rstrip("/")
        self.local_hits = 0
        self.downloads = 0
        self.failed: set[str] = set()

    def local_path(self, name: str) -> Path | None:
        """只接受固定资源清单，优先使用受管理文件，其次使用开发仓库资源。

        Args:
            name: 含主题前缀的资源相对路径。

        Returns:
            已存在的本地文件，发布包没有仓库素材时返回空。

        Raises:
            ValueError: 请求了清单之外的文件。
        """
        if name not in RESOURCE_FILES:
            raise ValueError("未知模板资源，请刷新列表后重试")
        for root in (self.directory, REPOSITORY_ASSETS):
            path = root / name
            if (
                path.is_file()
                and path.stat().st_size > 0
                and path.resolve().is_relative_to(root.resolve())
            ):
                return path
        return None

    def status(self) -> list[TemplateResourceGroup]:
        """返回各主题资源状态，不触发联网。

        Returns:
            完整固定清单及每个文件的可用状态。
        """
        return [
            {
                "theme": theme,
                "files": [
                    {"name": name, "available": self.local_path(name) is not None}
                    for name in names
                ],
            }
            for theme, names in THEME_FILES.items()
        ]

    async def ensure(self, name: str, session: aiohttp.ClientSession) -> Path:
        """缺失时流式下载，校验完成后原子落盘，已存在的文件不联网。

        Args:
            name: 固定清单中的相对路径。
            session: 本次请求或渲染持有的会话。

        Returns:
            可直接读取的资源路径。

        Raises:
            ValueError: 未知文件、超大响应或无效图片。
            aiohttp.ClientError: CDN 下载失败。
            OSError: 本地资源无法写入。
        """
        existing = self.local_path(name)
        if existing:
            self.local_hits += 1
            return existing
        target = self.directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.resolve().is_relative_to(self.directory.resolve()):
            raise ValueError("模板资源目录非法，请检查本地符号链接")
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        try:
            size = 0
            async with session.get(f"{self.base_url}/{name}") as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    async for chunk in response.content.iter_chunked(65536):
                        size += len(chunk)
                        if size > 8 * 1024 * 1024:
                            raise ValueError("模板资源超过 8 MiB，请检查 CDN 响应")
                        await asyncio.to_thread(output.write, chunk)
            await asyncio.to_thread(self._validate, temporary, name)
            temporary.replace(target)
            self.downloads += 1
            return target
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate(path: Path, name: str) -> None:
        """校验图片格式与预算，避免将 CDN 错误页面存成长期本地资源。

        Args:
            path: 尚未发布的下载临时文件。
            name: 固定清单中的原始文件名。

        Raises:
            ValueError: 响应不是允许的图片或超出像素预算。
        """
        if name.endswith(".svg"):
            payload = path.read_bytes()
            if len(payload) > 256 * 1024 or b"<!DOCTYPE" in payload.upper():
                raise ValueError("SVG 内容无效或过大")
            try:
                root = ElementTree.fromstring(payload)
            except ElementTree.ParseError as error:
                raise ValueError("CDN 返回的内容不是有效 SVG") from error
            if root.tag.rsplit("}", 1)[-1] != "svg":
                raise ValueError("CDN 返回的内容不是 SVG")
            return
        with Image.open(path) as image:
            if image.width * image.height > 16_000_000:
                raise ValueError("模板图片超过像素预算")
            image.verify()

    async def stage_vectors(self, theme: str, job_dir: Path) -> None:
        """将图标复制到隔离任务；网络缺图只留白，不中断整份报告。

        Args:
            theme: 当前内置主题。
            job_dir: 编译使用的隔离目录。
        """

        async def stage(filename: str, session: aiohttp.ClientSession) -> None:
            # 并发复制与下载；短网络预算为后续编译保留时间。
            name = f"{theme}/{filename}"
            target = job_dir / filename
            try:
                source = await self.ensure(name, session)
                await asyncio.to_thread(shutil.copyfile, source, target)
            except (aiohttp.ClientError, TimeoutError, ValueError, OSError):
                self.failed.add(name)
                target.write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"/>',
                    encoding="utf-8",
                )

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5),
            connector=aiohttp.TCPConnector(limit=6),
            trust_env=True,
        ) as session:
            await asyncio.gather(
                *(stage(filename, session) for filename in THEME_VECTORS.get(theme, ()))
            )
        if self.failed:
            logger.warning(
                f"Typst 有 {len(self.failed)} 个图标获取失败，本次留白；可在 WebUI 补齐素材"
            )
            trace = TraceContext.current()
            if trace:
                trace.metadata["has_warnings"] = True
                trace.metadata["typst_missing_resources"] = sorted(self.failed)
