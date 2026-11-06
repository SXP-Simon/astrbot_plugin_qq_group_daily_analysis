"""验证类型收紧后并发模块的开关、结果归属与取消行为。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.value_objects import SummaryTopic, GoldenQuote, TokenUsage
from src.infrastructure.analysis.llm_analyzer import LLMAnalyzer


def make_analyzer():
    analyzer = object.__new__(LLMAnalyzer)
    analyzer.topic_analyzer = SimpleNamespace(analyze_topics=AsyncMock(), incremental_max_count=None)
    analyzer.user_title_analyzer = SimpleNamespace(analyze_user_titles=AsyncMock())
    analyzer.golden_quote_analyzer = SimpleNamespace(analyze_golden_quotes=AsyncMock(), incremental_max_count=None)
    analyzer.chat_quality_analyzer = SimpleNamespace(analyze_quality=AsyncMock())
    return analyzer


@pytest.mark.asyncio
async def test_disabled_modules_do_not_run_and_keep_result_positions():
    analyzer = make_analyzer()
    topic = SummaryTopic(topic="周末出游", contributors=["群友"], detail="一起去公园")
    analyzer.topic_analyzer.analyze_topics.return_value = ([topic], TokenUsage(10, 4, 14))
    result = await analyzer.analyze_all_concurrent([], {}, user_title_enabled=False, golden_quote_enabled=False, chat_quality_enabled=False)
    assert result == ([topic], [], [], TokenUsage(10, 4, 14), None)
    analyzer.user_title_analyzer.analyze_user_titles.assert_not_called()
    analyzer.golden_quote_analyzer.analyze_golden_quotes.assert_not_called()
    analyzer.chat_quality_analyzer.analyze_quality.assert_not_called()


@pytest.mark.asyncio
async def test_one_failed_module_keeps_successful_quote_and_usage():
    analyzer = make_analyzer()
    quote = GoldenQuote(content="明天见", sender="群友", reason="出游约定")
    analyzer.topic_analyzer.analyze_topics.side_effect = RuntimeError("模型请求失败")
    analyzer.golden_quote_analyzer.analyze_golden_quotes.return_value = ([quote], TokenUsage(6, 2, 8))
    result = await analyzer.analyze_all_concurrent([], {}, user_title_enabled=False, chat_quality_enabled=False)
    assert result == ([], [], [quote], TokenUsage(6, 2, 8), None)


@pytest.mark.asyncio
@pytest.mark.parametrize("incremental", [False, True])
async def test_cancel_propagates_to_all_running_modules_and_resets_limits(incremental):
    analyzer = make_analyzer()
    started = asyncio.Event()
    running = set()
    cancelled = set()

    async def wait_for_cancel(name):
        running.add(name)
        if running == {"topic", "quote"}:
            started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.add(name)
            raise

    async def topic(*args):
        return await wait_for_cancel("topic")

    async def quote(*args):
        return await wait_for_cancel("quote")

    analyzer.topic_analyzer.analyze_topics.side_effect = topic
    analyzer.golden_quote_analyzer.analyze_golden_quotes.side_effect = quote
    operation = (
        analyzer.analyze_incremental_concurrent([], chat_quality_enabled=False)
        if incremental else
        analyzer.analyze_all_concurrent([], {}, user_title_enabled=False, chat_quality_enabled=False)
    )
    task = asyncio.create_task(operation)
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled == {"topic", "quote"}
        assert analyzer.topic_analyzer.incremental_max_count is None
        assert analyzer.golden_quote_analyzer.incremental_max_count is None
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
