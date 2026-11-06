"""验证多平台统一消息进入模型和图表时保留身份、关系及表情信息。"""

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.services.analysis_domain_service import AnalysisDomainService
from src.domain.services.statistics_service import StatisticsService
from src.domain.value_objects import GoldenQuote, SummaryTopic, TokenUsage
from src.domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from src.infrastructure.analysis.analyzers.chat_quality_analyzer import (
    ChatQualityAnalyzer,
)
from src.infrastructure.analysis.analyzers.golden_quote_analyzer import (
    GoldenQuoteAnalyzer,
)
from src.infrastructure.analysis.analyzers.topic_analyzer import TopicAnalyzer
from src.infrastructure.analysis.utils.analysis_messages import (
    extract_analysis_messages,
)
from src.infrastructure.visualization.activity_charts import ActivityVisualizer


def make_message(**changes):
    message = UnifiedMessage(
        message_id="message-1",
        sender_id="member-openid",
        sender_name="昵称",
        sender_card="群名片",
        group_id="channel-1",
        text_content="周末见",
        timestamp=int(datetime(2026, 11, 6, 10, 0).timestamp()),
        platform="discord",
        reply_to_id="message-before",
        contents=(
            MessageContent(type=MessageContentType.AT, at_user_id="member-other"),
            MessageContent(type=MessageContentType.TEXT, text="周末\n见\x00"),
            MessageContent(type=MessageContentType.EMOJI, emoji_id="smile"),
        ),
    )
    return replace(message, **changes)


def make_analyzer(kind):
    analyzer = object.__new__(kind)
    analyzer.incremental_max_count = None
    analyzer.config_manager = SimpleNamespace(
        get_enable_user_card=lambda: True,
        get_bot_self_ids=lambda: ["bot-openid"],
        get_max_topics=lambda: 3,
        get_max_golden_quotes=lambda: 3,
        get_topic_analysis_prompt=lambda: "${messages_text}",
        get_golden_quote_analysis_prompt=lambda: "${messages_text}",
        get_quality_analysis_prompt=lambda: "${messages_text}",
    )
    return analyzer


@pytest.mark.parametrize(
    "platform,user_id",
    [
        ("onebot", "0012345"),
        ("qq_official", "member-openid"),
        ("discord", "123456789012345678"),
        ("telegram", "user-tg"),
        ("satori", "member:abc"),
    ],
)
def test_identity_and_relations_are_platform_neutral(platform, user_id):
    message = make_message(platform=platform, sender_id=user_id)
    result = extract_analysis_messages([message], use_card=True, bot_self_ids=[])
    assert result == [
        {
            "time": "10:00",
            "sender": "群名片",
            "user_id": user_id,
            "content": "[回复:message-before] @[member-other] 周末 见",
        }
    ]
    assert message.contents[1].text == "周末\n见\x00"


@pytest.mark.parametrize(
    "use_card,name,card,expected",
    [
        (True, "昵称", "名片", "名片"),
        (False, "昵称", "名片", "昵称"),
        (True, "昵称", None, "昵称"),
        (False, "", "名片", "名片"),
        (False, "", None, "member-openid"),
    ],
)
def test_display_name_preference(use_card, name, card, expected):
    result = extract_analysis_messages(
        [make_message(sender_name=name, sender_card=card)],
        use_card=use_card,
        bot_self_ids=[],
    )
    assert result[0]["sender"] == expected


def test_empty_commands_bots_and_text_only_snapshots():
    messages = [
        make_message(sender_id="bot-openid"),
        make_message(text_content="/分析", contents=()),
        make_message(text_content="", contents=(), reply_to_id=None),
        make_message(
            text_content="",
            contents=(
                MessageContent(
                    type=MessageContentType.IMAGE, url="https://invalid.example/image"
                ),
            ),
            reply_to_id=None,
        ),
        make_message(
            message_id="snapshot",
            text_content="旧快照正文",
            contents=(),
            reply_to_id=None,
        ),
    ]
    result = extract_analysis_messages(
        messages, use_card=False, bot_self_ids=["bot-openid"]
    )
    assert [row["content"] for row in result] == ["旧快照正文"]


def test_mentions_and_reply_only_messages_keep_their_relation():
    mention = make_message(
        text_content="",
        contents=(MessageContent(type=MessageContentType.AT, at_user_id="all"),),
        reply_to_id=None,
    )
    reply = make_message(text_content="", contents=())
    result = extract_analysis_messages(
        [mention, reply], use_card=False, bot_self_ids=[]
    )
    assert [row["content"] for row in result] == ["@[all]", "[回复:message-before]"]


def test_reply_target_is_identifiable_without_labelling_unrelated_messages():
    target = make_message(
        message_id="message-before",
        text_content="周末去哪",
        contents=(),
        reply_to_id=None,
    )
    unrelated = make_message(
        message_id="unrelated", text_content="另一件事", contents=(), reply_to_id=None
    )
    result = extract_analysis_messages(
        [target, unrelated, make_message()], use_card=False, bot_self_ids=[]
    )
    assert result[0]["content"] == "[消息:message-before] 周末去哪"
    assert result[1]["content"] == "另一件事"
    assert result[2]["content"].startswith("[回复:message-before]")


def test_all_prompt_builders_use_the_same_relations():
    message = make_message()
    topic = make_analyzer(TopicAnalyzer)
    quote = make_analyzer(GoldenQuoteAnalyzer)
    quality = make_analyzer(ChatQualityAnalyzer)
    prompts = [
        topic.build_prompt(topic.extract_text_messages([message])),
        quote.build_prompt(quote.extract_interesting_messages([message])),
        quality.build_prompt([message]),
    ]
    for prompt in prompts:
        assert "@[member-other]" in prompt
        assert prompt.count("[回复:message-before]") == 1
        assert "周末 见" in prompt
    assert "[member-openid]" in prompts[0]
    assert "[member-openid]" in prompts[1]
    assert "[群名片]" in prompts[2]
    assert quality.build_prompt([replace(message, sender_id="bot-openid")]) == ""


@pytest.mark.asyncio
async def test_topic_and_quote_resolve_string_ids_after_analysis():
    topic = make_analyzer(TopicAnalyzer)
    topic.analyze = AsyncMock(
        return_value=(
            [
                SummaryTopic(
                    topic="出游", detail="周末见", contributors=["[member-openid]"]
                ),
            ],
            TokenUsage(1, 2, 3),
        )
    )
    quote = make_analyzer(GoldenQuoteAnalyzer)
    quote.analyze = AsyncMock(
        return_value=(
            [
                GoldenQuote(content="周末见", sender="[member-openid]", reason="相约"),
            ],
            TokenUsage(1, 2, 3),
        )
    )
    topics, usage = await topic.analyze_topics(
        [make_message()], "discord:GroupMessage:channel-1"
    )
    quotes, _ = await quote.analyze_golden_quotes([make_message()])
    assert topics[0].contributor_ids == ["member-openid"]
    assert topics[0].contributors == ["群名片"]
    assert quotes[0].user_id == "member-openid"
    assert quotes[0].sender == "群名片"
    assert usage.total_tokens == 3
    assert topic.analyze.call_args.args[0][0]["user_id"] == "member-openid"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"sub_type": 1, "summary": ""}, 1),
        ({"sub_type": 0, "summary": "动画表情"}, 0),
        ({"summary": "动画表情"}, 1),
        (None, 0),
    ],
)
def test_emoji_totals_users_and_hourly_distribution_agree(raw, expected):
    image = MessageContent(type=MessageContentType.IMAGE, raw_data=raw)
    messages = [
        make_message(contents=(image,), text_content="", reply_to_id=None),
        make_message(
            message_id="m2",
            timestamp=int(datetime(2026, 11, 6, 11, 0).timestamp()),
            contents=(
                MessageContent(type=MessageContentType.EMOJI, emoji_id="custom"),
            ),
            text_content="",
            reply_to_id=None,
        ),
    ]
    stats = StatisticsService(ActivityVisualizer()).calculate_group_statistics(messages)
    users = AnalysisDomainService().analyze_user_activity(messages)
    chart = stats.activity_visualization
    assert stats.emoji_count == expected + 1
    assert users["member-openid"]["emoji_count"] == expected + 1
    assert chart.hourly_activity == {10: 1, 11: 1}
    assert chart.activity_heatmap_data["emoji_normalized"][10] == expected * 100
    assert chart.activity_heatmap_data["emoji_normalized"][11] == 100


def test_text_only_chart_handles_zero_emoji_and_empty_input():
    visualizer = ActivityVisualizer()
    message = make_message(
        contents=(MessageContent(type=MessageContentType.TEXT, text="正文"),)
    )
    for messages in ([message], []):
        chart = visualizer.generate_activity_visualization(messages)
        assert all(
            value == 0
            for value in chart.activity_heatmap_data["emoji_normalized"].values()
        )


def test_onebot_protocol_fields_stop_at_adapter_boundary():
    from src.domain.services.message_cleaner_service import MessageCleanerService
    from src.infrastructure.platform.adapters.onebot.message_converter import (
        OneBotMessageConverter,
    )

    original = OneBotMessageConverter.to_unified_message(
        {
            "message_id": "onebot-message",
            "time": 123,
            "sender": {"user_id": 123, "nickname": "昵称"},
            "message": [
                {"type": "at", "data": {"qq": "456"}},
                {"type": "reply", "data": {"id": "previous-message"}},
                {"type": "text", "data": {"text": "下次一起去"}},
            ],
        },
        "group-1",
    )
    assert original.sender_id == "123"
    assert original.contents[0].at_user_id == "456"
    cleaned = MessageCleanerService().clean_messages([original])
    result = extract_analysis_messages(cleaned, use_card=False, bot_self_ids=[])
    assert result[0]["user_id"] == "123"
    assert result[0]["content"] == "[回复:previous-message] @[456] 下次一起去"
