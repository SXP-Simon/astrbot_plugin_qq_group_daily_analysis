"""
Telegram 消息转换器 (Telegram Message Converter)

负责 Telegram 数据库历史记录、统一领域消息 (UnifiedMessage) 与 OneBot 兼容格式之间的双向转换，
并提供占位昵称自愈、群组话题 ID 解析以及转发消息文本排版功能。
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import replace
from typing import Any

from ....domain.value_objects.unified_group import UnifiedMember
from ....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ....utils.logger import logger


class TelegramMessageConverter:
    """Telegram 消息转换与昵称自愈器。"""

    @staticmethod
    def parse_group_id(group_id: str) -> tuple[str, str | None]:
        """解析群组 ID 与话题 ID。

        Telegram 话题群的 ID 格式约定为: "chat_id#thread_id"。

        Args:
            group_id: 包含或不包含话题后缀的群聊 ID 字符串。

        Returns:
            tuple[str, str | None]: (chat_id, message_thread_id)
        """
        if "#" in group_id:
            parts = group_id.split("#", 1)
            return parts[0], parts[1]
        return group_id, None

    @staticmethod
    def is_placeholder_sender_name(name: str | None, sender_id: str | None) -> bool:
        """判断发送者昵称是否属于无效的占位值。

        Args:
            name: 发送者昵称。
            sender_id: 发送者用户 ID。

        Returns:
            bool: 若为占位昵称则返回 True，否则返回 False。
        """
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized.lower() in {"unknown", "none", "null", "nil", "undefined"}:
            return True
        if sender_id and normalized == str(sender_id).strip():
            return True
        return False

    @classmethod
    async def fix_sender_name_if_needed(
        cls,
        group_id: str,
        msg: UnifiedMessage,
        sender_name_cache: dict[str, str],
        member_fetcher: Callable[[str, str], Coroutine[Any, Any, UnifiedMember | None]],
    ) -> UnifiedMessage:
        """若发送者昵称为占位值，尝试通过成员查询回调自愈修复。

        说明：
        - 兼容历史脏数据（sender_name 记录为 user_id 或 Unknown）；
        - 使用 sender_id 级缓存，避免重复触发 API 请求。

        Args:
            group_id: 当前群组 ID。
            msg: 待检查的统一消息对象。
            sender_name_cache: 跨消息复用的发送者昵称缓存字典。
            member_fetcher: 异步成员信息查询回调函数。

        Returns:
            UnifiedMessage: 修复后的新消息对象（若无需修复则返回原对象）。
        """
        if not cls.is_placeholder_sender_name(msg.sender_name, msg.sender_id):
            return msg

        sender_id = str(msg.sender_id)
        if sender_id in sender_name_cache:
            cached_name = sender_name_cache[sender_id]
            if cached_name == msg.sender_name:
                return msg
            return replace(msg, sender_name=cached_name)

        resolved_name = msg.sender_name
        try:
            member = await member_fetcher(group_id, sender_id)
            if member:
                candidate = str(member.nickname or "").strip()
                if cls.is_placeholder_sender_name(candidate, sender_id):
                    candidate = str(member.card or "").strip()
                if not cls.is_placeholder_sender_name(candidate, sender_id):
                    resolved_name = candidate
        except Exception as e:
            logger.debug(f"[Telegram] 修复 sender_name 失败 (uid={sender_id}): {e}")

        sender_name_cache[sender_id] = resolved_name
        if resolved_name == msg.sender_name:
            return msg
        return replace(msg, sender_name=resolved_name)

    @staticmethod
    def to_unified_message(record: Any, group_id: str) -> UnifiedMessage | None:
        """将数据库历史消息记录转换为 UnifiedMessage 领域值对象。

        Args:
            record: 从 message_history_manager 查询出的单条数据库历史记录。
            group_id: 所属群聊 ID。

        Returns:
            UnifiedMessage | None: 转换成功返回领域消息对象，失败返回 None。
        """
        try:
            content = record.content
            if not content:
                return None

            # 提取消息内容
            message_parts = content.get("message", [])
            text_content = ""
            contents: list[MessageContent] = []

            for part in message_parts:
                if isinstance(part, dict):
                    part_type = part.get("type", "")
                    if part_type in ("plain", "text"):
                        text = part.get("text", "")
                        text_content += text
                        contents.append(
                            MessageContent(
                                type=MessageContentType.TEXT,
                                text=text,
                            )
                        )
                    elif part_type == "image":
                        contents.append(
                            MessageContent(
                                type=MessageContentType.IMAGE,
                                url=part.get("url", "")
                                or part.get("attachment_id", ""),
                            )
                        )
                    elif part_type == "at":
                        target_id = (
                            part.get("target_id", "")
                            or part.get("qq", "")
                            or part.get("at_user_id", "")
                        )
                        contents.append(
                            MessageContent(
                                type=MessageContentType.AT,
                                at_user_id=str(target_id),
                            )
                        )

            if not contents:
                contents.append(
                    MessageContent(
                        type=MessageContentType.TEXT,
                        text=text_content,
                    )
                )

            sender_id = str(record.sender_id or "")
            sender_name = str(record.sender_name or "").strip() or "Unknown"

            return UnifiedMessage(
                message_id=str(record.id),
                sender_id=sender_id,
                sender_name=sender_name,
                sender_card=None,
                group_id=group_id,
                text_content=text_content,
                contents=tuple(contents),
                timestamp=int(record.created_at.timestamp()),
                platform="telegram",
                reply_to_id=None,
            )

        except Exception as e:
            logger.debug(f"[Telegram] 转换历史记录失败: {e}")
            return None

    @staticmethod
    def to_raw_format(messages: list[UnifiedMessage]) -> list[dict]:
        """将统一消息列表转换为 OneBot 兼容的原生消息字典列表。

        用于向后兼容现有分析管线与数据序列化。

        Args:
            messages: 统一消息列表。

        Returns:
            list[dict]: OneBot 兼容格式的原始消息字典列表。
        """
        result: list[dict] = []
        for msg in messages:
            raw: dict[str, Any] = {
                "message_id": msg.message_id,
                "group_id": msg.group_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card or "",
                },
                "message": [],
                "user_id": msg.sender_id,
            }

            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    raw["message"].append(
                        {"type": "text", "data": {"text": content.text or ""}}
                    )
                elif content.type == MessageContentType.IMAGE:
                    raw["message"].append(
                        {"type": "image", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.AT:
                    raw["message"].append(
                        {"type": "at", "data": {"qq": content.at_user_id or ""}}
                    )

            result.append(raw)

        return result

    @staticmethod
    def format_forward_nodes_to_text(nodes: list[dict]) -> str:
        """将合并转发节点列表排版为 Markdown 格式的文本内容。

        Args:
            nodes: 转发节点字典列表。

        Returns:
            str: 格式化后的纯文本消息。
        """
        if not nodes:
            return ""

        lines = ["📊 **分析报告**\n"]
        for node in nodes:
            data = node.get("data", node)
            name = data.get("name", "AstrBot")
            content = data.get("content", "")
            if isinstance(content, list):
                text_parts: list[str] = []
                for seg in content:
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        text_parts.append(seg.get("data", {}).get("text", ""))
                content = "".join(text_parts)
            lines.append(f"**[{name}]**\n{content}\n")

        return "\n".join(lines)
