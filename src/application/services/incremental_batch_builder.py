"""增量批次构建与统计转换辅助模块

负责将消息序列和领域活跃度统计转换为增量分析批次（IncrementalBatch）所需的数据结构。
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...domain.services.analysis_domain_service import UserActivityStats
    from ...domain.value_objects.unified_message import UnifiedMessage


def compute_hourly_counts(
    messages: list[UnifiedMessage],
) -> tuple[dict[int, int], dict[int, int]]:
    """从消息列表计算按小时的消息数和字符数分布。

    Args:
        messages: 统一格式的消息列表。

    Returns:
        包含 (每小时消息计数字典, 每小时字符计数字典) 的元组。
    """
    hourly_msg: dict[int, int] = defaultdict(int)
    hourly_char: dict[int, int] = defaultdict(int)

    for msg in messages:
        hour = dt.datetime.fromtimestamp(msg.timestamp).hour
        hourly_msg[hour] += 1
        hourly_char[hour] += msg.get_text_length()

    return dict(hourly_msg), dict(hourly_char)


def convert_user_activity_for_merge(
    user_activity: Mapping[str, UserActivityStats],
    messages: list[UnifiedMessage],
) -> dict[str, dict]:
    """将领域用户活跃度数据转换为 IncrementalBatch 所需的 user_stats 字典格式。

    Args:
        user_activity: 用户活跃度统计字典。
        messages: 当前批次的消息列表。

    Returns:
        增量批次所需的用户统计字典。
    """
    user_last_time: dict[str, int] = {}
    for msg in messages:
        current = user_last_time.get(msg.sender_id, 0)
        if msg.timestamp > current:
            user_last_time[msg.sender_id] = msg.timestamp

    result: dict[str, dict] = {}
    for user_id, stats in user_activity.items():
        result[user_id] = {
            "nickname": stats.get("nickname", user_id),
            "message_count": stats.get("message_count", 0),
            "char_count": stats.get("char_count", 0),
            "emoji_count": stats.get("emoji_count", 0),
            "reply_count": stats.get("reply_count", 0),
            "hours": dict(stats.get("hours", {})),
            "last_message_time": user_last_time.get(user_id, 0),
        }

    return result
