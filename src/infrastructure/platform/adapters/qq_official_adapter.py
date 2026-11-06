"""QQ Official Bot adapter backed by AstrBot's local message history."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import random
import re
import time
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Protocol, cast
from urllib.parse import quote
from weakref import WeakValueDictionary

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
from ....entrypoints.plugin_host import PluginHostProtocol
from ....shared.type_guards import (
    is_object_awaitable,
    is_object_collection,
    is_object_list,
    is_string_mapping,
)
from ....utils.logger import logger
from ..base import PlatformAdapter
from ..message_normalization import is_image_sticker
from ..qq_official_faces import restore_qq_face_features
from .qq_markdown_images import QQMarkdownImages

if TYPE_CHECKING:
    from astrbot.api.event import MessageChain
    from astrbot.api.star import Context
    from botpy.http import BotHttp

    from ....domain.repositories.bot_client_protocol import (
        HistoryRecordProtocol,
        QQOfficialBotProtocol,
    )
    from ....domain.value_objects.analysis_results import QQOfficialMemberProfile


class _GroupInfoQuery(Protocol):
    """可选 SDK 群资料方法的调用契约。"""

    def __call__(self, *, group_openid: str) -> object:
        """返回原始响应或可等待的响应，交由适配器校验。"""
        ...


class QQOfficialAdapter(PlatformAdapter["QQOfficialBotProtocol"]):
    """Adapter for QQ Official group bots (WebSocket and Webhook variants)."""

    platform_name = "qq_official"
    AVATAR_TEMPLATE = "https://thirdqq.qlogo.cn/qqapp/{appid}/{member_openid}/640"
    HISTORY_PAGE_SIZE = 500
    MARKDOWN_CHUNK_SIZE = 3900
    GROUP_INFO_TIMEOUT = 3

    def __init__(
        self,
        bot_instance: QQOfficialBotProtocol,
        config: dict[str, object] | None = None,
    ) -> None:
        super().__init__(bot_instance, config)
        self._context: Context | None = None
        raw_plugin = config.get("plugin_instance") if config else None
        self._plugin_instance: PluginHostProtocol | None = (
            raw_plugin if isinstance(raw_plugin, PluginHostProtocol) else None
        )
        self._platform_id = str(config.get("platform_id", "")).strip() if config else ""
        raw_ids: object = config.get("bot_self_ids", []) if config else []
        self.bot_self_ids = (
            [str(item) for item in raw_ids if item]
            if is_object_collection(raw_ids)
            else []
        )
        self.appid = self._resolve_appid(config or {})
        self._markdown_msg_seq = random.randint(1, 10000)
        self._member_profiles: dict[str, QQOfficialMemberProfile] = {}
        self._markdown_images: QQMarkdownImages | None = None
        self._group_info_cache: dict[str, tuple[float, UnifiedGroup]] = {}
        self._group_info_locks: WeakValueDictionary[str, asyncio.Lock] = (
            WeakValueDictionary()
        )

    @property
    def platform_id(self) -> str:
        return self._platform_id or "qq_official"

    def _resolve_appid(self, config: Mapping[str, object]) -> str:
        direct = str(config.get("appid", "") or "").strip()
        if direct:
            return direct
        platform = self.bot.platform if self.bot else None
        platform_config = platform.config if platform else None
        if isinstance(platform_config, Mapping):
            return str(platform_config.get("appid", "") or "").strip()
        return ""

    @staticmethod
    def _is_placeholder_sender_name(name: str | None, sender_id: str) -> bool:
        normalized = str(name or "").strip()
        if not normalized:
            return True
        if normalized.lower() in {"unknown", "none", "null", "nil", "undefined"}:
            return True
        return normalized == str(sender_id).strip()

    @classmethod
    def _resolve_history_sender_name(
        cls, sender_name: str | None, sender_id: str, group_id: str
    ) -> str:
        normalized = str(sender_name or "").strip()
        if not cls._is_placeholder_sender_name(normalized, sender_id):
            return normalized
        digest = hashlib.sha256(f"{group_id}\0{sender_id}".encode()).hexdigest()[:8]
        return f"群友-{digest.upper()}"

    def set_context(self, context: Context | None) -> None:
        if context is not None:
            self._context = context

    def remember_user_profile(
        self, user_id: str, nickname: str | None = None, avatar_url: str | None = None
    ) -> None:
        """缓存 QQ 官方消息事件提供的用户资料。

        Args:
            user_id: QQ 成员 OpenID。
            nickname: 事件提供的显示名称。
            avatar_url: 事件提供的头像地址。
        """
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return

        profile = self._member_profiles.setdefault(normalized_user_id, {})
        normalized_nickname = str(nickname or "").strip()
        if not self._is_placeholder_sender_name(
            normalized_nickname, normalized_user_id
        ):
            profile["nickname"] = normalized_nickname

        normalized_avatar_url = str(avatar_url or "").strip()
        if normalized_avatar_url.startswith(("https://", "http://")):
            profile["avatar_url"] = normalized_avatar_url

    def _init_capabilities(self) -> PlatformCapabilities:
        return QQ_OFFICIAL_CAPABILITIES

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: str | None = None,
        since_ts: int | float | None = None,
    ) -> list[UnifiedMessage]:
        if not self._context:
            logger.warning("[QQOfficial] 未设置 context，无法读取本地消息历史")
            return []

        history_mgr = self._context.message_history_manager
        target_count = max(1, int(max_count))
        cutoff_ts = self.calculate_effective_start_timestamp(
            days=days, since_ts=since_ts
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
                records: Sequence[HistoryRecordProtocol] = await history_mgr.get(
                    platform_id=self.platform_id,
                    user_id=str(group_id),
                    page=page,
                    page_size=self.HISTORY_PAGE_SIZE,
                )
                if not records:
                    break

                reached_cutoff = False
                for record in records:
                    record_id = record.id
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
        self, record: HistoryRecordProtocol, group_id: str
    ) -> UnifiedMessage | None:
        try:
            content = record.content
            if not is_string_mapping(content):
                return None
            metadata = content.get("_qq_official")
            if not is_string_mapping(metadata):
                return None

            contents: list[MessageContent] = []
            reply_to_id = str(content.get("reply_to_id") or "")
            text_parts: list[str] = []
            raw_parts = content.get("message", [])
            if is_object_list(raw_parts):
                for part in raw_parts:
                    if not is_string_mapping(part):
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
                                is_sticker=is_image_sticker(part),
                                url=str(part.get("url", "") or ""),
                            )
                        )
                    elif part_type == "reply":
                        reply_to_id = reply_to_id or str(part.get("id") or "")
                        contents.append(MessageContent(type=MessageContentType.REPLY))
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
                                text=str(part.get("name") or ""),
                                url=str(part.get("url", "") or ""),
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

            contents.extend(restore_qq_face_features(metadata))

            message_id = str(
                metadata.get("message_id", "") or content.get("message_id", "") or ""
            )
            if not message_id:
                message_id = f"local:{record.id or ''}"
            raw_timestamp = metadata.get("timestamp", 0) or 0
            timestamp = (
                int(raw_timestamp)
                if isinstance(raw_timestamp, (str, int, float))
                else 0
            )
            if timestamp <= 0:
                created_at = record.created_at
                timestamp = int(created_at.timestamp()) if created_at else 0
            sender_id = str(record.sender_id or "")
            if not sender_id:
                return None
            sender_name = self._resolve_history_sender_name(
                record.sender_name, sender_id, group_id
            )

            return UnifiedMessage(
                message_id=message_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_card=None,
                group_id=group_id,
                text_content="".join(text_parts),
                contents=tuple(contents),
                reply_to_id=reply_to_id or None,
                timestamp=timestamp,
                platform=self.platform_name,
            )
        except Exception as exc:
            logger.debug("[QQOfficial] 转换本地历史记录失败: %s", exc)
            return None

    async def _send_chain(self, group_id: str, chain: MessageChain) -> bool:
        if not self._context:
            logger.error("[QQOfficial] 未设置 context，无法发送消息")
            return False
        try:
            # AstrBot's QQ Official adapter keeps the group/channel scene only
            # in memory. Restore it before proactive sends so scheduled reports
            # continue to work after a process restart, before the next event.
            platform = self.bot.platform if self.bot else None
            if platform and hasattr(platform, "remember_session_scene"):
                platform.remember_session_scene(str(group_id), "group")
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
        """发送图文 Markdown 报告，并在结束后释放本次上传的图片素材。"""
        try:
            return await self._send_text_report_chunks(
                group_id, content, fallback_content
            )
        finally:
            if self._markdown_images is not None:
                await self._markdown_images.release(content)

    async def upload_markdown_image(self, image: bytes) -> str | None:
        """上传本地 PNG 素材，供报告内嵌使用，不发送独立消息。

        Args:
            image: 原生渲染生成的 PNG 字节。

        Returns:
            当前机器人拥有的素材引用；客户端不支持时返回 None。
        """
        if self._markdown_images is None:
            # 旧版 botpy 尚未封装素材接口，沿用其鉴权 HTTP 客户端请求新端点。
            api = self.bot.api if self.bot else None
            http = getattr(api, "_http", None)
            if http is None:
                return None
            self._markdown_images = QQMarkdownImages(http)
        return await self._markdown_images.upload(image)

    async def _send_text_report_chunks(
        self,
        group_id: str,
        content: str,
        fallback_content: str | None,
    ) -> bool:
        """按 QQ 长度限制发送 Markdown 分片，失败时恢复文字报告。"""
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
        api = self.bot.api if self.bot else None
        if not api or not hasattr(api, "post_group_message"):
            return False

        platform = self.bot.platform if self.bot else None
        if platform and hasattr(platform, "remember_session_scene"):
            platform.remember_session_scene(str(group_id), "group")

        try:
            from botpy.types.message import MarkdownPayload

            markdown: dict[str, object] = dict(MarkdownPayload(content=content))
        except ImportError:
            # 轻量测试环境可能未安装 botpy，生产环境由 AstrBot 提供。
            markdown = {"content": content}
        if re.search(r"!\[[^\]]*\]\((?:https?://|qqbot-media://)", content):
            # 要求 QQ 明确返回转存失败，才能恢复包含统计的完整文字报告。
            markdown["force_verify_image_resource"] = True

        call_result = api.post_group_message(
            group_openid=str(group_id),
            msg_type=2,
            markdown=markdown,
            msg_seq=self._next_markdown_msg_seq(),
        )
        if is_object_awaitable(call_result):
            result = await call_result
        else:
            result = call_result
        return is_string_mapping(result) and bool(result.get("id"))

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
        # Prefer the public API; fall back to internal for backward compat.
        # astrbot.core is not part of the stable contract and may change.
        from astrbot.api.event import MessageChain
        from astrbot.core.message.components import File

        name = filename or os.path.basename(file_path) or "report"
        if file_path.startswith(("http://", "https://")):
            component = File(name=name, url=file_path)
        else:
            component = File(name=name, file=os.path.abspath(file_path))
        return await self._send_chain(group_id, MessageChain([component]))

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        """查询官方群资料，接口不可用时保留旧群名或回退群 OpenID。

        Args:
            group_id: 当前机器人对应的群 OpenID。

        Returns:
            群资料；空标识返回 None。成功缓存一小时，失败五分钟后再尝试，
            缓存仅属于当前适配器实例，不在不同机器人之间共享。

        Raises:
            asyncio.CancelledError: 调用方取消查询时原样传播。
        """
        target_id = str(group_id).strip()
        if not target_id:
            return None
        # 只合并同群查询；弱引用让最后一个等待者退出后自动释放锁记录。
        lock = self._group_info_locks.setdefault(target_id, asyncio.Lock())
        async with lock:
            cached = self._group_info_cache.get(target_id)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            result = (
                cached[1]
                if cached
                else UnifiedGroup(
                    group_id=target_id,
                    group_name=target_id,
                    platform=self.platform_name,
                )
            )
            ttl = 300
            try:
                api = self.bot.api if self.bot else None
                method: object = getattr(api, "get_group_info", None)
                async with asyncio.timeout(self.GROUP_INFO_TIMEOUT):
                    response: object
                    if callable(method):
                        # 边界已确认可调用；参数不兼容仍由下方异常回退处理。
                        query = cast("_GroupInfoQuery", method)
                        pending = query(group_openid=target_id)
                        response = (
                            await pending if is_object_awaitable(pending) else pending
                        )
                    else:
                        # 旧 SDK 没有该方法，复用它的鉴权、令牌刷新与沙箱设置。
                        from botpy.http import Route

                        class GroupInfoRoute(Route):
                            DOMAIN = "api.bot.qq.com"

                        http: BotHttp | None = getattr(api, "_http", None)
                        if http is None:
                            raise RuntimeError("当前 QQ 客户端不支持群资料查询")
                        response = await http.request(
                            GroupInfoRoute(
                                "GET",
                                "/v2/groups/{group_openid}/info",
                                group_openid=quote(target_id, safe=""),
                            )
                        )
                if is_string_mapping(response) and is_string_mapping(
                    response.get("data")
                ):
                    response = response["data"]
                if not is_string_mapping(response):
                    raise ValueError("群资料响应格式无效")
                name = response.get("group_name")
                returned_id = response.get("group_openid")
                if returned_id is not None and returned_id != target_id:
                    raise ValueError("群资料响应标识不匹配")
                if (
                    not isinstance(name, str)
                    or not name.strip()
                    or name.strip() == target_id
                ):
                    raise ValueError("群资料响应缺少有效群名")
                count = response.get("group_member_num")
                description = response.get("group_finger_memo")
                result = UnifiedGroup(
                    group_id=target_id,
                    group_name=" ".join(name.split()),
                    member_count=count if type(count) is int and count >= 0 else 0,
                    description=description if isinstance(description, str) else None,
                    platform=self.platform_name,
                )
                ttl = 3600
            except Exception as exc:
                # 不输出响应正文、令牌或重复 INFO；缺权限不影响分析与发送。
                logger.debug(
                    "[QQOfficial] 群 %s 资料查询未成功，继续使用缓存或群标识（%s）",
                    target_id,
                    type(exc).__name__,
                )
            if (
                target_id not in self._group_info_cache
                and len(self._group_info_cache) >= 256
            ):
                self._group_info_cache.pop(next(iter(self._group_info_cache)))
            self._group_info_cache[target_id] = (time.monotonic() + ttl, result)
            return result

    async def get_group_list(self) -> list[str]:
        if isinstance(self._plugin_instance, PluginHostProtocol):
            try:
                res = await self._plugin_instance.get_seen_group_ids(self.platform_id)
                return list(res)
            except Exception as exc:
                logger.warning("[QQOfficial] 获取已见群列表失败: %s", exc)
        return []

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        return []

    async def get_member_info(
        self, group_id: str, user_id: str
    ) -> UnifiedMember | None:
        profile = self._member_profiles.get(str(user_id), {})
        return UnifiedMember(
            user_id=str(user_id),
            nickname=profile.get("nickname", ""),
            avatar_url=await self.get_user_avatar_url(str(user_id)),
        )

    async def get_user_avatar_url(self, user_id: str, size: int = 100) -> str | None:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return None
        profile = self._member_profiles.get(normalized_user_id, {})
        remembered_avatar_url = profile.get("avatar_url", "")
        if remembered_avatar_url:
            return remembered_avatar_url
        if not self.appid:
            return None
        return self.AVATAR_TEMPLATE.format(
            appid=quote(self.appid, safe=""),
            member_openid=quote(normalized_user_id, safe=""),
        )

    async def get_user_avatar_data(self, user_id: str, size: int = 100) -> str | None:
        avatar_url = await self.get_user_avatar_url(user_id, size)
        if not avatar_url:
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with (
                aiohttp.ClientSession(timeout=timeout, trust_env=True) as session,
                session.get(avatar_url) as response,
            ):
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
