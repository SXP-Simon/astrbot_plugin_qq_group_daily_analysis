"""验证词云计数口径、增量边界、完整快照和独立采集副作用。"""

from __future__ import annotations

import time
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.analysis_application_service import (
    AnalysisApplicationService,
)
from src.application.services.analysis_serializer import AnalysisResultSerializer
from src.domain.entities.incremental_state import IncrementalBatch
from src.domain.services.incremental_merge_service import IncrementalMergeService
from src.domain.services.wordcloud_statistics_service import WordCloudStatisticsService
from src.domain.value_objects import (
    GroupStatistics,
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from src.domain.value_objects.wordcloud import (
    WordCloudData,
    WordCloudOptions,
    WordFrequency,
)
from src.infrastructure.analysis.jieba_tokenizer import JiebaWordTokenizer
from src.shared.trace_context import TraceContext


def message(
    message_id: str, text: str, timestamp: int = 1, sender_id: str = "user"
) -> UnifiedMessage:
    return UnifiedMessage(
        message_id=message_id,
        sender_id=sender_id,
        sender_name=sender_id,
        group_id="group",
        text_content=text,
        contents=(MessageContent(type=MessageContentType.TEXT, text=text),),
        timestamp=timestamp,
        platform="onebot",
    )


def test_message_frequency_and_occurrence_frequency_differ_without_page_duplicates():
    service = WordCloudStatisticsService(JiebaWordTokenizer())
    first = message("one", "星空 星空 海风")
    data = service.collect(
        [first, first, message("two", "星空 海风")], WordCloudOptions()
    )
    entries = {entry.text: entry for entry in data.frequencies}
    assert data.message_count == 2
    assert entries["星空"] == WordFrequency("星空", 3, 2)
    assert entries["海风"] == WordFrequency("海风", 2, 2)


def test_only_text_is_counted_and_technical_noise_is_removed():
    msg = replace(
        message("one", "星空 [CQ:at,qq=12345] https://example.com/noise [图片] 12345"),
        contents=(
            MessageContent(
                type=MessageContentType.TEXT,
                text="星空 [CQ:at,qq=12345] https://example.com/noise [图片] 12345",
            ),
            MessageContent(type=MessageContentType.AT, text="噪音昵称"),
            MessageContent(type=MessageContentType.IMAGE, text="噪音图片"),
        ),
    )
    data = WordCloudStatisticsService(JiebaWordTokenizer()).collect(
        [msg], WordCloudOptions()
    )
    assert data.frequencies == (WordFrequency("星空", 1, 1),)


def test_custom_dictionary_is_isolated_and_keep_words_override_stopwords():
    service = WordCloudStatisticsService(JiebaWordTokenizer())
    options = WordCloudOptions(
        keep_words=("高性能萝卜子", "这个"), stopwords=("这个",), min_frequency=1
    )
    data = service.collect([message("one", "高性能萝卜子 这个")], options)
    assert {entry.text for entry in data.top_words(options)} == {"高性能萝卜子", "这个"}
    next_group = service.collect(
        [message("one", "高性能萝卜子 这个")], WordCloudOptions()
    )
    assert "高性能萝卜子" not in {entry.text for entry in next_group.frequencies}
    assert "这个" not in {entry.text for entry in next_group.frequencies}


def test_merge_keeps_all_words_until_after_top_n_and_minimum_frequency():
    first = WordCloudData(
        (
            WordFrequency("第一", 4, 4),
            WordFrequency("合计", 3, 3),
            WordFrequency("少词", 1, 1),
        ),
        4,
        "group",
    )
    second = WordCloudData(
        (
            WordFrequency("第二", 4, 4),
            WordFrequency("合计", 3, 3),
            WordFrequency("少词", 1, 1),
        ),
        4,
        "group",
    )
    batch1 = IncrementalBatch(batch_id="one", wordcloud=first)
    batch2 = IncrementalBatch(batch_id="two", wordcloud=second)
    merge = IncrementalMergeService()
    state = merge.merge_batches(
        [batch1, batch1, batch2, IncrementalBatch(batch_id="old")], 1, 2
    )
    assert state.wordcloud is not None
    assert state.wordcloud.message_count == 8
    assert state.wordcloud.top_words(WordCloudOptions(max_words=1))[0].text == "合计"
    assert (
        next(
            entry for entry in state.wordcloud.frequencies if entry.text == "少词"
        ).message_count
        == 2
    )
    assert merge.build_analysis_result(state)["wordcloud"] == state.wordcloud


def test_snapshot_round_trip_and_old_checkpoint_compatibility():
    data = WordCloudData(
        (WordFrequency("海风", 6, 3),), 4, "group", "bot", "2026-10-17", 1, 3
    )
    snapshot = AnalysisResultSerializer.serialize({"wordcloud": data})
    assert AnalysisResultSerializer.deserialize(snapshot)["wordcloud"] == data
    batch = IncrementalBatch(wordcloud=data)
    assert IncrementalBatch.from_dict(batch.to_dict()).wordcloud == data
    assert IncrementalBatch.from_dict({}).wordcloud is None
    assert "wordcloud" not in AnalysisResultSerializer.deserialize({})


@pytest.mark.parametrize(
    "invalid",
    [
        {"word_spacing": -1},
        {"word_spacing": 41},
        {"max_words": True},
        {"min_font_size": 90, "max_font_size": 34},
        {"width": 799},
        {"font": "https://example.com/font.woff2"},
        {"template": "../ATRI"},
        {"palette": ["red"]},
        {"stopwords": "错误类型"},
        {"rotation": "unknown"},
    ],
)
def test_invalid_options_are_rejected(invalid: dict[str, object]):
    with pytest.raises(ValueError):
        WordCloudOptions.from_mapping(invalid)


def test_configuration_roundtrip_and_zero_spacing():
    options = WordCloudOptions.from_mapping(
        {"word_spacing": 0, "font": "uploaded:" + "a" * 64 + ".woff2"}
    )
    assert options.word_spacing == 0
    assert WordCloudOptions.from_mapping(options.to_dict()) == options


def make_application(messages: list[UnifiedMessage]) -> AnalysisApplicationService:
    config = MagicMock()
    config.get_llm_max_concurrent.return_value = 1
    config.get_wordcloud_options.return_value = WordCloudOptions()
    config.get_max_messages.return_value = 100
    config.get_bot_self_ids.return_value = []
    config.get_filter_bot_messages.return_value = True
    config.get_analysis_days.return_value = 1
    config.get_incremental_min_messages.return_value = 2
    config.get_topic_analysis_enabled.return_value = False
    config.get_golden_quote_analysis_enabled.return_value = False
    config.get_chat_quality_analysis_enabled.return_value = False
    adapter = MagicMock()
    adapter.platform_id = "bot"
    adapter.bot_self_ids = ["bot-self"]
    adapter.fetch_messages = AsyncMock(return_value=messages)
    adapter.is_group_muted = AsyncMock(return_value=False)
    bots = MagicMock()
    bots.get_adapter.return_value = adapter
    bots.get_adapter_platform_id.return_value = "bot"
    stats = MagicMock()
    stats.calculate_group_statistics.return_value = GroupStatistics(2, 4, 1, "", [], 0)
    domain = MagicMock()
    domain.analyze_user_activity.return_value = {}
    store = MagicMock()
    store.save_batch = AsyncMock(return_value=True)
    store.update_last_analyzed_cursor = AsyncMock()
    return AnalysisApplicationService(
        config_manager=config,
        bot_manager=bots,
        history_manager=MagicMock(),
        report_generator=MagicMock(),
        llm_analyzer=MagicMock(),
        statistics_service=stats,
        analysis_domain_service=domain,
        incremental_store=store,
        checkpoint_store=MagicMock(),
    )


@pytest.mark.asyncio
async def test_standalone_collection_filters_bots_commands_without_analysis_side_effects():
    service = make_application(
        [
            message("one", "海风 海风"),
            message("two", "海风"),
            message("command", "/词云"),
            message("bot", "机器人噪音", sender_id="bot-self"),
        ]
    )
    data = await service.collect_wordcloud("group", "bot", 1)
    assert data.message_count == 2
    assert data.frequencies == (WordFrequency("海风", 3, 2),)
    service.config_manager.get_wordcloud_options.assert_called_once_with(
        "bot:GroupMessage:group"
    )
    assert not service.llm_analyzer.mock_calls
    assert not service.incremental_store.mock_calls
    assert not service.checkpoint_store.mock_calls
    assert not service.history_manager.mock_calls


@pytest.mark.asyncio
async def test_standalone_disabled_does_not_fetch():
    service = make_application([])
    service.config_manager.get_wordcloud_options.return_value = WordCloudOptions(
        enabled=False
    )
    with pytest.raises(ValueError, match="已关闭"):
        await service.collect_wordcloud("group", "bot")
    service.bot_manager.get_adapter.return_value.fetch_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_incremental_counts_only_filtered_deduplicated_truncated_batch():
    boundary = int(time.time()) - 20
    eligible = message("new-one", "海风", boundary)
    service = make_application(
        [
            message("before", "旧词", boundary - 1),
            message("seen", "旧词", boundary),
            eligible,
            eligible,
            message("new-two", "星空", boundary + 1),
            message("deferred", "以后", boundary + 2),
        ]
    )
    service.incremental_store.get_last_analyzed_cursor = AsyncMock(
        return_value=(boundary, {"seen"})
    )
    with TraceContext(trace_id="wordcloud-boundary"):
        result = await service._incremental_service.execute_incremental_analysis(
            "group", "bot"
        )
    assert result["success"] is True
    batch = service.incremental_store.save_batch.call_args.args[0]
    assert batch.wordcloud.message_count == 2
    assert {entry.text for entry in batch.wordcloud.frequencies} == {"海风", "星空"}
    service.incremental_store.update_last_analyzed_cursor.assert_awaited_once_with(
        "group", boundary + 1, {"new-two"}
    )


@pytest.mark.asyncio
async def test_incremental_runtime_bot_messages_do_not_fill_threshold() -> None:
    """运行时识别的机器人消息不应凑满批次，也不应推进游标。"""
    boundary = int(time.time()) - 20
    service = make_application(
        [
            message("one", "海风", boundary),
            message("bot", "机器人噪音", boundary + 1, sender_id="bot-self"),
        ]
    )
    service.incremental_store.get_last_analyzed_cursor = AsyncMock(
        return_value=(0, set())
    )
    with TraceContext(trace_id="wordcloud-bot-threshold"):
        result = await service._incremental_service.execute_incremental_analysis(
            "group", "bot"
        )

    assert result == {
        "success": False,
        "reason": "below_threshold",
        "messages_count": 1,
    }
    service.incremental_store.save_batch.assert_not_awaited()
    service.incremental_store.update_last_analyzed_cursor.assert_not_awaited()
    service.statistics_service.calculate_group_statistics.assert_not_called()


@pytest.mark.asyncio
async def test_incremental_runtime_bot_is_filtered_before_batch_truncation() -> None:
    """排在前面的机器人消息不应挤占有效消息的批次名额。"""
    boundary = int(time.time()) - 20
    service = make_application(
        [
            message("bot", "机器人噪音", boundary, sender_id="bot-self"),
            message("one", "海风", boundary + 1),
            message("two", "星空", boundary + 2),
        ]
    )
    service.incremental_store.get_last_analyzed_cursor = AsyncMock(
        return_value=(0, set())
    )
    with TraceContext(trace_id="wordcloud-bot-truncation"):
        result = await service._incremental_service.execute_incremental_analysis(
            "group", "bot"
        )

    assert result["success"] is True
    batch = service.incremental_store.save_batch.call_args.args[0]
    assert batch.messages_count == 2
    assert batch.wordcloud.message_count == 2
    assert {entry.text for entry in batch.wordcloud.frequencies} == {"海风", "星空"}
    analyzed = service.statistics_service.calculate_group_statistics.call_args.args[0]
    assert [item.message_id for item in analyzed] == ["one", "two"]
    service.incremental_store.update_last_analyzed_cursor.assert_awaited_once_with(
        "group", boundary + 2, {"two"}
    )


@pytest.mark.asyncio
async def test_incremental_combines_bot_ids_without_mutating_config() -> None:
    """保留配置补充的屏蔽账号，合并运行时账号时不修改原列表。"""
    boundary = int(time.time()) - 20
    service = make_application(
        [
            message("bot", "机器人噪音", boundary, sender_id="bot-self"),
            message("extra", "其他噪音", boundary + 1, sender_id="other-bot"),
            message("one", "海风", boundary + 2),
            message("two", "星空", boundary + 3),
        ]
    )
    configured_ids = ["other-bot"]
    runtime_ids = ["bot-self", "other-bot", ""]
    service.config_manager.get_bot_self_ids.return_value = configured_ids
    service.bot_manager.get_adapter.return_value.bot_self_ids = runtime_ids
    service.incremental_store.get_last_analyzed_cursor = AsyncMock(
        return_value=(0, set())
    )
    with TraceContext(trace_id="wordcloud-bot-merged-ids"):
        result = await service._incremental_service.execute_incremental_analysis(
            "group", "bot"
        )

    assert result["success"] is True
    batch = service.incremental_store.save_batch.call_args.args[0]
    assert batch.wordcloud.message_count == 2
    assert {entry.text for entry in batch.wordcloud.frequencies} == {"海风", "星空"}
    assert configured_ids == ["other-bot"]
    assert runtime_ids == ["bot-self", "other-bot", ""]
    service.incremental_store.update_last_analyzed_cursor.assert_awaited_once_with(
        "group", boundary + 3, {"two"}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("configured_ids", [[], ["other-bot"]])
async def test_incremental_disabled_bot_filter_keeps_all_messages(
    configured_ids: list[str],
) -> None:
    """关闭过滤时，配置与运行时识别的机器人消息均参与统计。"""
    boundary = int(time.time()) - 20
    service = make_application(
        [
            message("one", "海风", boundary),
            message("bot", "星空", boundary + 1, sender_id="bot-self"),
            message("extra", "海风", boundary + 2, sender_id="other-bot"),
        ]
    )
    original_ids = configured_ids.copy()
    service.config_manager.get_bot_self_ids.return_value = configured_ids
    service.config_manager.get_filter_bot_messages.return_value = False
    service.config_manager.get_incremental_min_messages.return_value = 3
    service.incremental_store.get_last_analyzed_cursor = AsyncMock(
        return_value=(0, set())
    )
    with TraceContext(trace_id="wordcloud-bot-filter-disabled"):
        result = await service._incremental_service.execute_incremental_analysis(
            "group", "bot"
        )

    assert result["success"] is True
    batch = service.incremental_store.save_batch.call_args.args[0]
    assert batch.messages_count == 3
    assert batch.wordcloud.message_count == 3
    assert set(batch.wordcloud.frequencies) == {
        WordFrequency("海风", 2, 2),
        WordFrequency("星空", 1, 1),
    }
    assert configured_ids == original_ids
    service.incremental_store.update_last_analyzed_cursor.assert_awaited_once_with(
        "group", boundary + 2, {"extra"}
    )


@pytest.mark.asyncio
async def test_failed_batch_persistence_does_not_advance_cursor():
    boundary = int(time.time()) - 20
    service = make_application(
        [message("one", "海风", boundary), message("two", "海风", boundary + 1)]
    )
    service.incremental_store.get_last_analyzed_cursor = AsyncMock(
        return_value=(0, set())
    )
    service.incremental_store.save_batch.return_value = False
    with TraceContext(trace_id="wordcloud-persistence-failure"):
        result = await service._incremental_service.execute_incremental_analysis(
            "group", "bot"
        )
    assert result["reason"] == "batch_persistence_failed"
    service.incremental_store.update_last_analyzed_cursor.assert_not_awaited()
