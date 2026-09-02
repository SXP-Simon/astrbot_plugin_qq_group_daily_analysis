"""HTML 冗余 preconnect 与 dns-prefetch 标签清理拦截器。"""

from __future__ import annotations

import re
from typing import Any

from ....utils.logger import logger
from .base import BaseResourceInterceptor

# 匹配 preconnect / dns-prefetch <link> 标签正则
PRECONNECT_PATTERN = re.compile(
    r"""<link\s+[^>]*?rel=["'](?:preconnect|dns-prefetch)["'][^>]*?>""",
    re.IGNORECASE,
)


class PreconnectInterceptor(BaseResourceInterceptor):
    """剔除 HTML 中的 preconnect 与 dns-prefetch 标签，避免 Playwright 发起无效的 CDN 网络握手。"""

    async def intercept(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """剥离 preconnect / dns-prefetch 标签。

        Args:
            content: HTML 字符串。
            context: 可选上下文参数。

        Returns:
            清理后的 HTML 字符串。
        """
        ctx = context or {}
        telemetry = ctx.get("telemetry")
        matches = list(PRECONNECT_PATTERN.finditer(content))
        if matches and telemetry is not None:
            telemetry["preconnect_tags_stripped"] = len(matches)

        cleaned = PRECONNECT_PATTERN.sub("", content)
        logger.debug("[Preconnect拦截器] 已清理冗余 preconnect / dns-prefetch 标签。")
        return cleaned
