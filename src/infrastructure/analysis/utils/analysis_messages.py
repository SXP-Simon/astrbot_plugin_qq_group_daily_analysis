"""将统一消息提取为模型输入，集中处理跨平台身份及消息关系。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

from ....domain.value_objects.unified_message import MessageContentType

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from ....domain.value_objects.unified_message import (
        AnalysisTextMessage,
        UnifiedMessage,
    )


def extract_analysis_messages(
    messages: Sequence[UnifiedMessage],
    *,
    use_card: bool,
    bot_self_ids: Collection[str],
) -> list[AnalysisTextMessage]:
    """为话题、金句和聊天质量提供一致的文本输入。

    Args:
        messages: 已清洗的统一消息，保留原始发送者 ID 与消息关系。
        use_card: 是否优先使用群名片，否则优先使用昵称。
        bot_self_ids: 需要排除的机器人 ID。

    Returns:
        非空且非命令的文本消息。提及记为 @[用户ID]，回复记为
        [回复:消息ID]，本批次被引用的消息标记为 [消息:消息ID]。
        不下载图片，也不将平台原始数据拼入提示词。
    """
    bot_ids = set(bot_self_ids)
    referenced_ids = {
        message.reply_to_id for message in messages if message.reply_to_id
    }
    result: list[AnalysisTextMessage] = []
    for message in messages:
        if message.sender_id in bot_ids or message.text_content.lstrip().startswith(
            "/"
        ):
            continue

        parts: list[str] = []
        for content in message.contents:
            if content.type == MessageContentType.TEXT:
                parts.append(content.text)
            elif content.type == MessageContentType.AT and content.at_user_id:
                parts.append(f" @[{content.at_user_id}] ")
        # 旧快照可能只保存文本；有文本段时以消息段为准，避免正文重复。
        if not any(
            content.type == MessageContentType.TEXT for content in message.contents
        ):
            parts.insert(0, message.text_content)
        text = "".join(parts).strip()
        if text.startswith("/"):
            continue
        if message.reply_to_id:
            text = f"[回复:{message.reply_to_id}] {text}"
        text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text).strip()
        if not text:
            continue
        if message.message_id in referenced_ids:
            text = f"[消息:{message.message_id}] {text}"

        result.append(
            {
                "time": datetime.fromtimestamp(message.timestamp).strftime("%H:%M"),
                "sender": message.get_display_name(use_card=use_card),
                "content": text,
                "user_id": message.sender_id,
            }
        )
    return result
