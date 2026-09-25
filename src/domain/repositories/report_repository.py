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


class IReportGenerator(ABC):
    """报告生成器接口 - 领域层契约。"""

    html_templates: HTMLTemplates | None = None

    @abstractmethod
    async def generate_image_report(
        self,
        analysis_result: dict[str, object],
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
        analysis_result: dict[str, object],
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
    def generate_text_report(self, analysis_result: dict[str, object]) -> str:
        """生成文本报告。"""

    @abstractmethod
    async def close(self) -> None:
        """释放资源。"""
