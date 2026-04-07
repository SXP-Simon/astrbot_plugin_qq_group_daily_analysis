"""
报告生成接口 - 领域层
定义分析报告生成的抽象契约
"""

from abc import ABC, abstractmethod
from typing import Any


class IReportGenerator(ABC):
    """
    报告生成器接口
    """

    @abstractmethod
    async def generate_image_report(
        self,
        analysis_result: dict,
        group_id: str,
        html_render_func: Any,
        avatar_url_getter: Any = None,
        nickname_getter: Any = None,
    ) -> tuple[str | None, str | None]:
        """生成图片报告"""
        pass

    @abstractmethod
    async def generate_html_report(
        self,
        analysis_result: dict,
        group_id: str,
        avatar_url_getter: Any = None,
        nickname_getter: Any = None,
    ) -> tuple[str | None, str | None]:
        """生成 HTML 报告"""
        pass

    @abstractmethod
    def generate_text_report(self, analysis_result: dict) -> str:
        """生成文本报告"""
        pass

    @abstractmethod
    async def close(self):
        """释放资源"""
        pass
