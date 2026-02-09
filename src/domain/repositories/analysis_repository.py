"""
分析服务接口 - 领域层
定义语义分析的抽象契约
"""

from abc import ABC, abstractmethod

from ..models.data_models import GoldenQuote, SummaryTopic, TokenUsage, UserTitle


class IAnalysisProvider(ABC):
    """
    LLM 分析提供商接口
    """

    @abstractmethod
    async def analyze_topics(
        self, messages: list[dict], umo: str = None, session_id: str = None
    ) -> tuple[list[SummaryTopic], TokenUsage]:
        """分析话题"""
        pass

    @abstractmethod
    async def analyze_user_titles(
        self,
        messages: list[dict],
        user_activity: dict,
        umo: str = None,
        top_users: list[dict] = None,
        session_id: str = None,
    ) -> tuple[list[UserTitle], TokenUsage]:
        """分析用户称号"""
        pass

    @abstractmethod
    async def analyze_golden_quotes(
        self, messages: list[dict], umo: str = None, session_id: str = None
    ) -> tuple[list[GoldenQuote], TokenUsage]:
        """分析金句"""
        pass

    @abstractmethod
    async def analyze_all_concurrent(
        self,
        messages: list[dict],
        user_activity: dict,
        umo: str = None,
        top_users: list[dict] = None,
    ) -> tuple[list[SummaryTopic], list[UserTitle], list[GoldenQuote], TokenUsage]:
        """并发分析所有内容"""
        pass
