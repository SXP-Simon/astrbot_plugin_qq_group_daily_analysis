"""直接在 HTML <style> 标签或 CSS 中声明的 @font-face 字体链接拦截器。"""

from __future__ import annotations

import re
from typing import Any

from ....utils.logger import logger
from .base import BaseResourceInterceptor

# 匹配 CSS 中引用的字体二进制文件链接正则
DIRECT_FONT_URL_PATTERN = re.compile(
    r"""url\(["']?(?P<url>(?:https?:)?//[^\'")\s]+\.(?:woff2|woff|ttf|otf|eot)(?:\?[^\'")\s]*)?)["']?\)""",
    re.IGNORECASE,
)


class FontFaceInterceptor(BaseResourceInterceptor):
    """拦截 CSS 中直接引用的远程字体文件链接，并转换为 Base64 Data URI。"""

    async def intercept(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """查找并替换内容中所有的远程字体文件链接为 Base64 Data URI。

        Args:
            content: HTML 或 CSS 字符串。
            context: 可选上下文参数。

        Returns:
            完成字体本地化后的字符串。
        """
        ctx = context or {}
        timeout = float(ctx.get("timeout", 5.0))
        template = ctx.get("template")
        telemetry = ctx.get("telemetry")
        result = content

        urls_to_replace: set[str] = set()
        for match in DIRECT_FONT_URL_PATTERN.finditer(result):
            font_url = match.group("url").strip()
            if not font_url.startswith("data:"):
                urls_to_replace.add(font_url)

        if not urls_to_replace:
            return result

        for font_url in urls_to_replace:
            full_url = font_url
            if full_url.startswith("//"):
                full_url = f"https:{full_url}"

            had_cached = await self.cache_repo.has(full_url, template=template)
            data, mime = await self.cache_repo.get_or_download(
                full_url, timeout=timeout, template=template
            )
            if data:
                lower_url = full_url.lower()
                if ".woff2" in lower_url:
                    mime_type = "font/woff2"
                elif ".woff" in lower_url:
                    mime_type = "font/woff"
                elif ".ttf" in lower_url:
                    mime_type = "font/ttf"
                elif ".otf" in lower_url:
                    mime_type = "font/otf"
                elif ".eot" in lower_url:
                    mime_type = "application/vnd.ms-fontobject"
                else:
                    mime_type = mime or "font/woff2"

                data_uri = self.to_base64_data_uri(data, mime_type)
                pattern = re.compile(
                    rf"""url\(["']?{re.escape(font_url)}["']?\)""",
                    re.IGNORECASE,
                )
                result = pattern.sub(f"url('{data_uri}')", result)
                if telemetry is not None:
                    telemetry["inlined_bytes"] += len(data)
                    if had_cached:
                        telemetry["cache_hits"] += 1
                    else:
                        telemetry["downloaded"] += 1
                    telemetry["items"].append(
                        {
                            "url": full_url,
                            "type": "font_face",
                            "mime": mime_type,
                            "size": len(data),
                            "cached": had_cached,
                            "source": "font_face",
                        }
                    )
                logger.debug(f"[字体拦截器] 成功本地化字体: {font_url}")
            else:
                if telemetry is not None:
                    telemetry["failed"] += 1
                logger.warning(f"[字体拦截器] 下载字体文件失败: {font_url}")

        return result
