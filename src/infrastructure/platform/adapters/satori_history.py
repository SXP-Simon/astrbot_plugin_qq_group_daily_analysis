"""读取 Satori 历史 API，并将其消息片段转换为领域消息。"""

from __future__ import annotations

import asyncio
from html.parser import HTMLParser
from typing import TYPE_CHECKING

from ....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ....shared.type_guards import is_object_list, is_string_mapping
from ....utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Collection, Mapping

    SatoriRequest = Callable[[str, str, dict[str, object]], Awaitable[object]]


_MESSAGE_PAGE_SIZE = 30
_HISTORY_TIMEOUT_SECONDS = 15
_MEDIA_TYPES = {
    "img": MessageContentType.IMAGE,
    "image": MessageContentType.IMAGE,
    "audio": MessageContentType.VOICE,
    "record": MessageContentType.VOICE,
    "video": MessageContentType.VIDEO,
    "file": MessageContentType.FILE,
}


class _SatoriContentParser(HTMLParser):
    """解析消息片段，保留资源地址供分析使用。"""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[MessageContent] = []
        self.reply_to_id: str | None = None
        self._quote_depth = 0

    def handle_data(self, data: str) -> None:
        if not self._quote_depth and data:
            self.parts.append(MessageContent(MessageContentType.TEXT, text=data))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "quote":
            if not self._quote_depth:
                self.reply_to_id = values.get("id") or self.reply_to_id
                self.parts.append(MessageContent(MessageContentType.REPLY))
            self._quote_depth += 1
        elif self._quote_depth:
            return
        elif tag == "br":
            self.handle_data("\n")
        elif tag == "at":
            target = values.get("id") or values.get("name") or values.get("type")
            if target:
                self.parts.append(
                    MessageContent(MessageContentType.AT, at_user_id=target)
                )
        elif tag in {"emoji", "face", "milky:face"}:
            self.parts.append(
                MessageContent(
                    MessageContentType.EMOJI,
                    emoji_id=values.get("id") or "",
                    emoji_name=values.get("name") or "",
                )
            )
        elif tag in _MEDIA_TYPES and (url := values.get("src") or values.get("url")):
            filename = (
                (values.get("title") or values.get("name") or "")
                if tag == "file"
                else ""
            )
            self.parts.append(MessageContent(_MEDIA_TYPES[tag], url=url, text=filename))

    def handle_endtag(self, tag: str) -> None:
        if tag == "quote" and self._quote_depth:
            self._quote_depth -= 1


async def _read_pages(
    request: SatoriRequest, path: str, params: dict[str, object]
) -> AsyncIterator[list[object]]:
    """读取有效的分页结果，遇到不支持的响应或重复游标时结束。"""
    seen_cursors: set[str] = set()
    while True:
        response = await request("POST", path, params)
        if not is_string_mapping(response) or not is_object_list(
            data := response.get("data")
        ):
            return
        yield data
        cursor = response.get("next")
        if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
            return
        seen_cursors.add(cursor)
        params = {**params, "next": cursor}


def _decode_message(
    row: Mapping[str, object], group_id: str, timestamp: int
) -> UnifiedMessage | None:
    """将已校验时间戳的 Satori 消息转换为插件消息。"""
    message_id, user, content = row.get("id"), row.get("user"), row.get("content")
    if not isinstance(message_id, str) or not message_id or not is_string_mapping(user):
        return None
    sender_id = user.get("id")
    if not isinstance(sender_id, str) or not sender_id or not isinstance(content, str):
        return None

    parser = _SatoriContentParser()
    parser.feed(content)
    parser.close()
    if not parser.parts:
        return None
    member = row.get("member")
    card = member.get("nick") if is_string_mapping(member) else None
    return UnifiedMessage(
        message_id=message_id,
        group_id=group_id,
        sender_id=sender_id,
        sender_name=str(user.get("nick") or user.get("name") or sender_id),
        sender_card=card if isinstance(card, str) else None,
        timestamp=timestamp,
        contents=tuple(parser.parts),
        text_content="".join(
            part.text for part in parser.parts if part.type is MessageContentType.TEXT
        ).strip(),
        reply_to_id=parser.reply_to_id,
        platform="satori",
    )


async def fetch_satori_history(
    request: SatoriRequest,
    group_id: str,
    cutoff_ts: int,
    max_count: int,
    bot_self_ids: Collection[str],
) -> list[UnifiedMessage]:
    """从支持历史查询的 Satori 服务补拉指定时间窗口内的消息。

    Args:
        request: 当前平台实例的 Satori HTTP 请求入口。
        group_id: 分析目标的群组 ID。
        cutoff_ts: 最早纳入分析的 Unix 时间戳（秒）。
        max_count: 最多保留的消息条数。
        bot_self_ids: 应排除的机器人账号。

    Returns:
        可用的远端消息，服务不支持时为空，分页中断时保留已取得的消息。

    Raises:
        asyncio.CancelledError: 上层取消分析时传播。
    """
    messages: dict[str, UnifiedMessage] = {}
    channel_ids = [group_id]
    try:
        async with asyncio.timeout(_HISTORY_TIMEOUT_SECONDS):
            for channel_id in channel_ids:
                received_page = False
                channel_message_ids: set[str] = set()
                async for rows in _read_pages(
                    request,
                    "/message.list",
                    {
                        "channel_id": channel_id,
                        "direction": "before",
                        "order": "desc",
                        "limit": _MESSAGE_PAGE_SIZE,
                    },
                ):
                    received_page = True
                    reached_cutoff = False
                    for row in rows:
                        if not is_string_mapping(row):
                            continue
                        created_at = row.get("created_at")
                        if not isinstance(created_at, int) or created_at <= 0:
                            continue
                        timestamp = created_at // 1000
                        if timestamp < cutoff_ts:
                            reached_cutoff = True
                            continue
                        guild = row.get("guild")
                        if (
                            is_string_mapping(guild)
                            and guild.get("id", group_id) != group_id
                        ):
                            continue
                        channel = row.get("channel")
                        if (
                            is_string_mapping(channel)
                            and channel.get("id", channel_id) != channel_id
                        ):
                            continue
                        message = _decode_message(row, group_id, timestamp)
                        if message is None or message.sender_id in bot_self_ids:
                            continue
                        messages.setdefault(message.message_id, message)
                        channel_message_ids.add(message.message_id)
                    if reached_cutoff or len(channel_message_ids) >= max_count:
                        break
                if channel_id == group_id and not received_page:
                    # 群组 ID 与频道 ID 不同时，查询该群的文字频道。
                    async for channels in _read_pages(
                        request, "/channel.list", {"guild_id": group_id}
                    ):
                        for channel in channels:
                            if (
                                not is_string_mapping(channel)
                                or channel.get("type") != 0
                            ):
                                continue
                            candidate = channel.get("id")
                            if (
                                isinstance(candidate, str)
                                and candidate
                                and candidate not in channel_ids
                            ):
                                channel_ids.append(candidate)
    except Exception as exc:
        logger.debug("[Satori] 群 %s 远端历史补拉中断: %s", group_id, exc)
    return sorted(
        messages.values(), key=lambda item: (item.timestamp, item.message_id)
    )[-max_count:]
