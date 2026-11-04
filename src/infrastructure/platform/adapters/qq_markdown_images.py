"""QQ 本地图片素材上传与本次报告结束后的配额释放。"""

from __future__ import annotations

import asyncio
import hashlib
import re
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

import aiohttp

from ....utils.logger import logger

if TYPE_CHECKING:
    from botpy.http import BotHttp, Route


class QQMarkdownImages:
    """通过 botpy 鉴权客户端管理当前适配器上传的报告素材。

    Args:
        http: 当前机器人的 botpy HTTP 客户端，不另外保存访问令牌。
    """

    def __init__(self, http: BotHttp) -> None:
        self.http = http
        self.pending: dict[str, str] = {}

    async def upload(self, image: bytes) -> str:
        """将 PNG 直传 QQ，返回可用于同条 Markdown 的素材引用。

        Args:
            image: 原生渲染得到的 PNG 字节。

        Returns:
            与当前机器人绑定的 qqbot-media 引用。

        Raises:
            ValueError: PNG 为空、超过平台限制或接口响应不完整。
            TimeoutError: 上传超过三十秒。
            aiohttp.ClientError: 图片直传失败。
        """
        if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > 10 * 1024**2:
            raise ValueError("QQ Markdown 素材必须是 10 MiB 以内的 PNG")
        md5 = hashlib.md5(image, usedforsecurity=False).hexdigest()
        async with asyncio.timeout(30):
            prepared = await self.http.request(
                _material_route("POST", "/v2/media-images/prepare"),
                json={
                    "file_name": f"daily-analysis-{md5}.png",
                    "file_size": len(image),
                    "content_type": "image/png",
                    "md5": md5,
                    "sha1": hashlib.sha1(image, usedforsecurity=False).hexdigest(),
                },
            )
            if not isinstance(prepared, dict):
                raise ValueError("QQ 图片素材预上传响应无效")
            upload_id = prepared.get("upload_id")
            signed_url = prepared.get("presigned_url")
            if (
                not isinstance(upload_id, str)
                or not upload_id
                or not isinstance(signed_url, str)
            ):
                raise ValueError("QQ 图片素材预上传响应缺少字段")
            etag = await _put_png(signed_url, image)
            completed = await self.http.request(
                _material_route("POST", "/v2/media-images/complete"),
                json={"upload_id": upload_id, "md5": etag},
            )
        if not isinstance(completed, dict):
            raise ValueError("QQ 图片素材完成响应无效")
        reference, image_id = completed.get("url"), completed.get("image_id")
        if not isinstance(reference, str) or not re.fullmatch(
            r"qqbot-media://image/v1/[A-Za-z0-9_-]+", reference
        ):
            raise ValueError("QQ 图片素材没有返回有效引用")
        if not isinstance(image_id, str) or not image_id or len(image_id) > 256:
            raise ValueError("QQ 图片素材缺少有效标识")
        self.pending[reference] = image_id
        return reference

    async def release(self, content: str) -> None:
        """释放本条报告拥有的素材，已发送消息中的图片不受影响。

        Args:
            content: 报告正文，只清理其中实际引用且由本实例上传的素材。
        """
        references = set(
            re.findall(r"\((qqbot-media://image/v1/[A-Za-z0-9_-]+)\)", content)
        )
        for reference, image_id in tuple(self.pending.items()):
            if reference not in references:
                continue
            try:
                async with asyncio.timeout(5):
                    result = await self.http.request(
                        _material_route(
                            "DELETE",
                            f"/v2/media-images/{quote(image_id, safe='')}/delete",
                        )
                    )
                    if not isinstance(result, dict):
                        raise ValueError("QQ 图片素材删除未确认成功")
                self.pending.pop(reference, None)
            except Exception as exc:
                logger.warning(
                    "[QQOfficial] 报告图片素材清理失败，暂时保留: %s",
                    type(exc).__name__,
                )


def _material_route(method: str, path: str) -> Route:
    """为三个素材端点使用官方统一域名，避免修改旧 SDK 的全局路由。

    Args:
        method: 官方接口的 HTTP 方法。
        path: 固定的素材端点路径，动态标识已编码。

    Returns:
        继续由 botpy 负责鉴权与沙箱设置的路由。
    """
    from botpy.http import Route

    class MaterialRoute(Route):
        DOMAIN = "api.bot.qq.com"

    return MaterialRoute(method, path)


async def _put_png(url: str, image: bytes) -> str:
    """在独立 HTTP 会话直传图片，避免把机器人鉴权头交给 COS。

    Args:
        url: QQ 返回的 HTTPS 预签名上传地址。
        image: 已校验的 PNG 字节。

    Returns:
        COS 返回的对象 ETag，供完成上传时校验。

    Raises:
        ValueError: 上传地址、响应状态或 ETag 无效。
        aiohttp.ClientError: HTTP 直传失败。
    """
    address = urlsplit(url)
    if (
        address.scheme != "https"
        or not address.hostname
        or address.username
        or address.password
    ):
        raise ValueError("QQ 图片素材直传地址无效")
    async with (
        aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=25), trust_env=True
        ) as session,
        session.put(
            url,
            data=image,
            headers={"Content-Type": "image/png"},
            allow_redirects=False,
        ) as response,
    ):
        response.raise_for_status()
        etag = response.headers.get("ETag", "").strip('"')
        if response.status not in {200, 201, 204} or not re.fullmatch(
            r"[0-9a-fA-F]{32}", etag
        ):
            raise ValueError("QQ 图片素材直传缺少有效 ETag")
        return etag
