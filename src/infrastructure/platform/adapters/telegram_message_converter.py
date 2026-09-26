"""
Telegram 消息转换器 (Telegram Message Converter)

负责 Telegram 数据库历史记录、统一领域消息 (UnifiedMessage) 与 OneBot 兼容格式之间的双向转换，
并提供占位昵称自愈、群组话题 ID 解析以及转发消息文本排版功能。
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from ....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ....utils.logger import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from ....domain.repositories.bot_client_protocol import HistoryRecordProtocol
    from ....domain.value_objects.unified_group import UnifiedMember


class TelegramMessageConverter:
    """Telegram 消息转换与昵称自愈器。"""

    # Telegram 文本渲染：报告文本带 markdown 语法（**加粗** / `代码`），
    # 而 Bot API 默认按纯文本发送，导致群内看到的是 ** 原样字符。
    # 这里把 markdown 转成 Telegram HTML 模式可识别的标签，并转义 HTML 保留字符。
    # 刻意不处理 *斜体*：单个 * 在普通文本（2*3*4、*.py）里远比报告里常见，转换误伤大于收益。
    _MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.S)
    _MD_CODE_RE = re.compile(r"`([^`\n]+)`")
    # 行内代码里的 ** 不应被当成加粗（如 `**x**` 要原样显示），转换前先把代码段摘成
    # 占位符，其余转换做完再还原，避免代码段内容被后续正则改写。
    _MD_CODE_STASH_RE = re.compile(r"\x00(\d+)\x00")
    # 报告采用 Markdown 排版（与 QQ 官方一致）：标题 / 列表 / 引用。
    # Telegram HTML 模式不支持这些结构，这里逐行降级为加粗行、• 列表与引用块。
    # 注意：这些正则作用在「已转义」的文本上，所以引用符是 &gt; 而非 >。
    # 中标题（##/###）在 QQ 客户端自带间距，转为加粗行后需手动补一个空行，否则紧贴正文。
    _MD_TITLE_RE = re.compile(r"(?m)^[ \t]{0,3}#[ \t]+(.+?)[ \t]*$")
    _MD_SUBHEADING_RE = re.compile(r"(?m)^[ \t]{0,3}#{2,6}[ \t]*(.+?)[ \t]*$")
    _MD_BULLET_RE = re.compile(r"(?m)^[ \t]{0,3}[-+][ \t]+")
    _MD_QUOTE_RE = re.compile(r"(?m)^[ \t]{0,3}&gt;[ \t]?(.*)$")
    # 只有报告文本才带 Markdown 结构；图片标题、进度提示等纯文本必须走原样发送，
    # 否则正文里的 2*3*4、*.py 这类字符会被误当成斜体/列表标记。
    _MD_MARKER_RE = re.compile(r"(?m)^#{1,6}[ \t]+\S")

    @classmethod
    def looks_like_markdown_report(cls, text: str) -> bool:
        """判断文本是否是需要 Markdown 渲染的报告内容。

        以「是否含 ** 加粗」或「是否有 # 标题行」作为判据：插件的报告排版必然包含其一，
        而图片标题、进度提示等普通文本几乎不会出现，从而避免对普通文本做转换。

        Args:
            text: 待发送文本。

        Returns:
            bool: True 表示应按 Markdown 转 HTML 后发送。
        """
        source = str(text or "")
        return "**" in source or bool(cls._MD_MARKER_RE.search(source))

    @staticmethod
    def escape_html(text: str) -> str:
        """转义 Telegram HTML 模式下的保留字符。"""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @classmethod
    def to_telegram_html(cls, text: str) -> str:
        """将报告文本中的 markdown 语法转换为 Telegram HTML 标签。

        支持 QQ 官方同款排版：`# 标题`、`## 中标题`、`- 列表`、`> 引用`，
        以及 **加粗** / `代码`。行内代码段先摘出再还原，其中的 `**` 等标记不会被当作格式。

        Args:
            text: 含 markdown 语法的报告文本。

        Returns:
            str: 可直接以 parse_mode="HTML" 发送的文本。
        """
        escaped = cls.escape_html(text)
        code_spans: list[str] = []

        def stash_code(match: re.Match[str]) -> str:
            code_spans.append(match.group(1))
            return f"\x00{len(code_spans) - 1}\x00"

        escaped = cls._MD_CODE_RE.sub(stash_code, escaped)
        escaped = cls._MD_TITLE_RE.sub(r"<b>\1</b>", escaped)
        # 中标题后补空行，保持与 QQ 客户端一致的段落间距
        escaped = cls._MD_SUBHEADING_RE.sub(r"<b>\1</b>\n", escaped)
        escaped = cls._MD_QUOTE_RE.sub(r"<blockquote>\1</blockquote>", escaped)
        escaped = cls._MD_BULLET_RE.sub("• ", escaped)
        escaped = cls._MD_BOLD_RE.sub(r"<b>\1</b>", escaped)
        return cls._MD_CODE_STASH_RE.sub(
            lambda match: f"<code>{code_spans[int(match.group(1))]}</code>", escaped
        )

    @classmethod
    def strip_markdown(cls, text: str) -> str:
        """去除 markdown 标记，得到纯文本（HTML 渲染失败时的兜底）。

        与 `to_telegram_html` 一致，先把行内代码段摘出来，避免代码内容里的 `**`
        被当成加粗标记吃掉（`` `**x**` `` 应保留字面量，只去掉反引号）。
        """
        code_spans: list[str] = []

        def stash_code(match: re.Match[str]) -> str:
            code_spans.append(match.group(1))
            return f"\x00{len(code_spans) - 1}\x00"

        plain = cls._MD_CODE_RE.sub(stash_code, text)
        plain = cls._MD_BOLD_RE.sub(r"\1", plain)
        return cls._MD_CODE_STASH_RE.sub(
            lambda match: code_spans[int(match.group(1))], plain
        )

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
        return bool(sender_id and normalized == str(sender_id).strip())

    @classmethod
    async def fix_sender_name_if_needed(
        cls,
        group_id: str,
        msg: UnifiedMessage,
        sender_name_cache: dict[str, str],
        member_fetcher: Callable[[str, str], Awaitable[UnifiedMember | None]],
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
    def to_unified_message(
        record: HistoryRecordProtocol, group_id: str
    ) -> UnifiedMessage | None:
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
            raw_parts = content.get("message", [])
            message_parts = raw_parts if isinstance(raw_parts, list) else []
            text_content = ""
            contents: list[MessageContent] = []

            for part in message_parts:
                if isinstance(part, dict):
                    part_type = str(part.get("type", ""))
                    if part_type in ("plain", "text"):
                        text = str(part.get("text", ""))
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
                                url=str(
                                    part.get("url", "") or part.get("attachment_id", "")
                                ),
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
    def to_raw_format(messages: list[UnifiedMessage]) -> list[dict[str, object]]:
        """将统一消息列表转换为 OneBot 兼容的原生消息字典列表。

        用于向后兼容现有分析管线与数据序列化。

        Args:
            messages: 统一消息列表。

        Returns:
            list[dict[str, object]]: OneBot 兼容格式的原始消息字典列表。
        """
        result: list[dict[str, object]] = []
        for msg in messages:
            msg_segments: list[dict[str, object]] = []
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    msg_segments.append(
                        {"type": "text", "data": {"text": content.text or ""}}
                    )
                elif content.type == MessageContentType.IMAGE:
                    msg_segments.append(
                        {"type": "image", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.AT:
                    msg_segments.append(
                        {"type": "at", "data": {"qq": content.at_user_id or ""}}
                    )

            raw: dict[str, object] = {
                "message_id": msg.message_id,
                "group_id": msg.group_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card or "",
                },
                "message": msg_segments,
                "user_id": msg.sender_id,
            }

            result.append(raw)

        return result

    @staticmethod
    def format_forward_nodes_to_text(nodes: list[dict]) -> str:
        """将合并转发节点列表排版为 Markdown 格式的文本内容。

        Telegram 没有原生合并转发，只能把节点扁平化成一条消息。平台按段落切分时
        所有节点的 name 都是同一个（"分析报告"），这里不再逐段插入 **[name]** 标题，
        否则群里每段前面都会重复出现一次 "[分析报告]"；仅当节点名称确实不同
        （典型的多来源转发）时才保留逐段标题。

        Args:
            nodes: 转发节点字典列表。

        Returns:
            str: 格式化后的纯文本消息。
        """
        if not nodes:
            return ""

        names: list[str] = []
        contents: list[str] = []
        for node in nodes:
            data = node.get("data", node)
            name = str(data.get("name", "AstrBot"))
            content = data.get("content", "")
            if isinstance(content, list):
                text_parts: list[str] = []
                for seg in content:
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        text_parts.append(seg.get("data", {}).get("text", ""))
                content = "".join(text_parts)
            text = str(content).strip()
            if not text:
                continue
            names.append(name)
            contents.append(text)

        if not contents:
            return ""

        if len(set(names)) > 1:
            body = "\n\n".join(
                f"**[{name}]**\n{content}"
                for name, content in zip(names, contents, strict=True)
            )
        else:
            body = "\n\n".join(contents)

        # 正文自带 Markdown 标题（# 开头）时不再额外插 "📊 分析报告" 横幅
        if body.lstrip().startswith("#"):
            return body
        return "📊 **分析报告**\n\n" + body
