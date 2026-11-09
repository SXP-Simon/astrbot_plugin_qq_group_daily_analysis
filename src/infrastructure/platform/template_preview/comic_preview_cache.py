"""漫画样图查找、下载与分组缓存。"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import aiohttp

from ....shared.comic_presets import COMIC_PRESETS
from ....shared.constants import DEFAULT_ASSETS_CDN_URL
from ....utils.logger import logger
from .image_cache import PreviewImageCache

if TYPE_CHECKING:
    from ....application.services.template_command_service import TemplateCommandService


class ComicPreviewCache(PreviewImageCache):
    """供群聊预览与数据管理共用的漫画样图缓存。"""

    def __init__(
        self, directory: Path, template_service: TemplateCommandService
    ) -> None:
        super().__init__(directory)
        self.template_service = template_service

    async def get_preview(
        self,
        preset_id: str,
        variant: Literal["thumbnail", "preview"],
        *,
        deadline: float,
        refresh: bool = False,
    ) -> Path:
        """读取或重新获取指定样图，失败时保留已有缓存。

        Args:
            preset_id: 内置风格标识。
            variant: 缩略图或完整图。
            deadline: 请求截止时间（单调时钟）。
            refresh: 重新获取已有样图。

        Returns:
            平台可发送的 JPEG 路径。

        Raises:
            ValueError: 风格标识无效。
            OSError: 样图无法获取。
        """
        if preset_id not in COMIC_PRESETS:
            raise ValueError("未知漫画风格")
        relative = f"comic_previews/{preset_id}/{variant}.webp"
        local = Path(self.template_service.plugin_root) / "assets" / relative
        if local.is_file() and not local.is_symlink():
            source = str(local)
        else:
            config = self.template_service.config_provider
            cdn = (
                config.get_template_assets_base_url()
                if config
                else DEFAULT_ASSETS_CDN_URL
            )
            source = f"{cdn}/{relative}"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OSError("无法获取漫画样图，请检查样图来源或网络后重试")
        try:
            async with asyncio.timeout(min(4, remaining)):
                return Path(
                    await self.get_jpeg(
                        source,
                        relative_stem=Path(preset_id) / variant,
                        refresh=refresh,
                    )
                )
        except (OSError, ValueError, aiohttp.ClientError) as exc:
            logger.debug(
                "漫画样图读取失败: style=%s error=%s", preset_id, type(exc).__name__
            )
            raise OSError("无法获取漫画样图，请检查样图来源或网络后重试") from exc
