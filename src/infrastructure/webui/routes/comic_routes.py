"""漫画样图缓存与轮换进度的管理接口。"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from astrbot.api.star import StarTools

from ....domain.value_objects.group_session import GroupSession
from ....shared.constants import PLUGIN_NAME
from ....shared.type_guards import is_string_mapping
from ...config.comic_style_rotation import list_comic_rotation, reset_comic_rotation
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from ...platform.template_preview.comic_preview_cache import ComicPreviewCache


class ComicRoutes:
    """处理漫画专属资源与状态。"""

    def __init__(self, preview_cache: ComicPreviewCache | None = None) -> None:
        self.preview_cache = preview_cache

    async def api_refresh_preview(self) -> WebApiResponse:
        """重新获取一张内置样图，并保留下载失败前的缓存。"""
        try:
            body = await request.json()
            if not is_string_mapping(body):
                raise ValueError("缺少样图信息")
            preset_id, variant = body.get("preset_id"), body.get("variant")
            if not isinstance(preset_id, str) or variant not in (
                "thumbnail",
                "preview",
            ):
                raise ValueError("请指定有效的风格和样图类型")
            if self.preview_cache is None:
                return error_response("漫画样图缓存未初始化", status_code=503)
            await self.preview_cache.get_preview(
                preset_id,
                "thumbnail" if variant == "thumbnail" else "preview",
                deadline=time.monotonic() + 10,
                refresh=True,
            )
            return json_response({"status": "ok", "data": {"success": True}})
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        except OSError as exc:
            return error_response(str(exc), status_code=502)

    async def api_rotation(self) -> WebApiResponse:
        """查看已有的漫画风格轮换记录。"""
        path = StarTools.get_data_dir(PLUGIN_NAME) / "comic_style_rotation.json"
        try:
            items = await asyncio.to_thread(list_comic_rotation, path)
            return json_response({"status": "ok", "data": {"items": items}})
        except (OSError, ValueError):
            return error_response(
                "无法读取漫画轮换进度，请刷新或重置全部进度", status_code=500
            )

    async def api_reset_rotation(self) -> WebApiResponse:
        """重置共享、单群或全部风格进度。"""
        try:
            body = await request.json()
            if not is_string_mapping(body):
                raise ValueError("缺少轮换范围")
            scope = body.get("scope")
            session = None
            if scope == "group":
                platform_id, group_id = body.get("platform_id"), body.get("group_id")
                if (
                    not isinstance(platform_id, str)
                    or not platform_id.strip()
                    or not isinstance(group_id, str)
                    or not group_id.strip()
                ):
                    raise ValueError("请指定机器人实例与群号")
                session = GroupSession(platform_id, group_id)
            elif scope not in ("global", "all"):
                raise ValueError("请指定有效的轮换范围")
        except ValueError as exc:
            return error_response(str(exc), status_code=400)
        path = StarTools.get_data_dir(PLUGIN_NAME) / "comic_style_rotation.json"
        try:
            await asyncio.to_thread(
                reset_comic_rotation, path, session, all_scopes=scope == "all"
            )
            return json_response({"status": "ok", "data": {"success": True}})
        except (OSError, ValueError):
            return error_response(
                "无法重置漫画轮换进度，请检查状态文件", status_code=500
            )
