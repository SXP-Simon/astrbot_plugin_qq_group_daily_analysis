"""Satori 通用协议平台适配器

基于 AstrBot 本地消息历史与 Satori HTTP REST API 实现。
为群日常分析插件提供消息拉取、群组及成员元数据查询、头像获取以及长图/文本报告推送能力。
"""

from __future__ import annotations

import base64
import html
import mimetypes
from collections.abc import Awaitable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ....domain.repositories.plugin_host_repository import PluginHostProtocol
from ....domain.value_objects.platform_capabilities import (
    SATORI_CAPABILITIES,
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
    from collections.abc import Sequence

    from astrbot.api.star import Context

    from ....domain.repositories.bot_client_protocol import (
        HistoryRecordProtocol,
        SatoriClientProtocol,
    )


class SatoriAdapter(PlatformAdapter["SatoriClientProtocol"]):
    """Satori 通用协议机器人适配器。

    支持通过 AstrBot 本地消息数据库拉取群聊历史记录，
    通过 Satori REST API 查询群与成员资料，
    并通过 Satori XML 标签规范下发图文/文件分析报告。
    """

    platform_name = "satori"
    HISTORY_PAGE_SIZE = 500

    def __init__(
        self,
        bot_instance: SatoriClientProtocol,
        config: dict[str, object] | None = None,
    ) -> None:
        """初始化 Satori 适配器。

        Args:
            bot_instance: Satori 客户端底层实例。
            config: 平台配置字典（包含 platform_id、bot_self_ids 等）。
        """
        super().__init__(bot_instance, config)
        self._context: Context | None = None
        raw_plugin = config.get("plugin_instance") if config else None
        self._plugin_instance: PluginHostProtocol | None = (
            raw_plugin if isinstance(raw_plugin, PluginHostProtocol) else None
        )
        self._platform_id = str(config.get("platform_id", "")).strip() if config else ""
        raw_ids = config.get("bot_self_ids", []) if config else []
        self.bot_self_ids = (
            [str(item) for item in raw_ids if item]
            if isinstance(raw_ids, (list, tuple, set))
            else []
        )
        # 用户资料运行时缓存：user_id -> {"nickname": ..., "avatar_url": ...}
        self._member_profiles: dict[str, dict[str, str]] = {}

    @property
    def platform_id(self) -> str:
        """获取当前平台实例的唯一标识 ID。"""
        return self._platform_id or "satori"

    def set_context(self, context: Context | None) -> None:
        """注入 AstrBot 上下文对象，用于访问消息历史服务。

        Args:
            context: AstrBot 上下文实例。
        """
        if context is not None:
            self._context = context

    def remember_user_profile(
        self,
        user_id: str,
        nickname: str | None = None,
        avatar_url: str | None = None,
    ) -> None:
        """缓存事件或 API 中获取到的用户资料。

        Args:
            user_id: 用户唯一标识 ID。
            nickname: 可选的显示昵称。
            avatar_url: 可选的头像链接。
        """
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return

        profile = self._member_profiles.setdefault(normalized_user_id, {})
        if nickname and nickname.strip():
            profile["nickname"] = nickname.strip()
        if avatar_url and avatar_url.strip():
            profile["avatar_url"] = avatar_url.strip()

    def _init_capabilities(self) -> PlatformCapabilities:
        """返回 Satori 平台能力描述值对象。"""
        return SATORI_CAPABILITIES

    # ==================== IMessageRepository 接口实现 ====================

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: str | None = None,
        since_ts: int | float | None = None,
    ) -> list[UnifiedMessage]:
        """从 AstrBot 本地消息归档库拉取历史记录。

        按时间窗口、分页去重、Bot 自身过滤及时间升序进行处理。

        Args:
            group_id: 目标群组或频道 ID。
            days: 历史拉取天数。
            max_count: 最大拉取条数。
            before_id: 可选的记录 ID 上界。
            since_ts: 可选的增量分析游标起始时间戳。

        Returns:
            统一领域消息列表（按时间升序排序）。
        """
        if not self._context:
            logger.warning("[Satori] 未设置 context，无法读取本地消息历史")
            return []

        history_mgr = getattr(self._context, "message_history_manager", None)
        if not history_mgr:
            logger.warning("[Satori] context 中缺少 message_history_manager 服务")
            return []

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
                "[Satori] 从本地历史获取群 %s 消息 %d 条",
                group_id,
                len(messages),
            )
            return messages
        except Exception as exc:
            logger.error("[Satori] 读取本地消息历史失败: %s", exc, exc_info=True)
            return []

    async def _call_satori_api(
        self,
        method: str,
        path: str,
        data: dict[str, object] | None = None,
    ) -> object:
        """发送 Satori HTTP API 请求并返回响应。"""
        send_req = getattr(self.bot, "send_http_request", None)
        if callable(send_req):
            res = send_req(method, path, data)
            if isinstance(res, Awaitable):
                return await res
            return res
        return None

    def _convert_history_record(
        self, record: HistoryRecordProtocol, group_id: str
    ) -> UnifiedMessage | None:
        """将数据库历史记录转换为统一消息值对象。

        Args:
            record: AstrBot 原始历史记录对象。
            group_id: 群组或频道 ID。

        Returns:
            转换后的 UnifiedMessage 实例，失败时返回 None。
        """
        try:
            raw_content = getattr(record, "content", None)
            if not isinstance(raw_content, dict):
                return None
            content: dict[str, Any] = raw_content

            contents: list[MessageContent] = []
            text_parts: list[str] = []
            raw_parts = content.get("message", [])

            if isinstance(raw_parts, list):
                for part in raw_parts:
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
                                url=str(
                                    part.get("url", "") or part.get("file", "") or ""
                                ),
                            )
                        )
                    elif part_type == "at":
                        contents.append(
                            MessageContent(
                                type=MessageContentType.AT,
                                at_user_id=str(
                                    part.get("target_id", "")
                                    or part.get("qq", "")
                                    or part.get("name", "")
                                    or ""
                                ),
                            )
                        )
                    elif part_type == "file":
                        contents.append(
                            MessageContent(
                                type=MessageContentType.FILE,
                                text=str(part.get("name", "") or ""),
                                url=str(
                                    part.get("url", "") or part.get("file", "") or ""
                                ),
                                raw_data={"name": part.get("name", "")},
                            )
                        )
                    elif part_type in {"record", "audio", "voice"}:
                        contents.append(
                            MessageContent(
                                type=MessageContentType.VOICE,
                                url=str(
                                    part.get("url", "") or part.get("file", "") or ""
                                ),
                            )
                        )
                    elif part_type == "video":
                        contents.append(
                            MessageContent(
                                type=MessageContentType.VIDEO,
                                url=str(
                                    part.get("url", "") or part.get("file", "") or ""
                                ),
                            )
                        )
                    elif part_type == "reply":
                        contents.append(
                            MessageContent(
                                type=MessageContentType.REPLY,
                                raw_data={
                                    "reply_message_id": str(part.get("id", "") or "")
                                },
                            )
                        )

            raw_sender_id = getattr(record, "sender_id", None)
            sender_id = (
                str(raw_sender_id).strip() if raw_sender_id is not None else "unknown"
            )
            raw_name = getattr(record, "sender_name", None)
            sender_name = str(raw_name).strip() if raw_name else sender_id

            # 缓存发送者昵称资料
            self.remember_user_profile(sender_id, nickname=sender_name)

            raw_meta = content.get("_satori")
            metadata: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
            message_id = str(
                metadata.get("message_id")
                or content.get("message_id")
                or getattr(record, "id", "")
                or ""
            )
            if not message_id:
                message_id = f"local:{getattr(record, 'id', '') or ''}"

            timestamp = int(metadata.get("timestamp", 0) or 0)
            if timestamp <= 0:
                created_at = getattr(record, "created_at", None)
                timestamp = int(created_at.timestamp()) if created_at is not None else 0

            text_content = "".join(text_parts).strip()
            return UnifiedMessage(
                message_id=message_id,
                group_id=str(group_id),
                sender_id=sender_id,
                sender_name=sender_name,
                timestamp=timestamp,
                contents=tuple(contents),
                platform=self.platform_name,
                text_content=text_content,
            )
        except Exception as exc:
            logger.debug("[Satori] 转换历史记录异常: %s", exc)
            return None

    # ==================== IGroupInfoRepository 接口实现 ====================

    async def get_group_list(self) -> list[str]:
        """获取已记录的群组 ID 列表。

        Returns:
            群组 ID 字符串列表。
        """
        groups: list[str] = []
        if self._plugin_instance:
            registry = getattr(self._plugin_instance, "platform_group_registry", None)
            if registry is not None:
                get_all_group_ids = getattr(registry, "get_all_group_ids", None)
                if callable(get_all_group_ids):
                    try:
                        res = get_all_group_ids(self.platform_id)
                        kv_groups = await res if isinstance(res, Awaitable) else res
                        if isinstance(kv_groups, (list, tuple, set)):
                            groups.extend([str(gid) for gid in kv_groups])
                    except Exception as exc:
                        logger.warning("[Satori] 从群注册表读取群列表失败: %s", exc)

        return sorted(set(groups))

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        """通过 Satori HTTP API `/guild.get` 查询群组元数据。

        Args:
            group_id: 目标群组 ID。

        Returns:
            UnifiedGroup 值对象或默认回退群组信息。
        """
        target_id = str(group_id or "").strip()
        if not target_id:
            return None

        group_name = f"Satori Group {target_id}"
        member_count = 0

        try:
            guild_data = await self._call_satori_api(
                "POST", "/guild.get", {"guild_id": target_id}
            )
            if isinstance(guild_data, dict):
                group_name = str(guild_data.get("name") or group_name)
                member_count = int(guild_data.get("member_count", 0) or 0)
        except Exception as exc:
            logger.debug("[Satori] /guild.get 查询失败 %s: %s", target_id, exc)

        return UnifiedGroup(
            group_id=target_id,
            group_name=group_name,
            member_count=member_count,
            platform=self.platform_name,
        )

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        """获取群成员列表（契约别名）。"""
        return await self.get_group_members(group_id)

    async def get_group_member_list(self, group_id: str) -> list[UnifiedMember] | None:
        """获取群成员列表（PlatformAdapterProtocol 契约接口）。"""
        return await self.get_group_members(group_id)

    async def get_group_members(self, group_id: str) -> list[UnifiedMember]:
        """通过 Satori HTTP API `/guild.member.list` 分页获取全部群成员。

        Args:
            group_id: 目标群组 ID。

        Returns:
            统一成员对象列表。
        """
        target_id = str(group_id or "").strip()
        if not target_id:
            return []

        members: list[UnifiedMember] = []
        next_token: str | None = None
        seen_tokens: set[str] = set()

        try:
            while True:
                payload: dict[str, object] = {"guild_id": target_id}
                if next_token:
                    payload["next"] = next_token

                resp = await self._call_satori_api(
                    "POST", "/guild.member.list", payload
                )
                if not isinstance(resp, dict):
                    break

                data_list = resp.get("data")
                if not isinstance(data_list, list):
                    break

                for item in data_list:
                    if not isinstance(item, dict):
                        continue
                    raw_u = item.get("user")
                    user: dict[str, Any] = raw_u if isinstance(raw_u, dict) else {}
                    user_id = str(user.get("id") or item.get("user_id") or "").strip()
                    if not user_id:
                        continue

                    nickname = (
                        item.get("nick")
                        or user.get("nick")
                        or user.get("name")
                        or user_id
                    )
                    avatar_url = user.get("avatar") or item.get("avatar")

                    member_obj = UnifiedMember(
                        user_id=user_id,
                        nickname=str(nickname),
                        avatar_url=str(avatar_url) if avatar_url else None,
                    )
                    members.append(member_obj)
                    self.remember_user_profile(
                        user_id,
                        nickname=str(nickname),
                        avatar_url=str(avatar_url) if avatar_url else None,
                    )

                next_token_val = resp.get("next")
                next_token = str(next_token_val) if next_token_val else None
                if not next_token or next_token in seen_tokens:
                    break
                seen_tokens.add(next_token)

        except Exception as exc:
            logger.warning("[Satori] 获取群 %s 成员列表失败: %s", target_id, exc)

        return members

    async def get_member_info(
        self, group_id: str, user_id: str
    ) -> UnifiedMember | None:
        """获取单个群成员的详细资料。

        优先读取内存缓存，缺失时调用 Satori API `/guild.member.get`。

        Args:
            group_id: 目标群组 ID。
            user_id: 目标用户 ID。

        Returns:
            UnifiedMember 实例或 None。
        """
        target_uid = str(user_id or "").strip()
        if not target_uid:
            return None

        cached = self._member_profiles.get(target_uid)
        nickname = cached.get("nickname") if cached else None
        avatar_url = cached.get("avatar_url") if cached else None

        if not nickname:
            try:
                resp = await self._call_satori_api(
                    "POST",
                    "/guild.member.get",
                    {"guild_id": str(group_id), "user_id": target_uid},
                )
                if isinstance(resp, dict):
                    raw_u = resp.get("user")
                    user: dict[str, Any] = raw_u if isinstance(raw_u, dict) else {}
                    nickname = (
                        resp.get("nick")
                        or user.get("nick")
                        or user.get("name")
                        or target_uid
                    )
                    avatar_url = user.get("avatar") or resp.get("avatar") or avatar_url
            except Exception:
                pass

        return UnifiedMember(
            user_id=target_uid,
            nickname=str(nickname or target_uid),
            avatar_url=str(avatar_url) if avatar_url else None,
        )

    # ==================== IAvatarRepository 接口实现 ====================

    async def get_user_avatar_url(self, user_id: str, size: int = 40) -> str | None:
        """获取用户头像 URL。

        支持内存缓存、数字 QQ 号 CDN 规则以及 Satori `/user.get` API 查询。

        Args:
            user_id: 目标用户 ID。
            size: 目标尺寸像素。

        Returns:
            头像 URL 字符串或 None。
        """
        target_uid = str(user_id or "").strip()
        if not target_uid:
            return None

        # 1. 优先使用已缓存的头像链接
        cached = self._member_profiles.get(target_uid)
        if cached and cached.get("avatar_url"):
            return cached["avatar_url"]

        # 2. 纯数字账号（Chronocat/Satori QQ 场景）走 QQ 头像 CDN 兜底
        if target_uid.isdigit():
            return f"https://q1.qlogo.cn/g?b=qq&nk={target_uid}&s={size}"

        # 3. 调用 Satori `/user.get` API 查询
        try:
            resp = await self._call_satori_api(
                "POST", "/user.get", {"user_id": target_uid}
            )
            if isinstance(resp, dict) and resp.get("avatar"):
                avatar = str(resp["avatar"])
                self.remember_user_profile(target_uid, avatar_url=avatar)
                return avatar
        except Exception:
            pass

        return None

    async def get_user_avatar_data(self, user_id: str, size: int = 100) -> str | None:
        """获取用户头像的 Base64 Data URI。

        Args:
            user_id: 目标用户 ID。
            size: 目标尺寸像素。

        Returns:
            Data URI 字符串或 None。
        """
        avatar_url = await self.get_user_avatar_url(user_id, size=size)
        if avatar_url and avatar_url.startswith("data:"):
            return avatar_url
        return None

    async def batch_get_avatar_urls(
        self, user_ids: list[str], size: int = 100
    ) -> dict[str, str | None]:
        """批量获取多个用户的头像链接。

        Args:
            user_ids: 用户 ID 列表。
            size: 目标尺寸像素。

        Returns:
            用户 ID 到头像链接的映射字典。
        """
        result: dict[str, str | None] = {}
        for uid in user_ids:
            result[uid] = await self.get_user_avatar_url(uid, size=size)
        return result

    async def get_group_avatar_url(self, group_id: str, size: int = 100) -> str | None:
        """获取群组头像链接。

        Args:
            group_id: 目标群组 ID。
            size: 目标尺寸像素。

        Returns:
            群头像链接或 None。
        """
        target_gid = str(group_id or "").strip()
        if not target_gid:
            return None

        # 纯数字群号走 QQ 群头像 CDN
        if target_gid.isdigit():
            return f"https://p.qlogo.cn/gh/{target_gid}/{target_gid}/{size}"

        # 调用 Satori API `/guild.get` 获取 avatar 字段
        try:
            resp = await self._call_satori_api(
                "POST", "/guild.get", {"guild_id": target_gid}
            )
            if isinstance(resp, dict) and resp.get("avatar"):
                return str(resp["avatar"])
        except Exception:
            pass

        return None

    # ==================== IMessageSender 接口实现 ====================

    async def send_text(
        self, group_id: str, text: str, reply_to: str | None = None
    ) -> bool:
        """发送纯文本消息（支持引用回复）。"""
        content = text
        if reply_to:
            content = f'<quote id="{html.escape(reply_to)}"/>{content}'
        return await self.send_text_message(group_id, content)

    async def send_text_message(self, group_id: str, text: str) -> bool:
        """向指定群组或频道发送纯文本消息。

        Args:
            group_id: 目标频道或群组 ID。
            text: 待发送的文本内容。

        Returns:
            发送成功返回 True，否则返回 False。
        """
        target_id = str(group_id or "").strip()
        if not target_id or not text:
            return False

        try:
            escaped_text = html.escape(text) if not text.startswith("<quote") else text
            resp = await self._call_satori_api(
                "POST",
                "/message.create",
                {"channel_id": target_id, "content": escaped_text},
            )
            return bool(resp)
        except Exception as exc:
            logger.error("[Satori] 发送文本消息失败 %s: %s", target_id, exc)
            return False

    async def send_image(
        self, group_id: str, image_path: str, caption: str = ""
    ) -> bool:
        """发送图片消息（契约接口）。"""
        return await self.send_image_message(group_id, image_path, text=caption)

    async def send_image_message(
        self, group_id: str, image_url: str, text: str = ""
    ) -> bool:
        """发送图片消息（支持本地文件路径 Base64 编码、Data URI 与网络图片 URL）。

        Args:
            group_id: 目标频道或群组 ID。
            image_url: 图片路径或 URL。
            text: 可选的附带描述文本。

        Returns:
            发送成功返回 True，否则返回 False。
        """
        target_id = str(group_id or "").strip()
        if not target_id or not image_url:
            return False

        resolved_src = self._resolve_image_src(image_url)
        content_parts = [f'<img src="{resolved_src}"/>']
        if text:
            content_parts.append(html.escape(text))

        content = "".join(content_parts)
        try:
            resp = await self._call_satori_api(
                "POST",
                "/message.create",
                {"channel_id": target_id, "content": content},
            )
            return bool(resp)
        except Exception as exc:
            logger.error("[Satori] 发送图片消息失败 %s: %s", target_id, exc)
            return False

    async def send_forward_msg(self, group_id: str, nodes: list[dict]) -> bool:
        """发送转发消息节点。

        Args:
            group_id: 目标群组 ID。
            nodes: 转发节点字典列表。

        Returns:
            发送成功返回 True。
        """
        target_id = str(group_id or "").strip()
        if not target_id or not nodes:
            return False

        parts: list[str] = []
        for node in nodes:
            name = str(node.get("name") or node.get("sender_name") or "转发消息")
            content = str(node.get("content") or node.get("message") or "")
            parts.append(f"<b>{html.escape(name)}</b>: {html.escape(content)}")

        combined = "<br/>".join(parts)
        try:
            resp = await self._call_satori_api(
                "POST",
                "/message.create",
                {"channel_id": target_id, "content": combined},
            )
            return bool(resp)
        except Exception as exc:
            logger.error("[Satori] 发送合并转发消息失败 %s: %s", target_id, exc)
            return False

    async def send_report_image(
        self,
        group_id: str,
        image_url: str,
        text: str = "",
        trace_id: str | None = None,
    ) -> bool:
        """发送日常分析报告长图。

        Args:
            group_id: 目标群组 ID。
            image_url: 报告图片路径或 URL。
            text: 附加说明文字。
            trace_id: 可选的追踪 ID。

        Returns:
            发送成功返回 True。
        """
        return await self.send_image_message(group_id, image_url, text)

    async def send_file(
        self, group_id: str, file_path: str, filename: str | None = None
    ) -> bool:
        """发送文件消息（契约接口）。"""
        return await self.send_file_message(
            group_id, file_path, file_name=filename or ""
        )

    async def send_file_message(
        self, group_id: str, file_path: str, file_name: str = ""
    ) -> bool:
        """发送文件消息。

        Args:
            group_id: 目标群组 ID。
            file_path: 文件本地路径或 URL。
            file_name: 可选的文件显示名称。

        Returns:
            发送成功返回 True。
        """
        target_id = str(group_id or "").strip()
        if not target_id or not file_path:
            return False

        resolved_src = self._resolve_image_src(file_path)
        display_name = file_name or Path(file_path).name
        content = f'<file src="{resolved_src}" name="{html.escape(display_name)}"/>'

        try:
            resp = await self._call_satori_api(
                "POST",
                "/message.create",
                {"channel_id": target_id, "content": content},
            )
            return bool(resp)
        except Exception as exc:
            logger.error("[Satori] 发送文件失败 %s: %s", target_id, exc)
            return False

    def convert_to_raw_format(
        self, messages: list[UnifiedMessage]
    ) -> list[dict[str, object]]:
        """将 UnifiedMessage 列表转换为分析流水线使用的标准原始字典列表。

        Args:
            messages: 统一消息对象列表。

        Returns:
            标准字典格式的消息记录列表。
        """
        raw_list: list[dict[str, object]] = []
        for msg in messages:
            raw_list.append(
                {
                    "message_id": msg.message_id,
                    "time": msg.timestamp,
                    "sender": {
                        "user_id": msg.sender_id,
                        "nickname": msg.sender_name,
                        "card": msg.sender_name,
                    },
                    "message": msg.text_content,
                    "raw_message": msg.text_content,
                    "group_id": msg.group_id,
                }
            )
        return raw_list

    @staticmethod
    def _resolve_image_src(image_ref: str) -> str:
        """将本地文件路径、file:// 链接或网络 URL 解析为合法的 Satori src 属性。

        Args:
            image_ref: 本地路径、Data URI 或 HTTP 链接。

        Returns:
            编码后的 Data URL 或标准网络 URL。
        """
        ref_str = str(image_ref).strip()
        if ref_str.startswith(("http://", "https://", "data:")):
            return ref_str

        if ref_str.startswith("file:///"):
            ref_str = ref_str[8:]
        elif ref_str.startswith("file://"):
            ref_str = ref_str[7:]

        local_path = Path(ref_str)
        if local_path.is_file():
            try:
                mime_type, _ = mimetypes.guess_type(str(local_path))
                if not mime_type:
                    mime_type = "image/png"
                data = local_path.read_bytes()
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:{mime_type};base64,{b64}"
            except Exception as exc:
                logger.debug("[Satori] 本地文件转 Base64 失败: %s", exc)

        return ref_str
