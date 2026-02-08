"""
Message Converter - Bridges raw platform messages to UnifiedMessage

This module provides backward compatibility by converting between
raw platform message formats and the new UnifiedMessage format.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from ..domain.value_objects.unified_message import (
    UnifiedMessage,
    MessageContent,
    MessageContentType,
)


class MessageConverter:
    """
    Converts between raw platform messages and UnifiedMessage format.
    
    This provides a migration path: existing code can continue using
    raw dicts while new code uses UnifiedMessage.
    """

    @staticmethod
    def from_onebot_message(raw_msg: dict, group_id: str) -> Optional[UnifiedMessage]:
        """
        Convert OneBot v11 raw message to UnifiedMessage.
        
        Args:
            raw_msg: Raw message dict from OneBot API
            group_id: Group ID
            
        Returns:
            UnifiedMessage or None if conversion fails
        """
        try:
            sender = raw_msg.get("sender", {})
            message_chain = raw_msg.get("message", [])

            # Handle string message format
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
                    contents.append(MessageContent(type=MessageContentType.TEXT, text=text))

                elif seg_type == "image":
                    contents.append(MessageContent(
                        type=MessageContentType.IMAGE,
                        url=seg_data.get("url", seg_data.get("file", ""))
                    ))

                elif seg_type == "at":
                    contents.append(MessageContent(
                        type=MessageContentType.AT,
                        at_user_id=str(seg_data.get("qq", ""))
                    ))

                elif seg_type in ("face", "mface", "bface", "sface"):
                    contents.append(MessageContent(
                        type=MessageContentType.EMOJI,
                        emoji_id=str(seg_data.get("id", "")),
                        raw_data={"face_type": seg_type}
                    ))

                elif seg_type == "reply":
                    contents.append(MessageContent(
                        type=MessageContentType.REPLY,
                        raw_data={"reply_id": seg_data.get("id", "")}
                    ))

                elif seg_type == "forward":
                    contents.append(MessageContent(
                        type=MessageContentType.FORWARD,
                        raw_data=seg_data
                    ))

                elif seg_type == "record":
                    contents.append(MessageContent(
                        type=MessageContentType.VOICE,
                        url=seg_data.get("url", seg_data.get("file", ""))
                    ))

                elif seg_type == "video":
                    contents.append(MessageContent(
                        type=MessageContentType.VIDEO,
                        url=seg_data.get("url", seg_data.get("file", ""))
                    ))

                else:
                    contents.append(MessageContent(
                        type=MessageContentType.UNKNOWN,
                        raw_data=seg
                    ))

            # Extract reply_to from contents
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
        Convert UnifiedMessage back to OneBot v11 raw format.
        
        For backward compatibility with existing code that expects raw dicts.
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
                face_type = content.raw_data.get("face_type", "face") if content.raw_data else "face"
                message_chain.append({"type": face_type, "data": {"id": content.emoji_id}})
            elif content.type == MessageContentType.REPLY:
                reply_id = content.raw_data.get("reply_id", "") if content.raw_data else ""
                message_chain.append({"type": "reply", "data": {"id": reply_id}})
            elif content.type == MessageContentType.VOICE:
                message_chain.append({"type": "record", "data": {"url": content.url}})
            elif content.type == MessageContentType.VIDEO:
                message_chain.append({"type": "video", "data": {"url": content.url}})

        # Ensure sender fields are populated, even if missing in original
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
            # Add these helper fields for old analyzers that might expect them directly
            "raw_message": unified.text_content, 
            "user_id": unified.sender_id, 
        }

    @staticmethod
    def batch_from_onebot(raw_messages: List[dict], group_id: str) -> List[UnifiedMessage]:
        """Convert a batch of OneBot messages to UnifiedMessage list."""
        result = []
        for raw_msg in raw_messages:
            unified = MessageConverter.from_onebot_message(raw_msg, group_id)
            if unified:
                result.append(unified)
        return result

    @staticmethod
    def batch_to_onebot(unified_messages: List[UnifiedMessage]) -> List[dict]:
        """Convert a batch of UnifiedMessage to OneBot raw format."""
        return [MessageConverter.to_onebot_message(msg) for msg in unified_messages]

    @staticmethod
    def unified_to_analysis_text(messages: List[UnifiedMessage]) -> str:
        """
        Convert UnifiedMessage list to analysis text format for LLM.
        
        This is the format expected by the existing LLM analyzers.
        """
        lines = []
        for msg in messages:
            if msg.has_text():
                lines.append(msg.to_analysis_format())
        return "\n".join(lines)
