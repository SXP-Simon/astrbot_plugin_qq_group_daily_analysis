"""Google Fonts 与字体镜像站外部样式表拦截器。"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from ....utils.logger import logger
from .base import BaseResourceInterceptor

# 匹配 HTML 中 Google Fonts / 字体镜像站的 <link> 标签正则
GOOGLE_FONTS_LINK_PATTERN = re.compile(
    r"""<link\s+[^>]*?href=["'](?P<url>(?:https?:)?//(?:fonts\.googleapis\.com|fonts\.loli\.net|fonts\.font\.im)[^"']+)["'][^>]*?>""",
    re.IGNORECASE,
)

# 匹配 CSS 或 <style> 中 Google Fonts @import 语句正则
GOOGLE_FONTS_IMPORT_PATTERN = re.compile(
    r"""@import\s+(?:url\()?["']?(?P<url>(?:https?:)?//(?:fonts\.googleapis\.com|fonts\.loli\.net|fonts\.font\.im)[^"')]+)["']?\)?\s*;?""",
    re.IGNORECASE,
)

# 匹配 CSS @font-face 内部引用的 url(...) 字体文件链接正则
CSS_URL_PATTERN = re.compile(
    r"""url\(["']?(?P<url>(?:https?:)?//[^\'")]+|\.\./[^\'")]+|/[^\'")]+)["']?\)""",
    re.IGNORECASE,
)


class GoogleFontsInterceptor(BaseResourceInterceptor):
    """拦截 Google Fonts 样式表，按需极速复用缓存，未缓存资源后台静默预取不阻塞 T2I 渲染。"""

    async def _download_and_cache_font(
        self, font_url: str, template: str | None, sem: asyncio.Semaphore
    ) -> None:
        async with sem:
            try:
                await self.cache_repo.get_or_download(
                    font_url, timeout=12.0, template=template
                )
            except Exception as e:
                logger.debug(f"后台静默缓存字体失败 {font_url}: {e}")

    def _start_background_cache(self, urls: set[str], template: str | None) -> None:
        if not urls:
            return

        async def _run():
            sem = asyncio.Semaphore(8)
            tasks = [self._download_and_cache_font(u, template, sem) for u in urls]
            await asyncio.gather(*tasks, return_exceptions=True)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_run())
        except RuntimeError:
            pass

    async def _localize_css_content(
        self,
        css_text: str,
        timeout: float = 5.0,
        template: str | None = None,
        is_prefetch: bool = False,
        telemetry: dict[str, Any] | None = None,
    ) -> str:
        """下载 CSS 中引用的所有字体切片链接并替换为 Base64 Data URI。

        Args:
            css_text: 原始 CSS 文本。
            timeout: 单个字体切片的下载超时时间。
            template: 关联模板主题。
            is_prefetch: 是否处于显式预热模式（全量并发下载）。
            telemetry: 可选遥测收集字典。

        Returns:
            完成字体内联后的 CSS 文本。
        """
        urls_to_replace: set[str] = set()
        for match in CSS_URL_PATTERN.finditer(css_text):
            url = match.group("url").strip()
            if (
                url.startswith("http://")
                or url.startswith("https://")
                or url.startswith("//")
            ):
                urls_to_replace.add(url)

        if not urls_to_replace:
            return css_text

        result_css = css_text
        uncached_urls: set[str] = set()

        if is_prefetch:
            # 预热模式：并发全量下载并替换
            sem = asyncio.Semaphore(8)

            async def _fetch_one(
                font_url: str,
            ) -> tuple[str, bytes | None, str | None, bool]:
                async with sem:
                    had = await self.cache_repo.has(font_url, template=template)
                    data, mime = await self.cache_repo.get_or_download(
                        font_url, timeout=timeout, template=template
                    )
                    return font_url, data, mime, had

            results = await asyncio.gather(
                *[_fetch_one(u) for u in urls_to_replace],
                return_exceptions=False,
            )
            for font_url, data, mime, had_cached in results:
                if data:
                    mime_type = mime or "font/woff2"
                    data_uri = self.to_base64_data_uri(data, mime_type)
                    pattern = re.compile(
                        rf"""url\(["']?{re.escape(font_url)}["']?\)""",
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
                                "url": font_url,
                                "type": "font_chunk",
                                "mime": mime_type,
                                "size": len(data),
                                "cached": had_cached,
                                "source": "google_fonts",
                            }
                        )
                else:
                    if telemetry is not None:
                        telemetry["failed"] += 1
                    logger.warning(
                        f"[GoogleFonts拦截器] 字体切片下载或本地化失败: {font_url}"
                    )
        else:
            # JIT 实时渲染模式：直接命中本地缓存，未缓存的不阻塞 T2I 渲染并在后台静默下载
            for font_url in urls_to_replace:
                had_cached = await self.cache_repo.has(font_url, template=template)
                if had_cached:
                    data = await self.cache_repo.get(font_url, template=template)
                    if data:
                        mime_type = "font/woff2"
                        data_uri = self.to_base64_data_uri(data, mime_type)
                        pattern = re.compile(
                            rf"""url\(["']?{re.escape(font_url)}["']?\)""",
                            re.IGNORECASE,
                        )
                        result_css = pattern.sub(f"url('{data_uri}')", result_css)
                        if telemetry is not None:
                            telemetry["inlined_bytes"] += len(data)
                            telemetry["cache_hits"] += 1
                            telemetry["items"].append(
                                {
                                    "url": font_url,
                                    "type": "font_chunk",
                                    "mime": mime_type,
                                    "size": len(data),
                                    "cached": True,
                                    "source": "google_fonts",
                                }
                            )
                        continue
                uncached_urls.add(font_url)

            if uncached_urls:
                self._start_background_cache(uncached_urls, template)

        return result_css

    async def intercept(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """拦截 HTML/CSS 中的 Google Fonts 链接与 @import 语句。

        Args:
            content: HTML 或 CSS 字符串。
            context: 可选上下文（包含超时时间、模板名、遥测等）。

        Returns:
            完成内联后的内容。
        """
        ctx = context or {}
        timeout = float(ctx.get("timeout", 5.0))
        template = ctx.get("template")
        telemetry = ctx.get("telemetry")
        is_prefetch = bool(ctx.get("is_prefetch", False))
        result = content

        # 1. 处理 HTML 中的 <link ... href="...fonts.googleapis.com...">
        link_matches = list(GOOGLE_FONTS_LINK_PATTERN.finditer(result))
        for match in link_matches:
            full_tag = match.group(0)
            css_url = match.group("url")
            if css_url.startswith("//"):
                css_url = f"https:{css_url}"

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
                            "source": "google_fonts_css",
                        }
                    )

                css_text = css_data.decode("utf-8", errors="replace")
                inlined_css = await self._localize_css_content(
                    css_text,
                    timeout=timeout,
                    template=template,
                    is_prefetch=is_prefetch,
                    telemetry=telemetry,
                )
                replacement = f"<style data-localized-fonts='google-fonts'>\n{inlined_css}\n</style>"
                result = result.replace(full_tag, replacement)
                logger.debug(
                    f"[GoogleFonts拦截器] 成功内联 Google Fonts 样式表: {css_url}"
                )
            else:
                if telemetry is not None:
                    telemetry["failed"] += 1
                logger.warning(
                    f"[GoogleFonts拦截器] 获取 Google Fonts 样式表失败: {css_url}"
                )

        # 2. 处理 CSS 中的 @import url("...fonts.googleapis.com...")
        import_matches = list(GOOGLE_FONTS_IMPORT_PATTERN.finditer(result))
        for match in import_matches:
            full_stmt = match.group(0)
            css_url = match.group("url")
            if css_url.startswith("//"):
                css_url = f"https:{css_url}"

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
                            "type": "import_stylesheet",
                            "mime": "text/css",
                            "size": len(css_data),
                            "cached": had_cached,
                            "source": "google_fonts_import",
                        }
                    )

                css_text = css_data.decode("utf-8", errors="replace")
                inlined_css = await self._localize_css_content(
                    css_text,
                    timeout=timeout,
                    template=template,
                    is_prefetch=is_prefetch,
                    telemetry=telemetry,
                )
                result = result.replace(full_stmt, inlined_css)
                logger.debug(
                    f"[GoogleFonts拦截器] 成功内联 @import Google Fonts: {css_url}"
                )

        return result
