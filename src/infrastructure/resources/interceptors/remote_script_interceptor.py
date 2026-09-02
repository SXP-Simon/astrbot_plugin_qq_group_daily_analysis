"""远程外部脚本拦截器（<script src="http...">）。"""

from __future__ import annotations

import re
from typing import Any

from ....utils.logger import logger
from .base import BaseResourceInterceptor

# 匹配外部 <script src="http..."> 正则
SCRIPT_SRC_PATTERN = re.compile(
    r"""<script\s+[^>]*?src=["'](?P<url>(?:https?:)?//[^"']+)["'][^>]*?>\s*</script>""",
    re.IGNORECASE,
)


class RemoteScriptInterceptor(BaseResourceInterceptor):
    """拦截 HTML 中的远程脚本链接并转换为内联 <script> 标签。"""

    async def intercept(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """查找并内联远程脚本。

        Args:
            content: HTML 字符串。
            context: 可选上下文参数。

        Returns:
            完成脚本内联后的 HTML 字符串。
        """
        timeout = float((context or {}).get("timeout", 5.0))
        result = content

        matches = list(SCRIPT_SRC_PATTERN.finditer(result))
        for match in matches:
            full_tag = match.group(0)
            script_url = match.group("url")
            if script_url.startswith("//"):
                script_url = f"https:{script_url}"

            data, _ = await self.cache_repo.get_or_download(script_url, timeout=timeout)
            if data:
                script_text = data.decode("utf-8", errors="replace")
                replacement = f"<script data-localized-script='true'>\n/* 内联自 {script_url} */\n{script_text}\n</script>"
                result = result.replace(full_tag, replacement)
                logger.debug(f"[脚本拦截器] 成功内联远程脚本: {script_url}")
            else:
                logger.warning(f"[脚本拦截器] 下载或内联远程脚本失败: {script_url}")

        return result
