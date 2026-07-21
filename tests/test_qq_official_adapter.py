import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from src.infrastructure.platform.adapters.qq_official_adapter import QQOfficialAdapter
from src.infrastructure.platform.factory import PlatformAdapterFactory


class FakeHistoryManager:
    def __init__(self, pages):
        self.pages = pages

    async def get(self, platform_id, user_id, page, page_size):
        assert platform_id == "official-main"
        assert user_id == "GROUP_OPENID"
        assert page_size == 500
        return self.pages.get(page, [])


def make_record(record_id, message_id, sender_id, timestamp, text, sender_name=None):
    return SimpleNamespace(
        id=record_id,
        sender_id=sender_id,
        sender_name=sender_id if sender_name is None else sender_name,
        created_at=datetime.fromtimestamp(timestamp, timezone.utc),
        content={
            "type": "user",
            "message": [{"type": "plain", "text": text}],
            "_qq_official": {
                "message_id": message_id,
                "timestamp": timestamp,
            },
        },
    )


def make_adapter():
    platform = SimpleNamespace(config={"appid": "1029384756"})
    bot = SimpleNamespace(platform=platform)
    return QQOfficialAdapter(
        bot,
        {
            "platform_id": "official-main",
            "bot_self_ids": ["BOT_OPENID"],
        },
    )


def test_avatar_url_uses_appid_and_member_openid():
    adapter = make_adapter()
    assert asyncio.run(adapter.get_user_avatar_url("A1B2C3_OPENID")) == (
        "https://thirdqq.qlogo.cn/qqapp/1029384756/A1B2C3_OPENID/640"
    )


def test_local_history_is_deduplicated_filtered_and_sorted():
    adapter = make_adapter()
    adapter.set_context(
        SimpleNamespace(
            message_history_manager=FakeHistoryManager(
                {
                    1: [
                        make_record(1, "MSG-2", "B_OPENID", 200, "second", "用户乙"),
                        make_record(2, "MSG-1", "A_OPENID", 100, "first", "用户甲"),
                        make_record(3, "MSG-2", "B_OPENID", 200, "duplicate"),
                        make_record(4, "MSG-BOT", "BOT_OPENID", 300, "bot"),
                    ]
                }
            )
        )
    )

    messages = asyncio.run(
        adapter.fetch_messages("GROUP_OPENID", days=36500, max_count=20)
    )

    assert [message.message_id for message in messages] == ["MSG-1", "MSG-2"]
    assert [message.sender_id for message in messages] == ["A_OPENID", "B_OPENID"]
    assert [message.sender_name for message in messages] == ["用户甲", "用户乙"]
    assert [message.text_content for message in messages] == ["first", "second"]

    raw_messages = adapter.convert_to_raw_format(messages)
    assert [message["sender"]["nickname"] for message in raw_messages] == [
        "用户甲",
        "用户乙",
    ]


def test_local_history_sender_name_uses_group_scoped_alias_for_placeholder():
    adapter = make_adapter()
    empty_name_record = make_record(
        1,
        "MSG-1",
        "A_OPENID",
        100,
        "first",
        sender_name="",
    )
    openid_name_record = make_record(
        2,
        "MSG-2",
        "A_OPENID",
        101,
        "second",
        sender_name="A_OPENID",
    )

    empty_name_message = adapter._convert_history_record(
        empty_name_record, "GROUP_OPENID"
    )
    openid_name_message = adapter._convert_history_record(
        openid_name_record, "GROUP_OPENID"
    )
    other_group_message = adapter._convert_history_record(
        openid_name_record, "OTHER_GROUP_OPENID"
    )

    assert empty_name_message is not None
    assert openid_name_message is not None
    assert other_group_message is not None
    assert empty_name_message.sender_name.startswith("群友-")
    assert "A_OPENID" not in empty_name_message.sender_name
    assert openid_name_message.sender_name == empty_name_message.sender_name
    assert other_group_message.sender_name != empty_name_message.sender_name


def test_factory_registers_both_official_platform_types():
    assert PlatformAdapterFactory.is_supported("qq_official")
    assert PlatformAdapterFactory.is_supported("qq_official_webhook")


def test_proactive_send_restores_group_scene_after_restart():
    remember_session_scene = Mock()
    platform = SimpleNamespace(
        config={"appid": "1029384756"},
        remember_session_scene=remember_session_scene,
    )
    adapter = QQOfficialAdapter(
        SimpleNamespace(platform=platform),
        {"platform_id": "official-main"},
    )
    sent = []

    async def send_message(umo, chain):
        sent.append((umo, chain))
        return True

    adapter.set_context(SimpleNamespace(send_message=send_message))

    assert asyncio.run(adapter._send_chain("GROUP_OPENID", object())) is True
    remember_session_scene.assert_called_once_with("GROUP_OPENID", "group")
    assert sent[0][0] == "official-main:GroupMessage:GROUP_OPENID"


def test_official_adapter_does_not_advertise_reply_support():
    assert make_adapter().get_capabilities().supports_reply_message is False


def test_markdown_report_posts_custom_markdown_with_unique_sequences():
    calls = []

    class FakeAPI:
        async def post_group_message(self, **kwargs):
            calls.append(kwargs)
            return {"id": f"MSG-{len(calls)}"}

    remember_session_scene = Mock()
    platform = SimpleNamespace(
        config={"appid": "1029384756"},
        remember_session_scene=remember_session_scene,
    )
    bot = SimpleNamespace(platform=platform, api=FakeAPI())
    adapter = QQOfficialAdapter(bot, {"platform_id": "official-main"})
    adapter.MARKDOWN_CHUNK_SIZE = 35

    assert asyncio.run(
        adapter.send_text_report(
            "GROUP_OPENID",
            "# 报告\n\n第一段 <@A_OPENID>\n\n第二段 " + "x" * 40,
        )
    )

    assert len(calls) >= 2
    assert all(call["group_openid"] == "GROUP_OPENID" for call in calls)
    assert all(call["msg_type"] == 2 for call in calls)
    assert all("markdown" in call for call in calls)
    assert len({call["msg_seq"] for call in calls}) == len(calls)
    assert all(len(str(call["markdown"])) > 0 for call in calls)
    remember_session_scene.assert_called_with("GROUP_OPENID", "group")


def test_markdown_report_falls_back_to_plain_text_after_api_failure():
    class FailingAPI:
        async def post_group_message(self, **kwargs):
            raise RuntimeError("markdown disabled")

    platform = SimpleNamespace(
        config={"appid": "1029384756"},
        remember_session_scene=Mock(),
    )
    adapter = QQOfficialAdapter(
        SimpleNamespace(platform=platform, api=FailingAPI()),
        {"platform_id": "official-main"},
    )
    sent = []

    async def send_text(group_id, text, reply_to=None):
        sent.append((group_id, text))
        return True

    adapter.send_text = send_text

    assert asyncio.run(
        adapter.send_text_report(
            "GROUP_OPENID",
            "# 报告\n\n![图表](https://t2i.example/chart.png)",
            fallback_content="# 报告\n\n<@A_OPENID> 获得称号",
        )
    )
    assert len(sent) == 1
    assert sent[0][0] == "GROUP_OPENID"
    assert "<@A_OPENID>" in sent[0][1]
    assert "t2i.example" not in sent[0][1]


def test_markdown_split_does_not_break_mentions():
    adapter = make_adapter()
    adapter.MARKDOWN_CHUNK_SIZE = 20
    chunks = adapter._split_markdown_report("x" * 17 + "<@A_OPENID>" + "tail")

    assert all(len(chunk) <= 20 for chunk in chunks)
    assert "".join(chunks) == "x" * 17 + "<@A_OPENID>" + "tail"
    assert any("<@A_OPENID>" in chunk for chunk in chunks)
