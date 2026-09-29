"""Satori 通用协议适配器的单元测试。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.domain.value_objects.platform_capabilities import (
    SATORI_CAPABILITIES,
    get_capabilities,
)
from src.domain.value_objects.unified_message import MessageContentType
from src.infrastructure.platform.adapters.satori_adapter import SatoriAdapter
from src.infrastructure.platform.factory import PlatformAdapterFactory


class FakeHistoryManager:
    """用于测试分页读取的伪历史记录管理器。"""

    def __init__(self, pages: dict[int, list[object]]) -> None:
        self.pages = pages

    async def get(
        self,
        platform_id: str,
        user_id: str,
        page: int,
        page_size: int,
    ) -> list[object]:
        assert platform_id == "satori-test"
        assert user_id == "guild-123"
        return self.pages.get(page, [])


def make_record(
    record_id: int,
    message_id: str,
    sender_id: str,
    timestamp: int,
    text: str,
    sender_name: str | None = None,
    extra_parts: list[dict[str, object]] | None = None,
) -> SimpleNamespace:
    """构建伪历史记录对象的测试辅助函数。"""
    msg_parts: list[dict[str, object]] = [{"type": "plain", "text": text}]
    if extra_parts:
        msg_parts.extend(extra_parts)

    return SimpleNamespace(
        id=record_id,
        sender_id=sender_id,
        sender_name=sender_id if sender_name is None else sender_name,
        created_at=datetime.fromtimestamp(timestamp, timezone.utc),
        content={
            "type": "user",
            "message": msg_parts,
            "_satori": {
                "message_id": message_id,
                "timestamp": timestamp,
            },
        },
    )


def make_satori_adapter(
    send_http_request: AsyncMock | None = None,
    bot_self_ids: list[str] | None = None,
) -> tuple[SatoriAdapter, SimpleNamespace]:
    """构建 SatoriAdapter 实例的测试辅助函数。"""
    bot = SimpleNamespace(
        send_http_request=send_http_request or AsyncMock(return_value={})
    )
    adapter = SatoriAdapter(
        bot,  # type: ignore[arg-type]
        {
            "platform_id": "satori-test",
            "bot_self_ids": bot_self_ids or ["bot-user-id"],
        },
    )
    return adapter, bot


def test_satori_capabilities():
    """验证 Satori 平台能力定义。"""
    caps = get_capabilities("satori")
    assert caps is not None
    assert caps.platform_name == "satori"
    assert caps.supports_message_history is True
    assert caps.supports_image_message is True
    assert caps.supports_text_message is True
    assert caps.supports_file_message is True
    assert caps.can_analyze() is True
    assert caps.can_send_report("image") is True
    assert caps.can_send_report("text") is True


def test_satori_factory_registration():
    """验证 Satori 适配器可通过工厂正确解析和创建。"""
    assert PlatformAdapterFactory.is_supported("satori")
    adapter_cls = PlatformAdapterFactory.get_adapter_class("satori")
    assert adapter_cls is SatoriAdapter

    adapter = PlatformAdapterFactory.create(
        "satori",
        SimpleNamespace(send_http_request=AsyncMock()),
        {"platform_id": "satori-main"},
    )
    assert adapter is not None
    assert isinstance(adapter, SatoriAdapter)
    assert adapter.platform_id == "satori-main"


@pytest.mark.asyncio
async def test_satori_history_fetch_pagination_dedup_and_cutoff():
    """验证 fetch_messages 支持分页拉取、去重、截止时间过滤与机器人自身消息过滤。"""
    now_ts = int(datetime.now(timezone.utc).timestamp())
    adapter, _ = make_satori_adapter(bot_self_ids=["bot-id"])

    # 配置两页历史记录：第一页含 3 条（1条重复ID，1条机器人消息），第二页含 1 条
    history_pages = {
        1: [
            make_record(1, "msg-101", "user-1", now_ts - 50, "hello", sender_name="User One"),
            make_record(2, "msg-102", "bot-id", now_ts - 40, "bot response", sender_name="Bot"),
            make_record(3, "msg-101", "user-1", now_ts - 50, "duplicate"),
            make_record(4, "msg-103", "user-2", now_ts - 30, "world", sender_name="User Two"),
        ],
        2: [
            make_record(5, "msg-100", "user-3", now_ts - 100, "earlier msg", sender_name="User Three"),
        ],
    }

    adapter.set_context(
        SimpleNamespace(  # type: ignore[arg-type]
            message_history_manager=FakeHistoryManager(history_pages)  # type: ignore[arg-type]
        )
    )
    adapter.HISTORY_PAGE_SIZE = 4  # type: ignore[assignment]

    messages = await adapter.fetch_messages("guild-123", days=1, max_count=10)

    # 机器人自身消息 (msg-102) 和重复消息 (msg-101) 必须被过滤
    assert len(messages) == 3
    assert [m.message_id for m in messages] == ["msg-100", "msg-101", "msg-103"]
    assert [m.sender_name for m in messages] == ["User Three", "User One", "User Two"]
    assert [m.text_content for m in messages] == ["earlier msg", "hello", "world"]


@pytest.mark.asyncio
async def test_satori_history_message_parts_conversion():
    """验证各种消息类型（@、图片、文件、音频、视频、回复）的正确转换。"""
    adapter, _ = make_satori_adapter()
    record = make_record(
        record_id=1,
        message_id="msg-1",
        sender_id="user-123",
        timestamp=1000,
        text="text before ",
        sender_name="Alice",
        extra_parts=[
            {"type": "at", "target_id": "target-456"},
            {"type": "image", "url": "https://example.com/img.png"},
            {"type": "file", "name": "report.pdf", "url": "https://example.com/doc.pdf"},
            {"type": "audio", "url": "https://example.com/voice.wav"},
            {"type": "video", "url": "https://example.com/video.mp4"},
            {"type": "reply", "id": "ref-999"},
        ],
    )

    unified = adapter._convert_history_record(record, "guild-123")  # type: ignore[arg-type]
    assert unified is not None
    assert unified.sender_name == "Alice"
    assert unified.sender_id == "user-123"

    types = [c.type for c in unified.contents]
    assert MessageContentType.TEXT in types
    assert MessageContentType.AT in types
    assert MessageContentType.IMAGE in types
    assert MessageContentType.FILE in types
    assert MessageContentType.VOICE in types
    assert MessageContentType.VIDEO in types
    assert MessageContentType.REPLY in types


@pytest.mark.asyncio
async def test_satori_group_list():
    """验证 get_group_list 从插件群组注册表中获取所有群组 ID。"""
    adapter, _ = make_satori_adapter()
    mock_registry = SimpleNamespace(
        get_all_group_ids=AsyncMock(return_value=["group-1", "group-2", "group-1"])
    )
    adapter._plugin_instance = SimpleNamespace(platform_group_registry=mock_registry)  # type: ignore[assignment]

    groups = await adapter.get_group_list()
    assert groups == ["group-1", "group-2"]


@pytest.mark.asyncio
async def test_satori_group_info_success_and_fallback():
    """验证 get_group_info 请求 /guild.get 以及接口失败时的优雅降级。"""
    # 1. 成功响应
    send_req = AsyncMock(
        return_value={
            "id": "guild-100",
            "name": "AstrBot Developers",
            "avatar": "https://example.com/guild_avatar.png",
            "member_count": 42,
        }
    )
    adapter, _ = make_satori_adapter(send_http_request=send_req)

    group = await adapter.get_group_info("guild-100")
    assert group is not None
    assert group.group_id == "guild-100"
    assert group.group_name == "AstrBot Developers"
    assert group.member_count == 42
    assert await adapter.get_group_avatar_url("guild-100") == "https://example.com/guild_avatar.png"
    send_req.assert_awaited_with("POST", "/guild.get", {"guild_id": "guild-100"})

    # 2. 接口异常降级
    fail_req = AsyncMock(side_effect=Exception("API Timeout"))
    adapter_fallback, _ = make_satori_adapter(send_http_request=fail_req)
    group_fallback = await adapter_fallback.get_group_info("guild-200")
    assert group_fallback is not None
    assert group_fallback.group_id == "guild-200"
    assert group_fallback.group_name == "Satori Group guild-200"


@pytest.mark.asyncio
async def test_satori_group_members_pagination():
    """验证 get_group_members 正确处理 /guild.member.list 分页。"""
    async def mock_send_req(method: str, path: str, data: dict) -> dict:
        assert method == "POST"
        assert path == "/guild.member.list"
        next_tok = data.get("next")
        if not next_tok:
            return {
                "data": [
                    {"user": {"id": "u1", "name": "User 1", "avatar": "https://img/1.png"}},
                    {"user": {"id": "u2", "nick": "Nick 2"}},
                ],
                "next": "token_page_2",
            }
        elif next_tok == "token_page_2":
            return {
                "data": [
                    {"user": {"id": "u3", "name": "User 3"}},
                ],
                "next": None,
            }
        return {}

    adapter, _ = make_satori_adapter(send_http_request=AsyncMock(side_effect=mock_send_req))
    members = await adapter.get_group_members("guild-100")

    assert len(members) == 3
    assert [m.user_id for m in members] == ["u1", "u2", "u3"]
    assert [m.nickname for m in members] == ["User 1", "Nick 2", "User 3"]
    assert members[0].avatar_url == "https://img/1.png"


@pytest.mark.asyncio
async def test_satori_member_info_cached_and_api():
    """验证 get_member_info 优先从缓存读取，缓存未命中时请求 API。"""
    send_req = AsyncMock(
        return_value={
            "user": {"id": "u99", "name": "API User", "avatar": "https://img/99.png"}
        }
    )
    adapter, _ = make_satori_adapter(send_http_request=send_req)

    # 1. 命中缓存
    adapter.remember_user_profile("u1", nickname="Cached User", avatar_url="https://img/cached.png")
    member_cached = await adapter.get_member_info("guild-100", "u1")
    assert member_cached is not None
    assert member_cached.nickname == "Cached User"
    assert member_cached.avatar_url == "https://img/cached.png"
    send_req.assert_not_awaited()

    # 2. 缓存未命中，请求 API
    member_api = await adapter.get_member_info("guild-100", "u99")
    assert member_api is not None
    assert member_api.nickname == "API User"
    assert member_api.avatar_url == "https://img/99.png"


@pytest.mark.asyncio
async def test_satori_avatar_urls():
    """验证用户与群聊头像解析逻辑（缓存、QQ CDN 降级、Satori API）。"""
    send_req = AsyncMock(
        return_value={"id": "non_numeric_user", "avatar": "https://satori.avatar/u.png"}
    )
    adapter, _ = make_satori_adapter(send_http_request=send_req)

    # 1. 纯数字 QQ 账号 -> 标准 QQ 头像 CDN
    qq_avatar = await adapter.get_user_avatar_url("123456789", size=100)
    assert qq_avatar == "https://q1.qlogo.cn/g?b=qq&nk=123456789&s=100"

    # 2. 已缓存的头像 URL
    adapter.remember_user_profile("alpha_user", avatar_url="https://cached.url/avatar.jpg")
    cached_avatar = await adapter.get_user_avatar_url("alpha_user")
    assert cached_avatar == "https://cached.url/avatar.jpg"

    # 3. 非数字且未缓存账号 -> Satori API /user.get
    api_avatar = await adapter.get_user_avatar_url("non_numeric_user")
    assert api_avatar == "https://satori.avatar/u.png"

    # 4. 纯数字群号 -> 标准 QQ 群头像 CDN
    group_avatar = await adapter.get_group_avatar_url("987654321", size=100)
    assert group_avatar == "https://p.qlogo.cn/gh/987654321/987654321/100"


@pytest.mark.asyncio
async def test_satori_send_messages(tmp_path: Path):
    """验证 send_text_message、send_image_message 与 send_file_message 发送载荷。"""
    send_req = AsyncMock(return_value={"id": "msg-ack-1"})
    adapter, _ = make_satori_adapter(send_http_request=send_req)

    # 1. 发送纯文本消息
    text_ok = await adapter.send_text_message("channel-1", "Hello <world> & friends")
    assert text_ok is True
    send_req.assert_awaited_with(
        "POST",
        "/message.create",
        {"channel_id": "channel-1", "content": "Hello &lt;world&gt; &amp; friends"},
    )

    # 2. 发送网络图片与配文
    send_req.reset_mock()
    img_ok = await adapter.send_image_message("channel-1", "https://cdn.example/report.png", "Today's report")
    assert img_ok is True
    send_req.assert_awaited_with(
        "POST",
        "/message.create",
        {"channel_id": "channel-1", "content": '<img src="https://cdn.example/report.png"/>Today&#x27;s report'},
    )

    # 3. 发送本地图片（Base64 Data URL 编码）
    local_img = tmp_path / "test.png"
    local_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")
    send_req.reset_mock()
    local_img_ok = await adapter.send_image_message("channel-1", str(local_img))
    assert local_img_ok is True
    call_args = send_req.call_args[0]
    content = call_args[2]["content"]
    assert content.startswith('<img src="data:image/png;base64,')

    # 4. 发送文件消息
    local_file = tmp_path / "summary.pdf"
    local_file.write_bytes(b"%PDF-1.4...")
    send_req.reset_mock()
    file_ok = await adapter.send_file_message("channel-1", str(local_file), "daily_summary.pdf")
    assert file_ok is True
    call_args = send_req.call_args[0]
    file_content = call_args[2]["content"]
    assert 'name="daily_summary.pdf"' in file_content
    assert '<file src="data:application/pdf;base64,' in file_content


def test_satori_convert_to_raw_format():
    """验证 convert_to_raw_format 将 UnifiedMessage 列表转换为标准字典结构。"""
    adapter, _ = make_satori_adapter()
    msg = SimpleNamespace(
        message_id="msg-1",
        timestamp=123456,
        sender_id="u1",
        sender_name="Alice",
        text_content="Hello world",
        group_id="g1",
    )
    raw = adapter.convert_to_raw_format([msg])  # type: ignore[arg-type]
    assert len(raw) == 1
    assert raw[0]["message_id"] == "msg-1"
    assert raw[0]["time"] == 123456
    sender_dict = raw[0]["sender"]
    assert isinstance(sender_dict, dict)
    assert sender_dict["nickname"] == "Alice"
    assert raw[0]["message"] == "Hello world"
    assert raw[0]["group_id"] == "g1"


