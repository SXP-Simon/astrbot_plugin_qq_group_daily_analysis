"""
分析服务接口 - 领域层
定义语义分析的抽象契约
"""

from abc import ABC, abstractmethod

from ..models.data_models import (
    GoldenQuote,
    QualityReview,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)


class IAnalysisProvider(ABC):
    """
    LLM 分析提供商接口
    """

    @abstractmethod
    async def analyze_topics(
        self,
        messages: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
    ) -> tuple[list[SummaryTopic], TokenUsage]:
        """分析话题"""
        pass

    @abstractmethod
    async def analyze_user_titles(
        self,
        messages: list[dict],
        user_activity: dict,
        umo: str | None = None,
        top_users: list[dict] | None = None,
        session_id: str | None = None,
    ) -> tuple[list[UserTitle], TokenUsage]:
        """分析用户称号"""
        pass

    @abstractmethod
    async def analyze_golden_quotes(
        self,
        messages: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
    ) -> tuple[list[GoldenQuote], TokenUsage]:
        """分析金句"""
        pass

    @abstractmethod
    async def analyze_all_concurrent(
        self,
        messages: list[dict],
        user_activity: dict,
        umo: str | None = None,
        top_users: list[dict] | None = None,
        topic_enabled: bool = True,
        user_title_enabled: bool = True,
        golden_quote_enabled: bool = True,
        chat_quality_enabled: bool = False,
    ) -> tuple[
        list[SummaryTopic],
        list[UserTitle],
        list[GoldenQuote],
        TokenUsage,
        QualityReview | None,
    ]:
        """并发分析所有内容"""
        pass

    @abstractmethod
    async def analyze_incremental_concurrent(
        self,
        messages: list[dict],
        umo: str | None = None,
        topics_per_batch: int = 3,
        quotes_per_batch: int = 3,
        topic_enabled: bool = True,
        golden_quote_enabled: bool = True,
        chat_quality_enabled: bool = False,
    ) -> tuple[list[SummaryTopic], list[GoldenQuote], TokenUsage, QualityReview | None]:
        """增量模式并发分析"""
        pass

    @abstractmethod
    async def summarize_quality_reviews(
        self,
        batch_reviews: list[dict],
        umo: str | None = None,
        session_id: str | None = None,
    ) -> tuple[QualityReview | None, TokenUsage]:
        """汇总多个聊天质量报告（增量模式使用）"""
        pass
