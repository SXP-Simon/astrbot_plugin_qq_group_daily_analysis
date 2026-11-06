"""宿主历史存储接口适配，隔离旧版本参数差异。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict, cast

from ...utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.star import Context

    from ..config.config_manager import ConfigManager

_LOCAL_HISTORY_MAX_MESSAGES = 10000


class HistoryInsertArguments(TypedDict):
    """宿主消息历史写入的必填参数。"""

    platform_id: str
    user_id: str
    content: dict[str, object]
    sender_id: str
    sender_name: str


class HistoryWriter(Protocol):
    """兼容宿主历史写入方法，旧版不支持的参数仍由原有分支回退。"""

    async def insert(
        self,
        platform_id: str,
        user_id: str,
        content: dict[str, object],
        sender_id: str | None = None,
        sender_name: str | None = None,
        max_messages: int | None = None,
    ) -> object: ...


class AstrBotHistoryWriter:
    """在接入边界缓存宿主是否支持消息保留上限。"""

    def __init__(self, context: Context, config_manager: ConfigManager | None) -> None:
        self.context = context
        self.config_manager = config_manager
        self._supports_history_max_messages: bool | None = None

    async def insert(
        self,
        platform_id: str,
        group_id: str,
        content: dict[str, object],
        sender_id: str,
        sender_name: str,
    ) -> None:
        """兼容不同 AstrBot 版本的消息历史写入接口。

        Args:
            platform_id: AstrBot 平台实例 ID。
            group_id: 当前群组 ID。
            content: 待持久化的标准化消息内容。
            sender_id: 发送者 ID。
            sender_name: 发送者展示名称。

        Raises:
            Exception: 消息历史管理器写入失败时原样抛出。
        """
        insert = cast("HistoryWriter", self.context.message_history_manager).insert
        insert_kwargs: HistoryInsertArguments = {
            "platform_id": platform_id,
            "user_id": group_id,
            "content": content,
            "sender_id": sender_id,
            "sender_name": sender_name,
        }
        if self._supports_history_max_messages is False:
            await insert(**insert_kwargs)
            return

        max_messages = (
            self.config_manager.get_local_history_max_messages()
            if self.config_manager is not None
            else _LOCAL_HISTORY_MAX_MESSAGES
        )

        try:
            await insert(**insert_kwargs, max_messages=max_messages)
        except TypeError as exc:
            if "unexpected keyword argument 'max_messages'" not in str(exc):
                raise

            self._supports_history_max_messages = False
            logger.warning(
                "[消息历史] 当前 AstrBot 核心不支持 max_messages 参数，"
                "将使用兼容模式写入消息历史；建议升级核心以启用本地历史上限。"
            )
            await insert(**insert_kwargs)
        else:
            self._supports_history_max_messages = True
