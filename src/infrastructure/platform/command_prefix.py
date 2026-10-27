"""读取会话生效的 AstrBot 命令前缀，供交互提示复用。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from astrbot.api.star import Context


def get_command_prefix(context: Context | None, event: AstrMessageEvent) -> str:
    """按宿主匹配顺序选择首个字符串前缀，保留合法的空前缀。

    Args:
        context: AstrBot 上下文；未初始化时不猜测宿主前缀。
        event: 用于定位当前会话配置的消息事件。

    Returns:
        配置列表中的首个字符串，空字符串有效；无法读取时返回空字符串，
        让已通过 @ 唤醒的会话仍可使用裸命令，不回退到其他会话的配置。
    """
    if context is None:
        return ""
    umo: str | None = getattr(event, "unified_msg_origin", None)
    if not isinstance(umo, str) or not umo:
        return ""
    try:
        prefixes: object = context.get_config(umo=umo).get("wake_prefix", [])
        if isinstance(prefixes, list):
            for prefix in prefixes:
                if isinstance(prefix, str):
                    return prefix
    except Exception as exc:
        logger.debug(
            "读取会话命令前缀失败，提示使用裸命令: error_type=%s", type(exc).__name__
        )
    return ""
