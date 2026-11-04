"""固定主题素材的按需下载接口，每个请求只处理一个文件。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiohttp
from astrbot.api.star import StarTools

from ....shared.constants import (
    DEFAULT_CDN_HOST,
    GITHUB_REPO_BRANCH,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
    PLUGIN_NAME,
)
from ....utils.cdn_utils import normalize_cdn_base_url
from ....utils.logger import logger
from ...reporting.template_asset_catalog import RESOURCE_FILES
from ...reporting.template_resources import TemplateResourceStore
from ..download_control import DownloadCancelled, DownloadControl
from ..web_compat import WebApiResponse, error_response, json_response, request


class TemplateResourceRoutes:
    """素材状态无联网，下载目标严格由仓库清单控制。"""

    def __init__(self, downloads: DownloadControl | None = None) -> None:
        self.downloads = downloads or DownloadControl()

    async def api_get_resources(self) -> WebApiResponse:
        """查询各主题本地资源，以便关闭页面后继续补齐。

        Returns:
            插件管理目录及各主题文件的可用状态。
        """
        try:
            store = TemplateResourceStore(Path(StarTools.get_data_dir(PLUGIN_NAME)), "")
            groups = await asyncio.to_thread(store.status)
            return json_response(
                {
                    "status": "ok",
                    "data": {"directory": str(store.directory), "groups": groups},
                }
            )
        except OSError:
            logger.warning("读取模板素材目录失败，请检查插件 data 目录权限")
            return error_response(
                "无法读取模板素材目录，请检查插件 data 目录权限后刷新", status_code=500
            )

    async def api_download_resource(self) -> WebApiResponse:
        """补齐一个固定文件，由前端组织主题队列并展示逐文件进度。

        Returns:
            已就绪的文件名；非法请求返回 400，下载未完成返回 502。
        """
        try:
            body = await request.json()
            if type(body) is not dict:
                raise ValueError("无效请求")
            name, raw_cdn = body.get("name"), body.get("cdn_base_url", DEFAULT_CDN_HOST)
            if not isinstance(name, str) or name not in RESOURCE_FILES:
                raise ValueError("未知素材")
            if not isinstance(raw_cdn, str):
                raise ValueError("无效 CDN")
            cdn = normalize_cdn_base_url(raw_cdn) or DEFAULT_CDN_HOST
        except (ValueError, TypeError):
            return error_response(
                "请选择列表中的素材和有效 CDN 地址，不支持自定义文件路径",
                status_code=400,
            )
        base = f"{cdn}/gh/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}@{GITHUB_REPO_BRANCH}/assets"
        store = TemplateResourceStore(Path(StarTools.get_data_dir(PLUGIN_NAME)), base)
        try:
            async with (
                self.downloads.track(body.get("download_id")),
                aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=45), trust_env=True
                ) as session,
            ):
                await store.ensure(name, session)
            return json_response(
                {"status": "ok", "data": {"name": name, "available": True}}
            )
        except DownloadCancelled:
            return error_response("下载已取消，已完成的素材会保留", status_code=409)
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError) as error:
            logger.warning(f"模板素材 {name} 下载未完成：{error}")
            return error_response(
                "素材下载未完成，请检查网络或更换 CDN 后重试；已下载文件会保留",
                status_code=502,
            )
