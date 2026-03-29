"""
报告生成接口 - 领域层
定义分析报告生成的抽象契约
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Protocol

ReportData = Mapping[str, object]


class HtmlRenderFunc(Protocol):
    async def __call__(
        self,
        html_content: str,
        payload: Mapping[str, object],
        return_url: bool,
        image_options: Mapping[str, object],
    ) -> bytes | str | None: ...


class AvatarUrlGetter(Protocol):
    async def __call__(self, user_id: str) -> str | None: ...


class NicknameGetter(Protocol):
    async def __call__(self, user_id: str) -> str | None: ...


class IReportGenerator(ABC):
    """
    报告生成器接口
    """

    @abstractmethod
    async def generate_image_report(
        self,
        analysis_result: ReportData,
        group_id: str,
        html_render_func: HtmlRenderFunc,
        avatar_url_getter: AvatarUrlGetter | None = None,
        nickname_getter: NicknameGetter | None = None,
    ) -> tuple[str | None, str | None]:
        """生成图片报告"""
        pass

    @abstractmethod
    async def generate_pdf_report(
        self,
        analysis_result: ReportData,
        group_id: str,
        avatar_getter: AvatarUrlGetter | None = None,
        nickname_getter: NicknameGetter | None = None,
    ) -> str | None:
        """生成 PDF 报告"""
        pass

    @abstractmethod
    def generate_text_report(self, analysis_result: ReportData) -> str:
        """生成文本报告"""
        pass
