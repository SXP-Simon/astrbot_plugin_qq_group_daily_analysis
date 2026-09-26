"""
报告生成接口 - 领域层
定义分析报告生成的抽象契约
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ...infrastructure.reporting.templates import HTMLTemplates
    from ..value_objects import AnalysisResultPayload


class IReportGenerator(ABC):
    """报告生成器接口 - 领域层契约。"""

    html_templates: HTMLTemplates | None = None

    @abstractmethod
    async def generate_image_report(
        self,
        analysis_result: AnalysisResultPayload,
        group_id: str,
        html_render_func: Callable[..., Awaitable[str | bytes | None]] | None = None,
        avatar_url_getter: Callable[[str, int | None], Awaitable[str | None]]
        | None = None,
        nickname_getter: Callable[[str], Awaitable[str | None]] | None = None,
        avatar_cache_namespace: str | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
        template_theme: str | None = None,
    ) -> tuple[str | None, str | None]:
        """生成图片报告。"""

    @abstractmethod
    async def generate_html_report(
        self,
        analysis_result: AnalysisResultPayload,
        group_id: str,
        avatar_url_getter: Callable[[str, int | None], Awaitable[str | None]]
        | None = None,
        nickname_getter: Callable[[str], Awaitable[str | None]] | None = None,
        avatar_cache_namespace: str | None = None,
        hide_user_names: bool = False,
        allow_alphanumeric_user_ids: bool = False,
        template_theme: str | None = None,
        custom_filename: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[str | None, str | None]:
        """生成 HTML 报告。"""

    @abstractmethod
    def generate_text_report(self, analysis_result: AnalysisResultPayload) -> str:
        """生成文本报告。"""

    @abstractmethod
    async def generate_markdown_report(
        self,
        analysis_result: AnalysisResultPayload,
        html_render_func: Callable[..., Awaitable[str | bytes | None]] | None = None,
        mention_style: str = "name",
    ) -> tuple[str, str]:
        """生成 Markdown 格式分析报告。

        Args:
            analysis_result: 分析结果载荷。
            html_render_func: 可选的 HTML 异步渲染函数。
            mention_style: 提及展示风格（'name' 为跨平台通用昵称文本，'qq' 为 QQ 官方提及）。

        Returns:
            tuple[str, str]: (主报告文本, 备用降级文本)。
        """

    @abstractmethod
    async def close(self) -> None:
        """释放资源。"""
