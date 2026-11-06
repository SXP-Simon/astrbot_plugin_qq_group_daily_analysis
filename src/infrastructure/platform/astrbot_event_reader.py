"""AstrBot 事件接入：解析平台差异并生成历史存储需要的数据。"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...shared.type_guards import is_object_collection, is_string_mapping
from .qq_official_faces import extract_qq_face_features

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent

_QQ_OFFICIAL_PLATFORM_NAMES = frozenset({"qq_official", "qq_official_webhook"})
_QQ_OFFICIAL_MENTION_PATTERN = re.compile(r"<@!?([A-Za-z0-9_-]+)>")


@dataclass(frozen=True)
class IncomingGroupMessage:
    """事件接入后用于去重与历史保存的明确数据。"""

    platform_id: str
    platform_name: str
    group_id: str
    sender_id: str
    sender_name: str
    message_id: str
    umo: str
    content: dict[str, object]
    has_content: bool


class AstrBotEventReader:
    """隔离不同平台及宿主版本的消息结构。"""

    def read(self, event: AstrMessageEvent) -> IncomingGroupMessage:
        """解析事件，不写入存储或修改事件。

        Args:
            event: 宿主收到的群消息事件。

        Returns:
            已校验身份的历史消息输入。

        Raises:
            ValueError: 缺少群组、发送者或平台 ID。
        """
        group_id = self._get_group_id_from_event(event)
        sender_id = str(event.get_sender_id() or "")
        platform_id = str(event.get_platform_id() or "")
        if not group_id or not sender_id or not platform_id:
            raise ValueError("缺少群组、发送者或平台 ID，拒绝存储消息")
        platform_name = str(event.get_platform_name() or "").strip().lower()
        sender_name = self._resolve_sender_name(event, sender_id)
        message_obj = getattr(event, "message_obj", None)
        message_id = str(getattr(message_obj, "message_id", "") or "").strip()
        parts = self._extract_message_parts(event)
        faces = (
            extract_qq_face_features(event)
            if platform_name in _QQ_OFFICIAL_PLATFORM_NAMES
            else []
        )
        if not parts and faces:
            parts = [
                {
                    "type": "plain",
                    "text": "".join(
                        f"[表情:{face['name'] or face['face_id'] or '未知'}]"
                        for face in faces
                    ),
                }
            ]
        content: dict[str, object] = {
            "type": "user",
            "message": parts,
            "message_id": message_id,
        }
        if platform_name in _QQ_OFFICIAL_PLATFORM_NAMES:
            content["_qq_official"] = {
                "message_id": message_id,
                "timestamp": self._extract_event_timestamp(message_obj),
                "faces": faces,
            }
        return IncomingGroupMessage(
            platform_id,
            platform_name,
            group_id,
            sender_id,
            sender_name,
            message_id,
            str(
                getattr(event, "unified_msg_origin", "")
                or f"{platform_id}:GroupMessage:{group_id}"
            ),
            content,
            bool(parts),
        )

    def _get_group_id_from_event(self, event: AstrMessageEvent) -> str | None:
        """从消息事件中安全获取群组 ID"""
        try:
            group_id = event.get_group_id()
            return group_id if group_id else None
        except Exception:
            return None

    def _resolve_sender_name(self, event: AstrMessageEvent, sender_id: str) -> str:
        """解析发送者展示名"""
        platform_name = str(event.get_platform_name() or "").lower()
        candidates: list[str | None] = []

        msg_obj = getattr(event, "message_obj", None)
        sender_obj = getattr(msg_obj, "sender", None)
        raw_message = getattr(msg_obj, "raw_message", None)
        raw_msg_obj = getattr(raw_message, "message", raw_message)
        from_user = getattr(raw_msg_obj, "from_user", None)

        if platform_name == "telegram":
            if from_user is not None:
                candidates.extend(
                    [
                        getattr(from_user, "full_name", None),
                        getattr(from_user, "first_name", None),
                    ]
                )
            candidates.append(event.get_sender_name())
            if sender_obj is not None:
                candidates.append(getattr(sender_obj, "nickname", None))
            if from_user is not None:
                candidates.append(getattr(from_user, "username", None))
        else:
            candidates.append(event.get_sender_name())
            if sender_obj is not None:
                candidates.append(getattr(sender_obj, "nickname", None))

        if from_user is not None:
            candidates.extend(
                [
                    getattr(from_user, "full_name", None),
                    getattr(from_user, "first_name", None),
                    getattr(from_user, "username", None),
                ]
            )

        for candidate in candidates:
            name = str(candidate or "").strip()
            if not self._is_placeholder_sender_name(name, sender_id):
                return name

        return sender_id

    def _extract_message_parts(self, event: AstrMessageEvent) -> list[dict[str, str]]:
        """从事件中提取消息内容"""
        message_parts: list[dict[str, str]] = []
        message = event.message_obj
        platform_name = str(event.get_platform_name() or "").strip().lower()
        qq_mention_replacements = (
            self._extract_qq_official_mention_replacements(event)
            if platform_name in _QQ_OFFICIAL_PLATFORM_NAMES
            else None
        )

        # 收集 @ 标记
        pending_mentions: Counter[str] = Counter()
        if message and hasattr(message, "message"):
            for seg in message.message:
                if not hasattr(seg, "type"):
                    continue
                if seg.type not in ("At", "at", "AtAll", "at_all"):
                    continue

                target = (
                    "all"
                    if seg.type in ("AtAll", "at_all")
                    else (getattr(seg, "target", None) or getattr(seg, "qq", None))
                )
                seg_data = getattr(seg, "data", None)
                if target is None and is_string_mapping(seg_data):
                    target = seg_data.get("qq") or seg_data.get("target")

                target_str = str(target or "").strip()
                if target_str:
                    pending_mentions[target_str] += 1

                display_name = str(getattr(seg, "name", "") or "").strip()
                if display_name and display_name != target_str:
                    pending_mentions[display_name] += 1

        if message and hasattr(message, "message"):
            for seg in message.message:
                if not hasattr(seg, "type"):
                    continue

                seg_type = seg.type
                seg_data = getattr(seg, "data", None)
                if seg_type in ("Plain", "text"):
                    text = getattr(seg, "text", None)
                    if text is None and is_string_mapping(seg_data):
                        text = seg_data.get("text")
                    if text:
                        text = self._strip_known_mentions(str(text), pending_mentions)
                        if qq_mention_replacements is not None:
                            text = self._sanitize_qq_official_mentions(
                                text, qq_mention_replacements
                            )
                        message_parts.append({"type": "plain", "text": text})

                elif seg_type in ("Image", "image"):
                    # QQ 官方图片附件缺少可确认的表情标记，不能凭 URL、GIF 后缀或文件名推断表情包。
                    url = getattr(seg, "url", None) or (
                        seg_data.get("url") if is_string_mapping(seg_data) else None
                    )
                    if url:
                        message_parts.append({"type": "image", "url": str(url)})

                elif seg_type in ("At", "at", "AtAll", "at_all"):
                    target = (
                        "all"
                        if seg.type in ("AtAll", "at_all")
                        else (getattr(seg, "target", None) or getattr(seg, "qq", None))
                    )
                    if target is None and is_string_mapping(seg_data):
                        target = seg_data.get("qq") or seg_data.get("target")
                    if target:
                        message_parts.append(
                            {
                                "type": "at",
                                "target_id": str(target),
                                "name": str(getattr(seg, "name", "") or ""),
                            }
                        )

                elif (
                    seg_type in ("Face", "face", "emoji")
                    and platform_name not in _QQ_OFFICIAL_PLATFORM_NAMES
                ):
                    emoji_id = getattr(seg, "id", None)
                    if emoji_id is None and is_string_mapping(seg_data):
                        emoji_id = seg_data.get("id")
                    if emoji_id is not None:
                        message_parts.append(
                            {
                                "type": "emoji",
                                "id": str(emoji_id),
                                "name": str(getattr(seg, "name", "") or ""),
                            }
                        )

                elif seg_type in ("Reply", "reply"):
                    reply_id = getattr(seg, "id", None)
                    if reply_id is None and is_string_mapping(seg_data):
                        reply_id = seg_data.get("id")
                    if reply_id is not None:
                        message_parts.append({"type": "reply", "id": str(reply_id)})

                elif seg_type in ("File", "file"):
                    url = getattr(seg, "url", None) or getattr(seg, "file_", None)
                    message_parts.append(
                        {
                            "type": "file",
                            "url": str(url or ""),
                            "name": str(getattr(seg, "name", "") or ""),
                        }
                    )

                elif seg_type in ("Record", "record", "voice"):
                    url = getattr(seg, "url", None) or getattr(seg, "file", None)
                    message_parts.append({"type": "voice", "url": str(url or "")})

                elif seg_type in ("Video", "video"):
                    url = getattr(seg, "url", None) or getattr(seg, "file", None)
                    message_parts.append({"type": "video", "url": str(url or "")})

        if not message_parts and event.message_str:
            fallback_text = str(event.message_str)
            if qq_mention_replacements is not None:
                fallback_text = self._sanitize_qq_official_mentions(
                    fallback_text, qq_mention_replacements
                )
            message_parts.append({"type": "plain", "text": fallback_text})

        # 清理空文本段并返回
        return [
            part
            for part in message_parts
            if not (
                part.get("type") == "plain" and not str(part.get("text", "")).strip()
            )
        ]

    @classmethod
    def _extract_qq_official_mention_replacements(
        cls, event: AstrMessageEvent
    ) -> dict[str, str]:
        message_obj = getattr(event, "message_obj", None)
        raw_message = getattr(message_obj, "raw_message", None)
        raw_candidates = [raw_message]
        nested_message = cls._read_field(raw_message, "message")
        if nested_message is not None and nested_message is not raw_message:
            raw_candidates.insert(0, nested_message)

        mentions = None
        for candidate in raw_candidates:
            mentions = cls._read_field(candidate, "mentions")
            if mentions is not None:
                break

        replacements: dict[str, str] = {}
        if not is_object_collection(mentions):
            return replacements

        for mention in mentions:
            mention_id = str(
                cls._read_field(
                    mention,
                    "id",
                    "member_openid",
                    "memberopenid",
                    "user_openid",
                    "useropenid",
                )
                or ""
            ).strip()
            if not mention_id:
                continue

            if cls._read_field(mention, "is_you") is True:
                replacements[mention_id] = ""
                continue

            display_name = str(
                cls._read_field(mention, "username", "name", "nickname") or ""
            ).strip()
            display_name = display_name.lstrip("@").strip()
            if cls._is_placeholder_sender_name(display_name, mention_id):
                display_name = "群友"
            replacements[mention_id] = f"@{display_name}"

        return replacements

    @staticmethod
    def _sanitize_qq_official_mentions(text: str, replacements: dict[str, str]) -> str:
        def replace_mention(match: re.Match[str]) -> str:
            mention_id = match.group(1)
            if mention_id.lower() in {"all", "everyone"}:
                return "@全体成员"
            return replacements.get(mention_id, "@群友")

        cleaned = _QQ_OFFICIAL_MENTION_PATTERN.sub(replace_mention, str(text))
        return re.sub(r"[^\S\r\n]{2,}", " ", cleaned).strip(" \t")

    @staticmethod
    def _read_field(source: object, *names: str) -> object | None:
        if is_string_mapping(source):
            for name in names:
                if name in source:
                    return source[name]
            return None

        for name in names:
            value = getattr(source, name, None)
            if value is not None:
                return value
        return None

    @staticmethod
    def _strip_known_mentions(text: str, pending_mentions: Counter[str]) -> str:
        """从文本中移除已识别的 @ 提及"""
        cleaned = str(text)
        if not cleaned or not pending_mentions:
            return cleaned.strip()

        for mention, remaining in list(pending_mentions.items()):
            if not mention or remaining <= 0:
                continue

            pattern = re.compile(rf"(?<!\w)@{re.escape(mention)}(?!\w)")
            removed = 0
            while removed < remaining:
                cleaned, subn = pattern.subn("", cleaned, count=1)
                if subn == 0:
                    break
                removed += 1

            if removed > 0:
                pending_mentions[mention] -= removed
                if pending_mentions[mention] <= 0:
                    pending_mentions.pop(mention, None)

        return re.sub(r"[^\S\r\n]{2,}", " ", cleaned).strip()

    @staticmethod
    def _is_placeholder_sender_name(name: str | None, sender_id: str) -> bool:
        """判断 sender_name 是否为占位值"""
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized.lower() in {"unknown", "none", "null", "nil", "undefined"}:
            return True
        return normalized == str(sender_id).strip()

    @staticmethod
    def _extract_event_timestamp(message_obj: object) -> int:
        """从消息对象中提取平台事件时间戳。"""
        raw_message = getattr(message_obj, "raw_message", None)
        if is_string_mapping(raw_message):
            candidate = raw_message.get("timestamp")
            if not candidate:
                raw_data = raw_message.get("raw_data")
                if is_string_mapping(raw_data):
                    candidate = raw_data.get("timestamp")
        else:
            raw_data = getattr(raw_message, "raw_data", None)
            candidate = getattr(raw_message, "timestamp", None)
            if not candidate and is_string_mapping(raw_data):
                candidate = raw_data.get("timestamp")
        if isinstance(candidate, (int, float)):
            return int(candidate)
        if candidate:
            try:
                from datetime import datetime

                return int(
                    datetime.fromisoformat(
                        str(candidate).replace("Z", "+00:00")
                    ).timestamp()
                )
            except (TypeError, ValueError, OverflowError):
                pass
        return 0
