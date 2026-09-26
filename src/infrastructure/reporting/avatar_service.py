"""用户头像抓取与缓存管理服务

负责异步拉取用户头像、磁盘缓存、图片缩放、Base64 转换以及在 HTML 中的样式复用。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import re
import time
from io import BytesIO
from typing import TYPE_CHECKING

import aiohttp
from diskcache import Cache
from PIL import Image, UnidentifiedImageError

from ...utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

MAX_CONCURRENT_DOWNLOADS = 4
AVATAR_DOWNLOAD_RETRY_TIMES = 3
AVATAR_CACHE_EXPIRE_TIME = 259200
AVATAR_FAILURE_CACHE_EXPIRE_TIME = 60
AVATAR_MAX_EDGE_LENGTH = 96
TRANSPARENT_IMAGE_DATA_URI = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxIiBoZWlnaHQ9IjEiPjwvc3ZnPg=="
)


class AvatarService:
    """用户头像抓取、缓存与复用管理服务。"""

    def __init__(self, data_dir: Path):
        """初始化头像服务。

        Args:
            data_dir: 插件数据主目录。
        """
        self.data_dir = data_dir
        self._avatar_cache = Cache(str(self.data_dir / "avatar"))
        self._avatar_session_concurrent_semaphore = asyncio.Semaphore(
            MAX_CONCURRENT_DOWNLOADS
        )
        self._avatar_session: aiohttp.ClientSession | None = None
        self._avatar_session_lock = asyncio.Lock()
        self._avatar_failure_cache: dict[str, float] = {}

    @staticmethod
    def get_avatar_cache_key(
        avatar_id: str, avatar_cache_namespace: str | None = None
    ) -> str:
        """生成平台隔离的头像缓存键。

        Args:
            avatar_id: 用户唯一标识或头像 ID。
            avatar_cache_namespace: 平台命名空间（如 onebot, telegram 等）。

        Returns:
            带有命名空间前缀的缓存键字符串。
        """
        namespace = str(avatar_cache_namespace or "legacy").strip() or "legacy"
        return f"{namespace}:{avatar_id}"

    async def get_user_avatar(
        self,
        avatar_id: str,
        avatar_url_getter: Callable | None = None,
        avatar_cache_namespace: str | None = None,
    ) -> str:
        """获取用户头像的 Base64 Data URI。

        支持磁盘持久化缓存及短时失败熔断，获取失败时自动回退为默认占位头像。

        Args:
            avatar_id: 用户唯一标识。
            avatar_url_getter: 自定义头像 URL/Data 异步获取回调。
            avatar_cache_namespace: 平台命名空间。

        Returns:
            头像的 Base64 Data URI 字符串。
        """
        cache_key = self.get_avatar_cache_key(avatar_id, avatar_cache_namespace)

        # 1. 检查磁盘缓存
        if cache_key in self._avatar_cache:
            data = self._avatar_cache[cache_key]
            if isinstance(data, str):
                return data
            return str(data)

        failed_until = self._avatar_failure_cache.get(cache_key, 0)
        if failed_until > time.monotonic():
            return self.get_default_avatar_base64()
        self._avatar_failure_cache.pop(cache_key, None)

        # 2. 尝试拉取头像数据流
        avatar_bytes = await self.get_user_avatar_bytes(avatar_id, avatar_url_getter)

        if not avatar_bytes:
            self._avatar_failure_cache[cache_key] = (
                time.monotonic() + AVATAR_FAILURE_CACHE_EXPIRE_TIME
            )
            logger.debug(f"获取用户头像失败 {avatar_id}，本次将使用回退头像")
            return self.get_default_avatar_base64()

        # 3. 转换并缓存
        avatar = self.b64_with_mime(self.resize_avatar_bytes(avatar_bytes))
        if avatar:
            self._avatar_cache.set(cache_key, avatar, expire=AVATAR_CACHE_EXPIRE_TIME)
            self._avatar_failure_cache.pop(cache_key, None)
            return avatar

        self._avatar_failure_cache[cache_key] = (
            time.monotonic() + AVATAR_FAILURE_CACHE_EXPIRE_TIME
        )
        return self.get_default_avatar_base64()

    async def get_user_avatar_bytes(
        self, user_id: str, avatar_url_getter: Callable | None = None
    ) -> bytes | None:
        """从网络下载或通过回调获取头像的原始字节数据。

        Args:
            user_id: 用户 ID。
            avatar_url_getter: 头像地址获取回调。

        Returns:
            头像字节数组，获取失败返回 None。
        """
        async with self._avatar_session_lock:
            if not self._avatar_session or self._avatar_session.closed:
                self._avatar_session = aiohttp.ClientSession(
                    trust_env=True, timeout=aiohttp.ClientTimeout(total=15)
                )

        async with self._avatar_session_concurrent_semaphore:
            avatar_url = None
            if avatar_url_getter:
                try:
                    result = await avatar_url_getter(user_id)
                    if result:
                        if result.startswith("http"):
                            avatar_url = result
                        elif result.startswith("base64://"):
                            return base64.b64decode(result[len("base64://") :])
                        elif result.startswith("data:"):
                            parts = result.split(",", 1)
                            if len(parts) == 2:
                                return base64.b64decode(parts[1])
                        else:
                            logger.warning(
                                "自定义头像地址获取器返回了非 HTTP 地址: "
                                f"{result[:50]}..."
                            )
                except Exception as e:
                    logger.warning(f"使用自定义头像地址获取器失败: {e}")

            if not avatar_url:
                if (
                    avatar_url_getter is None
                    and user_id.isdigit()
                    and 5 <= len(user_id) <= 12
                ):
                    avatar_url = (
                        f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=40"
                    )
                else:
                    return None

            safe_avatar_url = self.safe_url_for_log(avatar_url)
            failure_reason = ""
            for attempt in range(1, AVATAR_DOWNLOAD_RETRY_TIMES + 1):
                try:
                    async with self._avatar_session.get(avatar_url) as response:
                        if response.status == 200:
                            content = await response.read()
                            if not content:
                                failure_reason = "响应内容为空"
                            elif content.startswith(
                                (b"\xff\xd8", b"\x89PNG\r\n\x1a\n", b"GIF8")
                            ) or (
                                content.startswith(b"RIFF") and b"WEBP" in content[:16]
                            ):
                                return content
                            else:
                                logger.warning(
                                    f"下载的头像数据格式无效 ({safe_avatar_url})"
                                )
                                return None
                        else:
                            failure_reason = f"HTTP {response.status}"
                            if (
                                response.status not in {408, 429}
                                and response.status < 500
                            ):
                                logger.warning(
                                    f"下载头像失败 {safe_avatar_url}: {failure_reason}"
                                )
                                return None
                except (TimeoutError, aiohttp.ClientError) as e:
                    failure_reason = f"{type(e).__name__}: {e!r}"
                except Exception as e:
                    logger.warning(
                        f"下载头像发生未知错误 {safe_avatar_url}: "
                        f"{type(e).__name__}: {e!r}"
                    )
                    return None

                if attempt < AVATAR_DOWNLOAD_RETRY_TIMES:
                    logger.debug(
                        f"下载头像失败，将在短暂等待后重试 "
                        f"({attempt}/{AVATAR_DOWNLOAD_RETRY_TIMES}): "
                        f"{safe_avatar_url}，原因: {failure_reason}"
                    )
                    await asyncio.sleep(0.5 * attempt)

            logger.warning(
                f"下载头像网络错误，已重试 {AVATAR_DOWNLOAD_RETRY_TIMES} 次 "
                f"{safe_avatar_url}: {failure_reason}"
            )
            return None

    @staticmethod
    def resize_avatar_bytes(payload: bytes) -> bytes:
        """缩放头像图片尺寸以减小 HTML 嵌入体积。

        Args:
            payload: 头像原始二进制数据。

        Returns:
            压缩后的图片字节流；格式无效时原样返回。
        """
        try:
            with Image.open(BytesIO(payload)) as image:
                image.load()
                image.thumbnail(
                    (AVATAR_MAX_EDGE_LENGTH, AVATAR_MAX_EDGE_LENGTH),
                    Image.Resampling.LANCZOS,
                )
                output = BytesIO()
                if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                    image.convert("RGBA").save(output, format="PNG", optimize=True)
                else:
                    image.convert("RGB").save(
                        output,
                        format="JPEG",
                        quality=85,
                        optimize=True,
                    )
                return output.getvalue()
        except (OSError, UnidentifiedImageError):
            return payload

    @staticmethod
    def b64_with_mime(raw_bytes: bytes) -> str | None:
        """将二进制字节流转换为带 MIME 前缀的 Data URI。

        Args:
            raw_bytes: 图片二进制数据。

        Returns:
            Data URI 字符串，转换异常返回 None。
        """
        try:
            b64 = base64.b64encode(raw_bytes).decode("utf-8")
            mime = "image/jpeg"
            if raw_bytes.startswith(b"\x89PNG"):
                mime = "image/png"
            elif raw_bytes.startswith(b"GIF8"):
                mime = "image/gif"
            elif raw_bytes.startswith(b"RIFF") and b"WEBP" in raw_bytes[8:16]:
                mime = "image/webp"
            elif raw_bytes.startswith(b"\xff\xd8"):
                mime = "image/jpeg"

            return f"data:{mime};base64,{b64}"
        except Exception as e:
            logger.error(f"base64 转换失败: {e}", exc_info=True)
        return None

    @staticmethod
    def get_default_avatar_base64() -> str:
        """生成默认灰色占位头像的 Data URI。

        Returns:
            Base64 Data URI 字符串。
        """
        svg = '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="50" fill="#ddd"/></svg>'
        b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64}"

    @staticmethod
    def safe_url_for_log(url: str | None) -> str:
        """对日志中的 URL 进行脱敏，防止暴露敏感 Token。

        Args:
            url: 原始 URL。

        Returns:
            脱敏后的 URL 字符串。
        """
        if not url:
            return ""
        return re.sub(r"/bot[^/]+/", "/bot<redacted>/", url)

    @staticmethod
    def build_avatar_ref(avatar_key: str | None, avatar_url: str) -> str:
        """根据稳定特征生成不泄露用户 ID 的头像引用标识。

        Args:
            avatar_key: 缓存键。
            avatar_url: 头像 Data URI 或 URL。

        Returns:
            哈希短引用标识（如 avatar-xxxxxx）。
        """
        if avatar_key:
            digest = hashlib.sha256(avatar_key.encode("utf-8")).hexdigest()[:24]
            return f"avatar-{digest}"

        digest = hashlib.sha256(avatar_url.encode("utf-8")).hexdigest()[:24]
        return f"avatar-{digest}"

    @staticmethod
    def register_reusable_avatar(
        avatar_url: str | None,
        avatar_reuse_registry: dict[str, str] | None,
        avatar_reuse_aliases: dict[str, str] | None = None,
        avatar_key: str | None = None,
    ) -> str | None:
        """将 Data URI 头像注册为可复用资源，返回短引用标识。

        Args:
            avatar_url: 头像 Data URI 字符串。
            avatar_reuse_registry: 复用资源注册表。
            avatar_reuse_aliases: 别名索引表。
            avatar_key: 头像缓存键。

        Returns:
            短引用标识，若非可复用 Data URI 则返回 None。
        """
        if not avatar_url or avatar_reuse_registry is None:
            return None
        if not avatar_url.startswith("data:image/"):
            return None

        if avatar_reuse_aliases and avatar_url in avatar_reuse_aliases:
            return avatar_reuse_aliases[avatar_url]

        ref = AvatarService.build_avatar_ref(avatar_key, avatar_url)
        avatar_reuse_registry.setdefault(ref, avatar_url)
        if avatar_reuse_aliases is not None:
            avatar_reuse_aliases[avatar_url] = ref
        return ref

    @staticmethod
    def build_avatar_reuse_styles(avatar_reuse_registry: dict[str, str]) -> str:
        """为所有复用头像生成 CSS 样式规则块。

        Args:
            avatar_reuse_registry: 头像复用注册表。

        Returns:
            HTML `<style>` 标签字符串。
        """
        if not avatar_reuse_registry:
            return ""

        rules = [
            '<style id="avatar-reuse-styles">',
            ".user-capsule-avatar,img[data-avatar-ref]{background-color:#ddd;background-size:cover;background-position:center;background-repeat:no-repeat;}",
        ]
        for ref, data_uri in avatar_reuse_registry.items():
            escaped_ref = html.escape(ref, quote=True)
            escaped_uri = data_uri.replace("\\", "\\\\").replace('"', '\\"')
            rules.append(
                f'[data-avatar-ref="{escaped_ref}"]'
                f'{{background-image:url("{escaped_uri}");}}'
            )
        rules.append("</style>")
        return "\n".join(rules)

    @staticmethod
    def reuse_inline_avatar_img_sources(
        html_content: str,
        avatar_reuse_registry: dict[str, str],
        avatar_reuse_aliases: dict[str, str] | None = None,
    ) -> str:
        """将 HTML 中冗余的内联 Data URI 替换为短引用属性。

        Args:
            html_content: 原始 HTML 文本。
            avatar_reuse_registry: 注册表。
            avatar_reuse_aliases: 别名表。

        Returns:
            优化体积后的 HTML 文本。
        """
        if not html_content:
            return html_content

        img_src_pattern = re.compile(
            r'(<img\b[^>]*?\bsrc\s*=\s*)(["\'])(data:image/[^"\']+)(\2)([^>]*>)',
            re.IGNORECASE | re.DOTALL,
        )

        def replace(match: re.Match[str]) -> str:
            prefix, quote_char, data_uri, _, suffix = match.groups()
            if data_uri == TRANSPARENT_IMAGE_DATA_URI:
                return match.group(0)

            avatar_ref = (
                avatar_reuse_aliases.get(data_uri) if avatar_reuse_aliases else None
            )
            if not avatar_ref:
                return match.group(0)

            escaped_ref = html.escape(avatar_ref, quote=True)
            return (
                f"{prefix}{quote_char}{TRANSPARENT_IMAGE_DATA_URI}{quote_char}"
                f' data-avatar-ref="{escaped_ref}"{suffix}'
            )

        return img_src_pattern.sub(replace, html_content)

    @staticmethod
    def inject_avatar_reuse_styles(html_content: str, avatar_reuse_styles: str) -> str:
        """将生成的头像复用样式注入 HTML 的 `<head>` 区域。

        Args:
            html_content: 原始 HTML 文本。
            avatar_reuse_styles: 样式标签字符串。

        Returns:
            注入样式后的 HTML 文本。
        """
        if not html_content or not avatar_reuse_styles:
            return html_content

        head_close = re.search(r"</head\s*>", html_content, re.IGNORECASE)
        if head_close:
            return (
                html_content[: head_close.start()]
                + avatar_reuse_styles
                + "\n"
                + html_content[head_close.start() :]
            )
        return avatar_reuse_styles + "\n" + html_content

    @staticmethod
    def reuse_avatars_in_final_html(
        html_content: str,
        avatar_reuse_registry: dict[str, str] | None,
        avatar_reuse_aliases: dict[str, str] | None = None,
    ) -> str:
        """统一对 HTML 进行内联头像瘦身与样式注入。

        Args:
            html_content: 原始 HTML 文本。
            avatar_reuse_registry: 注册表。
            avatar_reuse_aliases: 别名表。

        Returns:
            最终瘦身后的 HTML 字符串。
        """
        if not html_content:
            return html_content

        registry = avatar_reuse_registry if avatar_reuse_registry is not None else {}
        aliases = avatar_reuse_aliases if avatar_reuse_aliases is not None else {}
        html_content = AvatarService.reuse_inline_avatar_img_sources(
            html_content, registry, aliases
        )
        return AvatarService.inject_avatar_reuse_styles(
            html_content, AvatarService.build_avatar_reuse_styles(registry)
        )

    async def close(self) -> None:
        """释放网络会话与本地磁盘缓存资源。"""
        if self._avatar_session:
            await self._avatar_session.close()
            self._avatar_session = None

        try:
            if self._avatar_cache:
                self._avatar_cache.close()
                logger.debug("头像缓存已关闭")
        except Exception as e:
            logger.warning(f"关闭头像缓存失败: {e}")
