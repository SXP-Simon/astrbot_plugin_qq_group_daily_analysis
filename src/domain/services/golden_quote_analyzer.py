"""
金句分析领域服务

该模块提供平台无关的金句分析服务接口。
实际分析逻辑委托给 infrastructure 层的具体实现。

架构说明:
- 本文件定义领域服务接口和数据转换逻辑
- 具体的 LLM 调用和消息处理在 src/analysis/analyzers/golden_quote_analyzer.py 中实现
- 采用渐进式迁移策略，保持与现有代码的兼容性
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

from ..value_objects.golden_quote import GoldenQuote
from ..value_objects.unified_message import UnifiedMessage

if TYPE_CHECKING:
    from ..value_objects.statistics import TokenUsage


class LegacyGoldenQuote(Protocol):
    content: str
    sender: str
    reason: str
    user_id: str | None


class LegacyGoldenQuoteAnalyzer(Protocol):
    async def analyze_golden_quotes(
        self,
        messages: list[dict[str, object]],
        unified_msg_origin: str | None,
    ) -> tuple[list[LegacyGoldenQuote], "TokenUsage"]: ...


class IGoldenQuoteAnalyzer(ABC):
    """
    金句分析服务接口

    定义平台无关的金句分析契约。
    所有平台的金句分析都应该实现此接口。
    """

    @abstractmethod
    async def analyze(
        self,
        messages: list[UnifiedMessage],
        unified_msg_origin: str | None = None,
    ) -> tuple[list[GoldenQuote], "TokenUsage"]:
        """
        分析消息中的金句

        参数:
            messages: 统一格式的消息列表
            unified_msg_origin: 消息来源标识，用于选择 LLM 提供商

        返回:
            (金句列表, Token 使用统计)
        """
        pass


class GoldenQuoteAnalyzerAdapter(IGoldenQuoteAnalyzer):
    """
    金句分析服务适配器

    将现有的 GoldenQuoteAnalyzer 实现适配为领域服务接口。
    负责 UnifiedMessage 与原始消息格式之间的转换。
    """

    def __init__(self, legacy_analyzer: LegacyGoldenQuoteAnalyzer):
        """
        初始化适配器

        参数:
            legacy_analyzer: 现有的 GoldenQuoteAnalyzer 实例
        """
        self._analyzer = legacy_analyzer

    async def analyze(
        self,
        messages: list[UnifiedMessage],
        unified_msg_origin: str | None = None,
    ) -> tuple[list[GoldenQuote], "TokenUsage"]:
        """
        分析消息中的金句

        将 UnifiedMessage 转换为原始格式，调用现有分析器，
        然后将结果转换为领域值对象。

        参数:
            messages: 统一格式的消息列表
            unified_msg_origin: 消息来源标识

        返回:
            (金句列表, Token 使用统计)
        """
        # 将 UnifiedMessage 转换为原始消息格式
        raw_messages = [self._to_raw_message(msg) for msg in messages]

        # 调用现有分析器
        legacy_quotes, token_usage = await self._analyzer.analyze_golden_quotes(
            raw_messages, unified_msg_origin
        )

        # 将结果转换为领域值对象
        quotes = [
            GoldenQuote(
                content=q.content,
                sender=q.sender,
                user_id=str(q.user_id) if q.user_id else "",
                reason=q.reason,
            )
            for q in legacy_quotes
        ]

        return quotes, token_usage

    def _to_raw_message(self, msg: UnifiedMessage) -> dict[str, object]:
        """
        将 UnifiedMessage 转换为原始消息格式

        参数:
            msg: 统一消息对象

        返回:
            原始消息字典
        """
        # 构建消息内容列表
        message_content = []
        if msg.text_content:
            message_content.append({"type": "text", "data": {"text": msg.text_content}})

        return {
            "message_id": msg.message_id,
            "time": msg.timestamp,
            "sender": {
                "user_id": msg.sender_id,
                "nickname": msg.sender_name,
            },
            "message": message_content,
        }
