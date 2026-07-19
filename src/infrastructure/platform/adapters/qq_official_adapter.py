"""QQ Official Bot adapter backed by AstrBot's local message history."""

from __future__ import annotations

import asyncio
import base64
import os
import random
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import aiohttp

from ....domain.value_objects.platform_capabilities import (
    QQ_OFFICIAL_CAPABILITIES,
    PlatformCapabilities,
)
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ....utils.logger import logger
from ..base import PlatformAdapter

if TYPE_CHECKING:
    from astrbot.api.star import Context


class QQOfficialAdapter(PlatformAdapter):
    """Adapter for QQ Official group bots (WebSocket and Webhook variants)."""

    platform_name = "qq_official"
    AVATAR_TEMPLATE = "https://thirdqq.qlogo.cn/qqapp/{appid}/{member_openid}/640"
    HISTORY_PAGE_SIZE = 500
    MARKDOWN_CHUNK_SIZE = 3900

    def __init__(self, bot_instance: Any, config: dict | None = None):
        super().__init__(bot_instance, config)
        self._context: Context | None = None
        self._plugin_instance = config.get("plugin_instance") if config else None
        self._platform_id = str(config.get("platform_id", "")).strip() if config else ""
        ids = config.get("bot_self_ids", []) if config else []
        self.bot_self_ids = [str(item) for item in ids if item]
        self.appid = self._resolve_appid(config or {})
        self._markdown_msg_seq = random.randint(1, 10000)

    @property
    def platform_id(self) -> str:
        return self._platform_id or "qq_official"

    def _resolve_appid(self, config: dict) -> str:
        direct = str(config.get("appid", "") or "").strip()
        if direct:
            return direct
        platform = getattr(self.bot, "platform", None)
        platform_config = getattr(platform, "config", None)
        if isinstance(platform_config, dict):
            return str(platform_config.get("appid", "") or "").strip()
        return ""

    def set_context(self, context: Context) -> None:
        self._context = context

    def _init_capabilities(self) -> PlatformCapabilities:
        return QQ_OFFICIAL_CAPABILITIES

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: str | None = None,
        since_ts: int | None = None,
    ) -> list[UnifiedMessage]:
        if not self._context:
            logger.warning("[QQOfficial] 未设置 context，无法读取本地消息历史")
            return []

        history_mgr = self._context.message_history_manager
        target_count = max(1, int(max_count))
        cutoff_ts = (
            int(since_ts)
            if since_ts and since_ts > 0
            else int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        )
        before_record_id: int | None = None
        if before_id:
            try:
                before_record_id = int(before_id)
            except (TypeError, ValueError):
                pass

        messages: list[UnifiedMessage] = []
        seen_message_ids: set[str] = set()
        page = 1

        try:
            while len(messages) < target_count:
                records = await history_mgr.get(
                    platform_id=self.platform_id,
                    user_id=str(group_id),
                    page=page,
                    page_size=self.HISTORY_PAGE_SIZE,
                )
                if not records:
                    break

                reached_cutoff = False
                for record in records:
                    record_id = getattr(record, "id", None)
                    if (
                        before_record_id is not None
                        and record_id is not None
                        and int(record_id) >= before_record_id
                    ):
                        continue

                    unified = self._convert_history_record(record, str(group_id))
                    if not unified:
                        continue
                    if unified.timestamp < cutoff_ts:
                        reached_cutoff = True
                        continue
                    if unified.sender_id in self.bot_self_ids:
                        continue
                    if unified.message_id in seen_message_ids:
                        continue

                    seen_message_ids.add(unified.message_id)
                    messages.append(unified)

                if len(messages) >= target_count:
                    break
                if reached_cutoff or len(records) < self.HISTORY_PAGE_SIZE:
                    break
                page += 1

            messages.sort(key=lambda item: (item.timestamp, item.message_id))
            if len(messages) > target_count:
                messages = messages[-target_count:]
            logger.info(
                "[QQOfficial] 从本地历史获取群 %s 消息 %s 条",
                group_id,
                len(messages),
            )
            return messages
        except Exception as exc:
            logger.error("[QQOfficial] 读取本地消息历史失败: %s", exc, exc_info=True)
            return []

    def _convert_history_record(
        self, record: Any, group_id: str
    ) -> UnifiedMessage | None:
        try:
            content = getattr(record, "content", None)
            if not isinstance(content, dict):
                return None
            metadata = content.get("_qq_official")
            if not isinstance(metadata, dict):
                return None

            contents: list[MessageContent] = []
            text_parts: list[str] = []
            for part in content.get("message", []):
                if not isinstance(part, dict):
                    continue
                part_type = str(part.get("type", "")).lower()
                if part_type in {"plain", "text"}:
                    text = str(part.get("text", "") or "")
                    text_parts.append(text)
                    contents.append(
                        MessageContent(type=MessageContentType.TEXT, text=text)
                    )
                elif part_type == "image":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE,
                            url=str(part.get("url", "") or ""),
                        )
                    )
                elif part_type == "at":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.AT,
                            at_user_id=str(part.get("target_id", "") or ""),
                        )
                    )
                elif part_type == "file":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.FILE,
                            url=str(part.get("url", "") or ""),
                            raw_data={"name": part.get("name", "")},
                        )
                    )
                elif part_type in {"record", "voice"}:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VOICE,
                            url=str(part.get("url", "") or ""),
                        )
                    )
                elif part_type == "video":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VIDEO,
                            url=str(part.get("url", "") or ""),
                        )
                    )

            message_id = str(metadata.get("message_id", "") or "")
            if not message_id:
                message_id = f"local:{getattr(record, 'id', '')}"
            timestamp = int(metadata.get("timestamp", 0) or 0)
            if timestamp <= 0:
                created_at = getattr(record, "created_at", None)
                timestamp = int(created_at.timestamp()) if created_at else 0
            sender_id = str(getattr(record, "sender_id", "") or "")
            if not sender_id:
                return None

            return UnifiedMessage(
                message_id=message_id,
                sender_id=sender_id,
                sender_name=sender_id,
                sender_card=None,
                group_id=group_id,
                text_content="".join(text_parts),
                contents=tuple(contents),
                timestamp=timestamp,
                platform=self.platform_name,
            )
        except Exception as exc:
            logger.debug("[QQOfficial] 转换本地历史记录失败: %s", exc)
            return None

    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        result: list[dict] = []
        for message in messages:
            chain: list[dict] = []
            for content in message.contents:
                if content.type == MessageContentType.TEXT:
                    chain.append({"type": "text", "data": {"text": content.text}})
                elif content.type == MessageContentType.IMAGE:
                    chain.append({"type": "image", "data": {"url": content.url}})
                elif content.type == MessageContentType.AT:
                    chain.append({"type": "at", "data": {"qq": content.at_user_id}})
            result.append(
                {
                    "message_id": message.message_id,
                    "time": message.timestamp,
                    "group_id": message.group_id,
                    "sender": {
                        "user_id": message.sender_id,
                        "nickname": message.sender_id,
                        "card": "",
                    },
                    "message": chain,
                    "user_id": message.sender_id,
                }
            )
        return result

    async def _send_chain(self, group_id: str, chain: Any) -> bool:
        if not self._context:
            logger.error("[QQOfficial] 未设置 context，无法发送消息")
            return False
        try:
            # AstrBot's QQ Official adapter keeps the group/channel scene only
            # in memory. Restore it before proactive sends so scheduled reports
            # continue to work after a process restart, before the next event.
            platform = getattr(self.bot, "platform", None)
            remember_scene = getattr(platform, "remember_session_scene", None)
            if callable(remember_scene):
                remember_scene(str(group_id), "group")
            umo = f"{self.platform_id}:GroupMessage:{group_id}"
            return bool(await self._context.send_message(umo, chain))
        except Exception as exc:
            logger.error("[QQOfficial] 发送消息失败: %s", exc, exc_info=True)
            return False

    async def send_text(
        self, group_id: str, text: str, reply_to: str | None = None
    ) -> bool:
        from astrbot.api.event import MessageChain

        return await self._send_chain(group_id, MessageChain().message(str(text)))

    async def send_text_report(
        self,
        group_id: str,
        content: str,
        fallback_content: str | None = None,
    ) -> bool:
        """Send long reports as QQ custom Markdown with plain-text fallback."""
        chunks = self._split_markdown_report(str(content))
        if not chunks:
            return True

        markdown_enabled = True
        sent_markdown_chunks = 0
        for chunk in chunks:
            if markdown_enabled:
                try:
                    if await self._send_markdown_chunk(group_id, chunk):
                        sent_markdown_chunks += 1
                        continue
                    logger.warning(
                        "[QQOfficial] Markdown 接口未返回成功结果，后续改用普通文本"
                    )
                except Exception as exc:
                    logger.warning(
                        "[QQOfficial] Markdown 报告发送失败，后续改用普通文本: %s",
                        exc,
                    )
                markdown_enabled = False

                if fallback_content and sent_markdown_chunks == 0:
                    for fallback_chunk in self._split_markdown_report(
                        str(fallback_content)
                    ):
                        if not await self.send_text(group_id, fallback_chunk):
                            return False
                    return True

            if not await self.send_text(group_id, chunk):
                return False
        return True

    async def _send_markdown_chunk(self, group_id: str, content: str) -> bool:
        api = getattr(self.bot, "api", None)
        post_group_message = getattr(api, "post_group_message", None)
        if not callable(post_group_message):
            return False

        platform = getattr(self.bot, "platform", None)
        remember_scene = getattr(platform, "remember_session_scene", None)
        if callable(remember_scene):
            remember_scene(str(group_id), "group")

        try:
            from botpy.types.message import MarkdownPayload

            markdown: Any = MarkdownPayload(content=content)
        except ImportError:
            # Allows lightweight test environments while botpy is provided by
            # AstrBot in production.
            markdown = {"content": content}

        result = await post_group_message(  # type: ignore[arg-type]
            group_openid=str(group_id),
            msg_type=2,
            markdown=markdown,
            msg_seq=self._next_markdown_msg_seq(),
        )
        return result is not None

    def _next_markdown_msg_seq(self) -> int:
        self._markdown_msg_seq = (self._markdown_msg_seq % 10000) + 1
        return self._markdown_msg_seq

    def _split_markdown_report(self, content: str) -> list[str]:
        """Split Markdown on block boundaries without breaking mention tokens."""
        normalized = str(content or "").strip()
        if not normalized:
            return []

        blocks = re.split(r"\n{2,}", normalized)
        chunks: list[str] = []
        current = ""

        def append_piece(piece: str) -> None:
            nonlocal current
            candidate = f"{current}\n\n{piece}" if current else piece
            if len(candidate) <= self.MARKDOWN_CHUNK_SIZE:
                current = candidate
                return
            if current:
                chunks.append(current)
            current = piece

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            if len(block) <= self.MARKDOWN_CHUNK_SIZE:
                append_piece(block)
                continue

            lines = block.splitlines() or [block]
            piece = ""
            for line in lines:
                candidate = f"{piece}\n{line}" if piece else line
                if len(candidate) <= self.MARKDOWN_CHUNK_SIZE:
                    piece = candidate
                    continue
                if piece:
                    append_piece(piece)
                while len(line) > self.MARKDOWN_CHUNK_SIZE:
                    split_at = self.MARKDOWN_CHUNK_SIZE
                    mention_start = line.rfind("<@", 0, split_at)
                    mention_end = (
                        line.find(">", mention_start) if mention_start >= 0 else -1
                    )
                    if mention_start >= 0 and mention_end >= split_at:
                        split_at = mention_start or self.MARKDOWN_CHUNK_SIZE
                    append_piece(line[:split_at])
                    line = line[split_at:]
                piece = line
            if piece:
                append_piece(piece)

        if current:
            chunks.append(current)
        return chunks

    async def send_image(
        self, group_id: str, image_path: str, caption: str = ""
    ) -> bool:
        from astrbot.api.event import MessageChain

        chain = MessageChain()
        if caption:
            chain.message(caption)
        if image_path.startswith("base64://"):
            chain.base64_image(image_path[len("base64://") :])
        elif image_path.startswith("data:") and "," in image_path:
            chain.base64_image(image_path.split(",", 1)[1])
        elif image_path.startswith(("http://", "https://")):
            chain.url_image(image_path)
        else:
            chain.file_image(os.path.abspath(image_path))
        return await self._send_chain(group_id, chain)

    async def send_file(
        self, group_id: str, file_path: str, filename: str | None = None
    ) -> bool:
        from astrbot.api.event import MessageChain
        from astrbot.core.message.components import File

        name = filename or os.path.basename(file_path) or "report"
        if file_path.startswith(("http://", "https://")):
            component = File(name=name, url=file_path)
        else:
            component = File(name=name, file=os.path.abspath(file_path))
        return await self._send_chain(group_id, MessageChain([component]))

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        return UnifiedGroup(
            group_id=str(group_id),
            group_name=str(group_id),
            platform=self.platform_name,
        )

    async def get_group_list(self) -> list[str]:
        if self._plugin_instance and hasattr(
            self._plugin_instance, "get_seen_group_ids"
        ):
            try:
                return await self._plugin_instance.get_seen_group_ids(self.platform_id)
            except Exception as exc:
                logger.warning("[QQOfficial] 获取已见群列表失败: %s", exc)
        return []

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        return []

    async def get_member_info(
        self, group_id: str, user_id: str
    ) -> UnifiedMember | None:
        return UnifiedMember(
            user_id=str(user_id),
            nickname="",
            avatar_url=await self.get_user_avatar_url(str(user_id)),
        )

    async def get_user_avatar_url(self, user_id: str, size: int = 100) -> str | None:
        if not self.appid or not user_id:
            return None
        return self.AVATAR_TEMPLATE.format(
            appid=quote(self.appid, safe=""),
            member_openid=quote(str(user_id), safe=""),
        )

    async def get_user_avatar_data(self, user_id: str, size: int = 100) -> str | None:
        avatar_url = await self.get_user_avatar_url(user_id, size)
        if not avatar_url:
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(
                timeout=timeout, trust_env=True
            ) as session:
                async with session.get(avatar_url) as response:
                    if response.status != 200:
                        return None
                    payload = await response.read()
            if not payload:
                return None
            mime = "image/png" if payload.startswith(b"\x89PNG") else "image/jpeg"
            return f"data:{mime};base64,{base64.b64encode(payload).decode('utf-8')}"
        except Exception as exc:
            logger.debug("[QQOfficial] 下载头像失败: %s", exc)
            return None

    async def get_group_avatar_url(self, group_id: str, size: int = 100) -> str | None:
        return None

    async def batch_get_avatar_urls(
        self, user_ids: list[str], size: int = 100
    ) -> dict[str, str | None]:
        unique_ids = list(
            dict.fromkeys(str(user_id) for user_id in user_ids if user_id)
        )

        async def get_one(user_id: str) -> tuple[str, str | None]:
            return user_id, await self.get_user_avatar_url(user_id, size)

        return dict(await asyncio.gather(*(get_one(user_id) for user_id in unique_ids)))
