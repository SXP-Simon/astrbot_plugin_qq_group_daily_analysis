"""统一消息快照的读取边界，兼容旧字段但不将它们传入领域。"""

from ...domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ...shared.type_guards import is_object_list, is_string_mapping
from ..platform.message_normalization import is_image_sticker


def restore_unified_messages(
    unified_messages_raw: object, group_id: str
) -> list[UnifiedMessage]:
    """还原当前和旧版消息快照。

    Args:
        unified_messages_raw: JSON 消息列表或内存中的统一消息列表。
        group_id: 旧快照缺少会话 ID 时的回退值。

    Returns:
        保留消息段与关系的统一消息，不携带原始协议字典。
    """
    unified_messages: list[UnifiedMessage] = []
    if is_object_list(unified_messages_raw):
        for message in unified_messages_raw:
            if isinstance(message, UnifiedMessage):
                unified_messages.append(message)
            elif is_string_mapping(message):
                # 恢复消息段及关系，确保续跑与首次分析读取相同的信息。
                contents: list[MessageContent] = []
                reply_to_id = str(message.get("reply_to_id") or "")
                saved_contents = message.get("contents")
                if is_object_list(saved_contents):
                    for part in saved_contents:
                        if not is_string_mapping(part):
                            continue
                        try:
                            content_type = MessageContentType(part.get("type"))
                        except ValueError:
                            content_type = MessageContentType.UNKNOWN
                        if content_type == MessageContentType.REPLY and not reply_to_id:
                            raw_reply = part.get("raw_data")
                            if is_string_mapping(raw_reply):
                                reply_to_id = str(
                                    raw_reply.get("reply_id")
                                    or raw_reply.get("reply_message_id")
                                    or ""
                                )
                        old_data = part.get("raw_data")
                        old_fields = old_data if is_string_mapping(old_data) else {}
                        text = str(part.get("text") or "")
                        if content_type == MessageContentType.FILE and not text:
                            text = str(
                                old_fields.get("filename")
                                or old_fields.get("name")
                                or ""
                            )
                        contents.append(
                            MessageContent(
                                type=content_type,
                                text=text,
                                url=str(part.get("url") or ""),
                                emoji_id=str(
                                    part.get("emoji_id")
                                    or old_fields.get("sticker_id")
                                    or ""
                                ),
                                emoji_name=str(
                                    part.get("emoji_name")
                                    or old_fields.get("sticker_name")
                                    or ""
                                ),
                                at_user_id=str(part.get("at_user_id") or ""),
                                is_sticker=is_image_sticker(part)
                                if isinstance(part.get("is_sticker"), bool)
                                else is_image_sticker(part.get("raw_data")),
                            )
                        )
                timestamp = message.get("timestamp", 0)
                try:
                    restored_timestamp = (
                        int(timestamp)
                        if isinstance(timestamp, (int, float, str))
                        else 0
                    )
                except (ValueError, OverflowError):
                    # 时间戳不参与文本续跑，旧值无效时保留消息正文并使用零值。
                    restored_timestamp = 0
                unified_messages.append(
                    UnifiedMessage(
                        message_id=str(message.get("message_id", "")),
                        sender_id=str(message.get("sender_id", "")),
                        sender_name=str(message.get("sender_name", "")),
                        group_id=str(message.get("group_id", group_id)),
                        text_content=str(message.get("text_content", "")),
                        timestamp=restored_timestamp,
                        contents=tuple(contents),
                        platform=str(message.get("platform") or "unknown"),
                        reply_to_id=reply_to_id or None,
                        sender_card=str(message["sender_card"])
                        if message.get("sender_card")
                        else None,
                    )
                )

    return unified_messages
