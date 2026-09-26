import asyncio
import base64
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.value_objects.unified_message import MessageContentType
from src.infrastructure.platform.adapters.discord_adapter import DiscordAdapter


class AsyncIterator:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self._iter = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


# ==========================================
# 1. 客户端初始化与能力集测试
# ==========================================


def test_discord_adapter_initialization_and_lazy_user_id():
    bot = SimpleNamespace(
        user=SimpleNamespace(id=987654321),
        get_channel=MockChannelGetter(),
    )
    adapter = DiscordAdapter(bot, config={})
    assert adapter._discord_client is bot
    assert adapter.bot_user_id == "987654321"

    caps = adapter.get_capabilities()
    assert caps.platform_name == "discord"
    assert caps.supports_forward_message is False
    assert caps.supports_image_message is True
    assert caps.supports_file_message is True


# ==========================================
# 2. 消息获取与多媒体内容转换测试
# ==========================================


class MockChannelGetter:
    def __call__(self, channel_id):
        return None


@pytest.mark.asyncio
async def test_fetch_messages_with_filters_attachments_and_stickers():
    bot_id = "999000"

    # 1. 普通文本消息
    msg1 = SimpleNamespace(
        id=101,
        author=SimpleNamespace(
            id=1001, name="Alice", nick="AliceGuild", global_name="AliceGlobal"
        ),
        content="Hello Discord",
        attachments=[],
        embeds=[],
        stickers=[],
        reference=None,
        created_at=datetime.fromtimestamp(1700000100, timezone.utc),
    )

    # 2. 富媒体附件消息 (图片、视频、语音、文件)
    att_img = SimpleNamespace(
        content_type="image/png",
        url="https://cdn.discordapp.com/img.png",
        filename="img.png",
        size=1024,
    )
    att_vid = SimpleNamespace(
        content_type="video/mp4",
        url="https://cdn.discordapp.com/vid.mp4",
        filename="vid.mp4",
        size=2048,
    )
    att_audio = SimpleNamespace(
        content_type="audio/ogg",
        url="https://cdn.discordapp.com/audio.ogg",
        filename="audio.ogg",
        size=512,
    )
    att_file = SimpleNamespace(
        content_type="application/pdf",
        url="https://cdn.discordapp.com/doc.pdf",
        filename="doc.pdf",
        size=4096,
    )

    msg2 = SimpleNamespace(
        id=102,
        author=SimpleNamespace(
            id=1002, name="Bob", nick=None, global_name="BobGlobal"
        ),
        content="Rich Media Message",
        attachments=[att_img, att_vid, att_audio, att_file],
        embeds=[],
        stickers=[],
        reference=SimpleNamespace(message_id=101),
        created_at=datetime.fromtimestamp(1700000200, timezone.utc),
    )

    # 3. 嵌入内容 (Embeds) 与 贴纸 (Stickers)
    embed = SimpleNamespace(
        image=SimpleNamespace(url="https://cdn.discordapp.com/embed.png"),
        description="Embed summary description",
    )
    sticker = SimpleNamespace(
        id=888999,
        name="cat_dance",
        url="https://cdn.discordapp.com/sticker.png",
    )

    msg3 = SimpleNamespace(
        id=103,
        author=SimpleNamespace(id=1003, name="Charlie", nick=None, global_name=None),
        content="Embed & Sticker",
        attachments=[],
        embeds=[embed],
        stickers=[sticker],
        reference=None,
        created_at=datetime.fromtimestamp(1700000300, timezone.utc),
    )

    # 4. 机器人自己的消息（应被过滤）
    msg_bot = SimpleNamespace(
        id=104,
        author=SimpleNamespace(id=int(bot_id), name="MyBot", nick=None, global_name=None),
        content="Bot reply should be filtered",
        attachments=[],
        embeds=[],
        stickers=[],
        reference=None,
        created_at=datetime.fromtimestamp(1700000400, timezone.utc),
    )

    # Mock channel and history
    channel = MagicMock()
    channel.history.return_value = AsyncIterator([msg_bot, msg3, msg2, msg1])

    bot = SimpleNamespace(
        user=SimpleNamespace(id=int(bot_id)),
        get_channel=lambda cid: channel if cid == 123456 else None,
    )

    adapter = DiscordAdapter(bot, config={"bot_user_id": bot_id})
    messages = await adapter.fetch_messages("123456", days=7, max_count=50)

    # Verify bot message was filtered out and messages are sorted in ascending timestamp order
    assert len(messages) == 3
    assert [m.message_id for m in messages] == ["101", "102", "103"]

    # Verify msg1
    assert messages[0].sender_id == "1001"
    assert messages[0].sender_name == "Alice"
    assert messages[0].sender_card == "AliceGuild"
    assert messages[0].text_content == "Hello Discord"

    # Verify msg2 attachments and reply
    assert messages[1].sender_card == "BobGlobal"
    assert messages[1].reply_to_id == "101"
    content_types = [c.type for c in messages[1].contents]
    assert MessageContentType.TEXT in content_types
    assert MessageContentType.IMAGE in content_types
    assert MessageContentType.VIDEO in content_types
    assert MessageContentType.VOICE in content_types
    assert MessageContentType.FILE in content_types

    # Verify msg3 embeds and stickers
    msg3_contents = messages[2].contents
    msg3_types = [c.type for c in msg3_contents]
    assert MessageContentType.IMAGE in msg3_types
    assert any("[Embed] Embed summary description" in (c.text or "") for c in msg3_contents)


def test_convert_to_raw_format():
    bot = SimpleNamespace(user=SimpleNamespace(id=123))
    adapter = DiscordAdapter(bot)

    # Construct unified message
    from src.domain.value_objects.unified_message import MessageContent, UnifiedMessage

    contents = (
        MessageContent(type=MessageContentType.TEXT, text="Hello raw"),
        MessageContent(type=MessageContentType.IMAGE, url="https://img.png"),
        MessageContent(type=MessageContentType.AT, at_user_id="999"),
        MessageContent(
            type=MessageContentType.REPLY, raw_data={"reply_id": "888"}
        ),
    )
    unified = UnifiedMessage(
        message_id="msg_1",
        sender_id="user_1",
        sender_name="Alice",
        sender_card="AliceCard",
        group_id="guild_channel_1",
        text_content="Hello raw",
        contents=contents,
        timestamp=1700000000,
        platform="discord",
    )

    raw_list = adapter.convert_to_raw_format([unified])
    assert len(raw_list) == 1
    raw = raw_list[0]
    assert raw["message_id"] == "msg_1"
    assert raw["group_id"] == "guild_channel_1"
    assert raw["sender"]["nickname"] == "Alice"
    assert raw["sender"]["card"] == "AliceCard"

    types = [seg["type"] for seg in raw["message"]]
    assert types == ["text", "image", "at", "reply"]
    assert raw["message"][2]["data"]["qq"] == "999"
    assert raw["message"][3]["data"]["id"] == "888"


# ==========================================
# 3. 消息发送与模拟合并转发测试
# ==========================================


@pytest.mark.asyncio
async def test_send_text_with_and_without_reply():
    channel = AsyncMock()
    channel.send = AsyncMock()

    bot = SimpleNamespace(
        user=SimpleNamespace(id=123),
        get_channel=lambda cid: channel,
    )
    adapter = DiscordAdapter(bot)

    # 1. Send plain text
    ok = await adapter.send_text("123456", "Hello Discord channel")
    assert ok is True
    channel.send.assert_called_with(content="Hello Discord channel", reference=None)

    # 2. Send text with reply
    with patch("discord.MessageReference") as mock_ref:
        mock_ref.return_value = "REF_OBJECT"
        ok_reply = await adapter.send_text("123456", "Reply text", reply_to="999888")
        assert ok_reply is True
        mock_ref.assert_called_with(message_id=999888, channel_id=123456)
        channel.send.assert_called_with(content="Reply text", reference="REF_OBJECT")


@pytest.mark.asyncio
async def test_send_image_base64_and_local():
    channel = AsyncMock()
    channel.send = AsyncMock()

    bot = SimpleNamespace(
        user=SimpleNamespace(id=123),
        get_channel=lambda cid: channel,
    )
    adapter = DiscordAdapter(bot)

    # 1. Base64 sending
    raw_b64 = base64.b64encode(b"fake_image_bytes").decode("utf-8")
    b64_uri = f"base64://{raw_b64}"

    with patch("discord.File") as mock_file:
        mock_file.return_value = "FILE_OBJ"
        ok = await adapter.send_image("123456", b64_uri, caption="Report Diagram")
        assert ok is True
        mock_file.assert_called()
        channel.send.assert_called_with(content="Report Diagram", file="FILE_OBJ")

    # 2. Local file sending
    with patch("discord.File") as mock_file:
        mock_file.return_value = "LOCAL_FILE_OBJ"
        ok_local = await adapter.send_image(
            "123456", "/path/to/report.png", caption=""
        )
        assert ok_local is True
        mock_file.assert_called_with("/path/to/report.png")
        channel.send.assert_called_with(content=None, file="LOCAL_FILE_OBJ")


@pytest.mark.asyncio
async def test_send_forward_msg_chunking():
    channel = AsyncMock()
    channel.send = AsyncMock()

    bot = SimpleNamespace(
        user=SimpleNamespace(id=123),
        get_channel=lambda cid: channel,
    )
    adapter = DiscordAdapter(bot)

    # 1. Single chunk (< 1900 chars)
    nodes = [
        {"data": {"name": "Alice", "content": "Short summary part 1"}},
        {"data": {"name": "Bob", "content": "Short summary part 2"}},
    ]
    ok = await adapter.send_forward_msg("123456", nodes)
    assert ok is True
    assert channel.send.call_count == 1
    call_content = channel.send.call_args[1]["content"]
    assert "Alice" in call_content
    assert "Short summary part 1" in call_content

    # 2. Large content chunking (> 1900 chars)
    channel.send.reset_mock()
    large_nodes = [
        {"data": {"name": f"User_{i}", "content": "A" * 500}} for i in range(10)
    ]
    ok_large = await adapter.send_forward_msg("123456", large_nodes)
    assert ok_large is True
    assert channel.send.call_count > 1
    # Verify each chunk is <= 1900 chars
    for call in channel.send.call_args_list:
        assert len(call[1]["content"]) <= 1900


# ==========================================
# 4. 群组与成员信息解析测试
# ==========================================


@pytest.mark.asyncio
async def test_get_group_info_guild_and_dm():
    # 1. Guild channel
    guild_channel = SimpleNamespace(
        id=123456,
        name="general",
        guild=SimpleNamespace(member_count=150, owner_id=999888),
        created_at=datetime.fromtimestamp(1700000000, timezone.utc),
    )

    # 2. DM channel (no guild)
    dm_channel = SimpleNamespace(
        id=654321,
        name="dm-channel",
        guild=None,
        recipients=[SimpleNamespace(id=1), SimpleNamespace(id=2)],
        owner_id=1,
        created_at=None,
    )

    bot = SimpleNamespace(
        user=SimpleNamespace(id=123),
        get_channel=lambda cid: guild_channel if cid == 123456 else dm_channel,
    )
    adapter = DiscordAdapter(bot)

    group_guild = await adapter.get_group_info("123456")
    assert group_guild is not None
    assert group_guild.group_name == "general"
    assert group_guild.member_count == 150
    assert group_guild.owner_id == "999888"

    group_dm = await adapter.get_group_info("654321")
    assert group_dm is not None
    assert group_dm.member_count == 3  # 2 recipients + 1 bot
    assert group_dm.owner_id == "1"


@pytest.mark.asyncio
async def test_get_member_list_and_roles():
    owner_member = SimpleNamespace(
        id=1001,
        name="OwnerUser",
        nick="TheBoss",
        global_name=None,
        guild_permissions=SimpleNamespace(administrator=True),
        joined_at=datetime.fromtimestamp(1700000000, timezone.utc),
    )
    admin_member = SimpleNamespace(
        id=1002,
        name="AdminUser",
        nick=None,
        global_name="AdminGlobal",
        guild_permissions=SimpleNamespace(administrator=True),
        joined_at=None,
    )
    normal_member = SimpleNamespace(
        id=1003,
        name="RegularUser",
        nick=None,
        global_name=None,
        guild_permissions=SimpleNamespace(administrator=False),
        joined_at=None,
    )

    channel = SimpleNamespace(
        id=123456,
        guild=SimpleNamespace(
            owner_id=1001, members=[owner_member, admin_member, normal_member]
        ),
    )

    bot = SimpleNamespace(
        user=SimpleNamespace(id=123),
        get_channel=lambda cid: channel,
    )
    adapter = DiscordAdapter(bot)

    members = await adapter.get_member_list("123456")
    assert len(members) == 3

    roles = {m.user_id: m.role for m in members}
    assert roles["1001"] == "owner"
    assert roles["1002"] == "admin"
    assert roles["1003"] == "member"

    cards = {m.user_id: m.card for m in members}
    assert cards["1001"] == "TheBoss"
    assert cards["1002"] == "AdminGlobal"
    assert cards["1003"] is None


# ==========================================
# 5. 头像 URL 尺寸对齐与表情回应测试
# ==========================================


@pytest.mark.asyncio
async def test_avatar_url_power_of_two_alignment():
    class MockAvatar:
        def __init__(self, size=128):
            self.size = size
            self.url = f"https://cdn.discordapp.com/avatars/user.png?size={size}"

        def with_size(self, size):
            return MockAvatar(size=size)

    user = SimpleNamespace(id=1001, display_avatar=MockAvatar())
    bot = SimpleNamespace(
        user=SimpleNamespace(id=123),
        get_user=lambda uid: user if uid == 1001 else None,
        get_channel=lambda cid: None,
    )
    adapter = DiscordAdapter(bot)

    # Size 100 aligns to 128 (power of 2)
    url = await adapter.get_user_avatar_url("1001", size=100)
    assert url is not None
    assert "size=128" in url

    # Size 300 aligns to 256
    url_256 = await adapter.get_user_avatar_url("1001", size=300)
    assert "size=256" in url_256

    # Batch avatars
    batch = await adapter.batch_get_avatar_urls(["1001", "9999"], size=100)
    assert "1001" in batch and batch["1001"] is not None
    assert "9999" in batch and batch["9999"] is None


@pytest.mark.asyncio
async def test_set_reaction_emoji_mapping():
    partial_msg = AsyncMock()
    channel = SimpleNamespace(
        get_partial_message=lambda mid: partial_msg if mid == 888999 else None
    )

    bot = SimpleNamespace(
        user=SimpleNamespace(id=123),
        get_channel=lambda cid: channel,
    )
    adapter = DiscordAdapter(bot)

    # 1. Add reaction mapping "analysis_started" -> "🔍"
    ok = await adapter.set_reaction("123456", "888999", "analysis_started", is_add=True)
    assert ok is True
    partial_msg.add_reaction.assert_called_with("🔍")

    # 2. Add reaction mapping "analysis_done" / "124" -> "📊"
    ok2 = await adapter.set_reaction("123456", "888999", "124", is_add=True)
    assert ok2 is True
    partial_msg.add_reaction.assert_called_with("📊")
