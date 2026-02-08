"""
消息转换器 - 连接原始平台消息和 UnifiedMessage

该模块通过在原始平台消息格式和新的 UnifiedMessage 格式之间进行转换，
提供向后兼容性。
"""

from ..domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)


class MessageConverter:
    """
    在原始平台消息和 UnifiedMessage 格式之间进行转换。

    这提供了一个迁移路径：现有代码可以继续使用原始字典，
    而新代码使用 UnifiedMessage。
    """

    @staticmethod
    def from_onebot_message(raw_msg: dict, group_id: str) -> UnifiedMessage | None:
        """
        将 OneBot v11 原始消息转换为 UnifiedMessage。

        Args:
            raw_msg: 来自 OneBot API 的原始消息字典
            group_id: 群组 ID

        Returns:
            UnifiedMessage 或 None（如果转换失败）
        """
        try:
            sender = raw_msg.get("sender", {})
            message_chain = raw_msg.get("message", [])

            # 处理字符串消息格式
            if isinstance(message_chain, str):
                message_chain = [{"type": "text", "data": {"text": message_chain}}]

            contents = []
            text_parts = []

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
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE,
                            url=seg_data.get("url", seg_data.get("file", "")),
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

            # 从内容中提取 reply_to
            reply_to = None
            for c in contents:
                if c.type == MessageContentType.REPLY and c.raw_data:
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

        except Exception:
            return None

    @staticmethod
    def to_onebot_message(unified: UnifiedMessage) -> dict:
        """
        将 UnifiedMessage 转换回 OneBot v11 原始格式。

        用于与期望原始字典的现有代码向后兼容。
        """
        message_chain = []

        for content in unified.contents:
            if content.type == MessageContentType.TEXT:
                message_chain.append({"type": "text", "data": {"text": content.text}})
            elif content.type == MessageContentType.IMAGE:
                message_chain.append({"type": "image", "data": {"url": content.url}})
            elif content.type == MessageContentType.AT:
                message_chain.append({"type": "at", "data": {"qq": content.at_user_id}})
            elif content.type == MessageContentType.EMOJI:
                face_type = (
                    content.raw_data.get("face_type", "face")
                    if content.raw_data
                    else "face"
                )
                message_chain.append(
                    {"type": face_type, "data": {"id": content.emoji_id}}
                )
            elif content.type == MessageContentType.REPLY:
                reply_id = (
                    content.raw_data.get("reply_id", "") if content.raw_data else ""
                )
                message_chain.append({"type": "reply", "data": {"id": reply_id}})
            elif content.type == MessageContentType.VOICE:
                message_chain.append({"type": "record", "data": {"url": content.url}})
            elif content.type == MessageContentType.VIDEO:
                message_chain.append({"type": "video", "data": {"url": content.url}})

        # 确保填充发送者字段，即使原始数据中缺失
        sender_data = {
            "user_id": unified.sender_id,
            "nickname": unified.sender_name,
            "card": unified.sender_card or "",
        }

        return {
            "message_id": unified.message_id,
            "sender": sender_data,
            "group_id": unified.group_id,
            "message": message_chain,
            "time": unified.timestamp,
            # 添加这些辅助字段，以便旧分析器可以直接使用
            "raw_message": unified.text_content,
            "user_id": unified.sender_id,
        }

    @staticmethod
    def batch_from_onebot(
        raw_messages: list[dict], group_id: str
    ) -> list[UnifiedMessage]:
        """将一批 OneBot 消息转换为 UnifiedMessage 列表。"""
        result = []
        for raw_msg in raw_messages:
            unified = MessageConverter.from_onebot_message(raw_msg, group_id)
            if unified:
                result.append(unified)
        return result

    @staticmethod
    def batch_to_onebot(unified_messages: list[UnifiedMessage]) -> list[dict]:
        """将一批 UnifiedMessage 转换为 OneBot 原始格式。"""
        return [MessageConverter.to_onebot_message(msg) for msg in unified_messages]

    @staticmethod
    def unified_to_analysis_text(messages: list[UnifiedMessage]) -> str:
        """
        将 UnifiedMessage 列表转换为 LLM 分析文本格式。

        这是现有 LLM 分析器期望的格式。
        """
        lines = []
        for msg in messages:
            if msg.has_text():
                lines.append(msg.to_analysis_format())
        return "\n".join(lines)
