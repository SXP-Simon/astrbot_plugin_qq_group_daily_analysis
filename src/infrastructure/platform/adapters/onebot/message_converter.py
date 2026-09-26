"""
OneBot v11 消息与领域模型转换器 (OneBot Message Converter)

负责 OneBot 原始消息字典（包含 CQ 码与分段 Segment 链）与统一领域消息对象 (UnifiedMessage) 之间的双向转换。
"""

from __future__ import annotations

from .....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from .....utils.logger import logger


class OneBotMessageConverter:
    """OneBot v11 消息双向协议转换器。"""

    @staticmethod
    def to_unified_message(raw_msg: dict, group_id: str) -> UnifiedMessage | None:
        """将 OneBot 原生原始消息字典转换为 UnifiedMessage 领域值对象。

        Args:
            raw_msg: OneBot API 返回的单条原生消息字典。
            group_id: 当前群聊 ID 字符串。

        Returns:
            UnifiedMessage | None: 解析成功返回统一领域消息，解析失败返回 None。
        """
        try:
            sender = raw_msg.get("sender", {})
            message_chain = raw_msg.get("message", [])

            # 兼容性处理：如果是字符串格式的 message，转换为列表格式
            if isinstance(message_chain, str):
                message_chain = [{"type": "text", "data": {"text": message_chain}}]

            contents: list[MessageContent] = []
            text_parts: list[str] = []

            for seg in message_chain:
                seg_type = seg.get("type", "")
                seg_data = seg.get("data", {})

                if seg_type == "text":
                    text = seg_data.get("text", "")
                    text_parts.append(text)
                    contents.append(
                        MessageContent(type=MessageContentType.TEXT, text=text)
                    )

                elif seg_type == "image":
                    # QQ 平台: subType=1 表示表情包，通过 raw_data 传递给下游统计
                    sub_type = seg_data.get("subType", seg_data.get("sub_type"))
                    try:
                        is_sticker = int(sub_type) == 1
                    except (TypeError, ValueError):
                        is_sticker = False
                    raw_data: dict[str, object] = {
                        "summary": seg_data.get("summary", "")
                    }
                    if sub_type is not None:
                        try:
                            raw_data["sub_type"] = int(sub_type)
                        except (TypeError, ValueError):
                            pass
                    contents.append(
                        MessageContent(
                            type=MessageContentType.EMOJI
                            if is_sticker
                            else MessageContentType.IMAGE,
                            url=seg_data.get("url", seg_data.get("file", "")),
                            raw_data=raw_data,
                        )
                    )

                elif seg_type == "at":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.AT,
                            at_user_id=str(seg_data.get("qq", "")),
                        )
                    )

                elif seg_type in ("face", "mface", "bface", "sface"):
                    contents.append(
                        MessageContent(
                            type=MessageContentType.EMOJI,
                            emoji_id=str(seg_data.get("id", "")),
                            raw_data={"face_type": seg_type},
                        )
                    )

                elif seg_type == "reply":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.REPLY,
                            raw_data={"reply_id": seg_data.get("id", "")},
                        )
                    )

                elif seg_type == "forward":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.FORWARD, raw_data=seg_data
                        )
                    )

                elif seg_type == "record":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VOICE,
                            url=seg_data.get("url", seg_data.get("file", "")),
                        )
                    )

                elif seg_type == "video":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VIDEO,
                            url=seg_data.get("url", seg_data.get("file", "")),
                        )
                    )

                else:
                    contents.append(
                        MessageContent(type=MessageContentType.UNKNOWN, raw_data=seg)
                    )

            # 提取回复 ID
            reply_to = None
            for c in contents:
                if c.type == MessageContentType.REPLY and isinstance(c.raw_data, dict):
                    reply_to = str(c.raw_data.get("reply_id", ""))
                    break

            return UnifiedMessage(
                message_id=str(raw_msg.get("message_id", "")),
                sender_id=str(sender.get("user_id", "")),
                sender_name=sender.get("nickname", ""),
                sender_card=sender.get("card", "") or None,
                group_id=group_id,
                text_content="".join(text_parts),
                contents=tuple(contents),
                timestamp=raw_msg.get("time", 0),
                platform="onebot",
                reply_to_id=reply_to,
            )

        except Exception as e:
            logger.debug(f"OneBot 消息转换失败: {e}")
            return None

    @staticmethod
    def to_raw_messages(messages: list[UnifiedMessage]) -> list[dict]:
        """将 UnifiedMessage 领域消息列表逆向转换为 OneBot 原生字典格式。

        Args:
            messages: 统一消息值对象列表。

        Returns:
            list[dict]: 符合 OneBot v11 规范的消息字典列表。
        """
        raw_messages: list[dict] = []
        for msg in messages:
            message_chain: list[dict[str, object]] = []
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    message_chain.append(
                        {"type": "text", "data": {"text": content.text or ""}}
                    )
                elif content.type == MessageContentType.IMAGE:
                    message_chain.append(
                        {"type": "image", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.AT:
                    message_chain.append(
                        {"type": "at", "data": {"qq": content.at_user_id or ""}}
                    )
                elif content.type == MessageContentType.EMOJI:
                    face_type = (
                        str(content.raw_data.get("face_type", "face"))
                        if isinstance(content.raw_data, dict)
                        else "face"
                    )
                    message_chain.append(
                        {"type": face_type, "data": {"id": content.emoji_id or ""}}
                    )
                elif content.type == MessageContentType.REPLY:
                    reply_id = (
                        str(content.raw_data.get("reply_id", ""))
                        if isinstance(content.raw_data, dict)
                        else ""
                    )
                    message_chain.append({"type": "reply", "data": {"id": reply_id}})
                elif content.type == MessageContentType.FORWARD:
                    fwd_data = (
                        content.raw_data if isinstance(content.raw_data, dict) else {}
                    )
                    message_chain.append({"type": "forward", "data": fwd_data})
                elif content.type == MessageContentType.VOICE:
                    message_chain.append(
                        {"type": "record", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.VIDEO:
                    message_chain.append(
                        {"type": "video", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.UNKNOWN and isinstance(
                    content.raw_data, dict
                ):
                    message_chain.append(content.raw_data)

            raw_msg = {
                "message_id": msg.message_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card or "",
                },
                "message": message_chain,
                "group_id": msg.group_id,
                "raw_message": msg.text_content,
                "user_id": msg.sender_id,
            }
            raw_messages.append(raw_msg)

        return raw_messages
