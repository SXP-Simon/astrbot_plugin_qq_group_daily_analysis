"""保留 QQ 官方原始表情事实，不从图片、Unicode 文本或占位描述猜测表情。"""

from __future__ import annotations

import base64
import json
import re
from typing import TYPE_CHECKING, TypedDict

from ...domain.value_objects.unified_message import MessageContent, MessageContentType

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent


_FACE_TAG = re.compile(
    r'<faceType\s*=\s*([0-9]+)((?:\s*,\s*[A-Za-z]\w*\s*=\s*(?:"[^"<>]*"|[0-9]+))*)\s*>'
)
_FACE_ATTRIBUTE = re.compile(r'(\w+)\s*=\s*(?:"([^"<>]*)"|([0-9]+))')


class QQFaceFeature(TypedDict):
    """平台原始标签或明确 Face 组件提供的表情特征。"""

    face_type: str
    face_id: str
    name: str


def extract_qq_face_features(event: AstrMessageEvent) -> list[QQFaceFeature]:
    """从普通或 Webhook 事件读取事实，不反推宿主转换后的可读占位文本。

    Args:
        event: QQ 官方群消息事件。

    Returns:
        可直接写入历史 JSON 的表情特征，不保留完整原始事件或 ext 数据。
    """
    message = event.message_obj
    raw = getattr(message, "raw_message", None)
    raw_data = getattr(raw, "raw_data", None)
    sources = []
    for source in (raw_data, raw):
        if isinstance(source, dict):
            sources.append(source.get("d"))
        sources.append(source)
    raw_text: str | None = None
    # 只读取本条正文，不扫描 msg_elements 中引用的旧消息，避免重复计算引用表情。
    for source in sources:
        content = (
            source.get("content")
            if isinstance(source, dict)
            else getattr(source, "content", None)
        )
        if isinstance(content, str):
            raw_text = content
            break
    faces = _parse_face_tags(raw_text or "")
    if faces:
        # 宿主将来若同时输出 Face 组件，也不能把同一份原始表情重复记录。
        return faces
    for component in getattr(message, "message", None) or []:
        if getattr(component, "type", None) not in ("Face", "face"):
            continue
        face_id = getattr(component, "id", None)
        if isinstance(face_id, bool) or not isinstance(face_id, (str, int)):
            continue
        identifier = str(face_id)
        if identifier.isascii() and identifier.isdecimal():
            faces.append({"face_type": "component", "face_id": identifier, "name": ""})
    return faces


def _parse_face_tags(text: str) -> list[QQFaceFeature]:
    """解析完整 QQ 协议标签，描述损坏不影响已确认的表情次数。

    Args:
        text: 原始事件 content 字段，未使用宿主的可读占位替换。

    Returns:
        保留重复次数、类型与标识的表情事实。
    """
    faces: list[QQFaceFeature] = []
    for match in _FACE_TAG.finditer(text):
        attributes = {
            key: quoted or numeric
            for key, quoted, numeric in _FACE_ATTRIBUTE.findall(match[2])
        }
        if "faceId" not in attributes and "ext" not in attributes:
            continue
        name = ""
        ext = attributes.get("ext", "")
        if ext and len(ext) <= 16384:
            try:
                decoded = json.loads(base64.b64decode(ext, validate=True))
                if isinstance(decoded, dict) and isinstance(decoded.get("text"), str):
                    description = decoded["text"][:256]
                    description.encode("utf-8")
                    name = description
            except (ValueError, UnicodeError, RecursionError):
                # 类型标记已经确认一次表情；描述只用于展示，不能阻断整条消息入库。
                pass
        faces.append(
            {
                "face_type": match[1],
                "face_id": attributes.get("faceId", ""),
                "name": name,
            }
        )
    return faces


def restore_qq_face_features(metadata: dict[str, object]) -> list[MessageContent]:
    """将已持久化的表情事实还原为统计使用的统一内容段。

    Args:
        metadata: QQ 官方消息元数据。

    Returns:
        明确保存的表情段；旧记录缺少事实时不依据占位描述或图片补猜。
    """
    faces = metadata.get("faces")
    if not isinstance(faces, list):
        return []
    contents = []
    for face in faces:
        if not isinstance(face, dict):
            continue
        kind, face_id, name = (
            face.get("face_type"),
            face.get("face_id"),
            face.get("name", ""),
        )
        if not isinstance(kind, str) or not (
            (kind.isascii() and kind.isdecimal()) or kind == "component"
        ):
            continue
        if not isinstance(face_id, str) or not isinstance(name, str):
            continue
        if kind == "component" and not (face_id.isascii() and face_id.isdecimal()):
            continue
        contents.append(
            MessageContent(
                type=MessageContentType.EMOJI,
                emoji_id=f"qq:{kind}:{face_id or name or 'unknown'}",
                emoji_name=name,
                raw_data={"face_type": kind, "face_id": face_id},
            )
        )
    return contents
