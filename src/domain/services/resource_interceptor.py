"""资源拦截与 HTML 本地化领域接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IResourceInterceptor(ABC):
    """遵循开闭原则 (OCP) 的资源拦截器抽象基类接口。"""

    @abstractmethod
    async def intercept(
        self, content: str, context: dict[str, Any] | None = None
    ) -> str:
        """处理内容（HTML 或 CSS）并将外部资源链接转换为本地或内联资源。

        Args:
            content: 待转换的 HTML 或 CSS 字符串。
            context: 可选的上下文参数（如超时设置、主题名、本地路径等）。

        Returns:
            完成外部资源本地化/内联化后的内容。
        """
        pass


class IHTMLResourceLocalizer(ABC):
    """用于协调 HTML 模板资源本地化拦截流水线的领域服务接口。"""

    @abstractmethod
    async def localize_html(
        self, html_content: str, context: dict[str, Any] | None = None
    ) -> str:
        """执行拦截器流水线，将 HTML 中的所有外部资源替换为本地 Base64 内联数据。

        Args:
            html_content: 渲染生成的原始 HTML 字符串。
            context: 可选的上下文参数。

        Returns:
            完全自包含、0 外网依赖的 HTML 字符串。
        """
        pass
