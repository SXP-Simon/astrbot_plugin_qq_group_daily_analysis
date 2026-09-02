"""通用外部 CSS 样式表拦截器（<link rel="stylesheet">）。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from ....utils.logger import logger
from .base import BaseResourceInterceptor

# 匹配外部 CSS 样式表 <link> 标签正则
STYLESHEET_LINK_PATTERN = re.compile(
    r"""<link\s+[^>]*?rel=["']stylesheet["'][^>]*?href=["'](?P<url>(?:https?:)?//[^"']+)["'][^>]*?>|<link\s+[^>]*?href=["'](?P<url2>(?:https?:)?//[^"']+\.css(?:\?[^"']*)?)["'][^>]*?rel=["']stylesheet["'][^>]*?>""",
    re.IGNORECASE,
)

# 匹配 CSS 中引用的 url(...) 子资源正则
CSS_SUBRESOURCE_PATTERN = re.compile(
    r"""url\(["']?(?P<url>[^"')]+)["']?\)""",
    re.IGNORECASE,
)


class CssStylesheetInterceptor(BaseResourceInterceptor):
    """拦截通用外部 CSS 样式表，下载并递归内联其中的字体与子资源，转换为内联 <style>。"""

    async def _localize_stylesheet_content(
        self,
        base_url: str,
        css_text: str,
        timeout: float = 5.0,
        template: str | None = None,
        telemetry: dict[str, Any] | None = None,
    ) -> str:
        """解析并内联 CSS 中引用的所有相对或绝对子资源（字体、背景图等）。

        Args:
            base_url: CSS 文件的 URL（用于解析相对路径）。
            css_text: 原始 CSS 文本。
            timeout: 下载超时时间。
            template: 关联模板名称。
            telemetry: 可选遥测收集字典。

        Returns:
            完成子资源内联后的 CSS 文本。
        """
        urls_to_replace: set[tuple[str, str]] = set()
        for match in CSS_SUBRESOURCE_PATTERN.finditer(css_text):
            raw_url = match.group("url").strip()
            if raw_url.startswith("data:"):
                continue
            abs_url = urljoin(base_url, raw_url)
            urls_to_replace.add((raw_url, abs_url))

        result_css = css_text
        for raw_url, abs_url in urls_to_replace:
            had_cached = await self.cache_repo.has(abs_url, template=template)
            data, mime = await self.cache_repo.get_or_download(
                abs_url, timeout=timeout, template=template
            )
            if data:
                mime_type = mime or (
                    "font/woff2"
                    if ".woff2" in abs_url.lower()
                    else "application/octet-stream"
                )
                data_uri = self.to_base64_data_uri(data, mime_type)
                pattern = re.compile(
                    rf"""url\(["']?{re.escape(raw_url)}["']?\)""",
                    re.IGNORECASE,
                )
                result_css = pattern.sub(f"url('{data_uri}')", result_css)
                if telemetry is not None:
                    telemetry["inlined_bytes"] += len(data)
                    if had_cached:
                        telemetry["cache_hits"] += 1
                    else:
                        telemetry["downloaded"] += 1
                    telemetry["items"].append(
                        {
                            "url": abs_url,
                            "type": "subresource",
                            "mime": mime_type,
                            "size": len(data),
                            "cached": had_cached,
                            "source": "css_subresource",
                        }
                    )
            else:
                if telemetry is not None:
                    telemetry["failed"] += 1
                logger.warning(f"[CSS样式表拦截器] 子资源下载或内联失败: {abs_url}")

        return result_css

    async def intercept(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """拦截 HTML 中的外部样式表 <link> 标签并转换为内联 <style>。

        Args:
            content: HTML 字符串。
            context: 可选上下文参数。

        Returns:
            完成内联后的 HTML 字符串。
        """
        ctx = context or {}
        timeout = float(ctx.get("timeout", 5.0))
        template = ctx.get("template")
        telemetry = ctx.get("telemetry")
        result = content

        matches = list(STYLESHEET_LINK_PATTERN.finditer(result))
        for match in matches:
            full_tag = match.group(0)
            css_url = match.group("url") or match.group("url2")
            if not css_url:
                continue
            if css_url.startswith("//"):
                css_url = f"https:{css_url}"

            # 跳过已由 GoogleFontsInterceptor 处理的链接
            if (
                "fonts.googleapis.com" in css_url
                or "fonts.loli.net" in css_url
                or "fonts.font.im" in css_url
            ):
                continue

            had_cached = await self.cache_repo.has(css_url, template=template)
            css_data, _ = await self.cache_repo.get_or_download(
                css_url, timeout=timeout, template=template
            )
            if css_data:
                if telemetry is not None:
                    if had_cached:
                        telemetry["cache_hits"] += 1
                    else:
                        telemetry["downloaded"] += 1
                    telemetry["items"].append(
                        {
                            "url": css_url,
                            "type": "stylesheet",
                            "mime": "text/css",
                            "size": len(css_data),
                            "cached": had_cached,
                            "source": "external_css",
                        }
                    )

                css_text = css_data.decode("utf-8", errors="replace")
                inlined_css = await self._localize_stylesheet_content(
                    css_url,
                    css_text,
                    timeout=timeout,
                    template=template,
                    telemetry=telemetry,
                )
                replacement = (
                    f"<style data-localized-stylesheet='true'>\n{inlined_css}\n</style>"
                )
                result = result.replace(full_tag, replacement)
                logger.debug(f"[CSS样式表拦截器] 成功内联外部样式表: {css_url}")
            else:
                if telemetry is not None:
                    telemetry["failed"] += 1
                logger.warning(f"[CSS样式表拦截器] 无法下载外部样式表: {css_url}")

        return result
