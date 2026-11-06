"""
OneBot v11 消息与领域模型转换器 (OneBot Message Converter)

负责 OneBot 原始消息字典（包含 CQ 码与分段 Segment 链）与统一领域消息对象 (UnifiedMessage) 之间的转换。
"""

from __future__ import annotations

from .....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from .....shared.type_guards import is_object_list, is_string_mapping
from .....utils.logger import logger
from ...message_normalization import is_image_sticker


class OneBotMessageConverter:
    """OneBot v11 消息协议转换器。"""

    @staticmethod
    def to_unified_message(
        raw_msg: dict[str, object], group_id: str
    ) -> UnifiedMessage | None:
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
            if not is_string_mapping(sender):
                return None

            # 兼容性处理：如果是字符串格式的 message，转换为列表格式
            if isinstance(message_chain, str):
                message_chain = [{"type": "text", "data": {"text": message_chain}}]
            if not is_object_list(message_chain):
                return None

            contents: list[MessageContent] = []
            text_parts: list[str] = []
            reply_to: str | None = None

            for seg in message_chain:
                if not is_string_mapping(seg):
                    return None
                seg_type = seg.get("type", "")
                seg_data = seg.get("data", {})
                if not is_string_mapping(seg_data):
                    return None

                if seg_type == "text":
                    text = str(seg_data.get("text", ""))
                    text_parts.append(text)
                    contents.append(
                        MessageContent(type=MessageContentType.TEXT, text=text)
                    )

                elif seg_type == "image":
                    is_sticker = is_image_sticker(seg_data)
                    contents.append(
                        MessageContent(
                            type=MessageContentType.EMOJI
                            if str(seg_data.get("subType", seg_data.get("sub_type")))
                            == "1"
                            else MessageContentType.IMAGE,
                            is_sticker=is_sticker,
                            url=str(seg_data.get("url", seg_data.get("file", ""))),
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
                        )
                    )

                elif seg_type == "reply":
                    reply_to = reply_to or str(seg_data.get("id", "")) or None
                    contents.append(
                        MessageContent(
                            type=MessageContentType.REPLY,
                        )
                    )

                elif seg_type == "forward":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.FORWARD,
                        )
                    )

                elif seg_type == "record":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VOICE,
                            url=str(seg_data.get("url", seg_data.get("file", ""))),
                        )
                    )

                elif seg_type == "video":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VIDEO,
                            url=str(seg_data.get("url", seg_data.get("file", ""))),
                        )
                    )

                else:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.UNKNOWN,
                        )
                    )

            timestamp = raw_msg.get("time", 0)
            if not isinstance(timestamp, (str, int, float)):
                return None
            return UnifiedMessage(
                message_id=str(raw_msg.get("message_id", "")),
                sender_id=str(sender.get("user_id", "")),
                sender_name=str(sender.get("nickname", "")),
                sender_card=str(sender.get("card") or "") or None,
                group_id=group_id,
                text_content="".join(text_parts),
                contents=tuple(contents),
                timestamp=int(timestamp),
                platform="onebot",
                reply_to_id=reply_to,
            )

        except Exception as e:
            logger.debug(f"OneBot 消息转换失败: {e}")
            return None
