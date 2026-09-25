"""平台客户端底层通信行为协议 (Bot Client Communication Protocols)

定义各聊天平台底层 SDK / 客户端连接的结构化行为协议 (Protocol)，
彻底替代 hasattr/getattr 反射探测与弱类型 object。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence
    from datetime import datetime


@runtime_checkable
class HistoryRecordProtocol(Protocol):
    """AstrBot 数据库历史消息记录对象协议。"""

    @property
    def id(self) -> int | str | None: ...

    @property
    def sender_id(self) -> str | int | None: ...

    @property
    def sender_name(self) -> str | None: ...

    @property
    def content(self) -> dict[str, object] | None: ...

    @property
    def created_at(self) -> datetime: ...


@runtime_checkable
class OneBotClientProtocol(Protocol):
    """OneBot (v11/v12) 客户端连接行为协议。"""

    async def call_action(self, action: str, **params: object) -> object:
        """调用 OneBot 动作 API。"""
        ...


@runtime_checkable
class TelegramMessageProtocol(Protocol):
    """Telegram 消息返回对象协议。"""

    message_id: int


@runtime_checkable
class TelegramApplicationProtocol(Protocol):
    """Telegram Application 实例行为协议。"""

    bot: TelegramClientProtocol

    def add_handler(self, handler: object, group: int | None = None) -> object:
        """添加回调或消息处理器。"""
        ...

    def remove_handler(self, handler: object, group: int | None = None) -> None:
        """移除指定处理器。"""
        ...


@runtime_checkable
class TelegramUserProtocol(Protocol):
    """Telegram 用户对象协议。"""

    id: int
    is_bot: bool
    first_name: str
    username: str | None
    full_name: str | None


@runtime_checkable
class TelegramPhotoSizeProtocol(Protocol):
    """Telegram 照片尺寸对象协议。"""

    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: int | None
    file_path: str | None


@runtime_checkable
class TelegramUserProfilePhotosProtocol(Protocol):
    """Telegram 用户头像集合协议。"""

    total_count: int
    photos: list[list[TelegramPhotoSizeProtocol]]


@runtime_checkable
class TelegramChatPhotoProtocol(Protocol):
    """Telegram 群组头像对象协议。"""

    small_file_id: str
    big_file_id: str


@runtime_checkable
class TelegramChatProtocol(Protocol):
    """Telegram 聊天群组对象协议。"""

    id: int
    type: str
    title: str | None
    description: str | None
    photo: TelegramChatPhotoProtocol | None


@runtime_checkable
class TelegramChatMemberProtocol(Protocol):
    """Telegram 群组成员对象协议。"""

    user: TelegramUserProtocol
    status: str
    custom_title: str | None


@runtime_checkable
class TelegramFileProtocol(Protocol):
    """Telegram 文件路径元数据协议。"""

    file_id: str
    file_unique_id: str
    file_size: int | None
    file_path: str | None


@runtime_checkable
class TelegramClientProtocol(Protocol):
    """Telegram ExtBot / Client 客户端行为协议。"""

    token: str

    async def send_photo(
        self,
        chat_id: int | str,
        photo: object,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: object = None,
        message_thread_id: int | None = None,
        **kwargs: object,
    ) -> TelegramMessageProtocol:
        """发送图片。"""
        ...

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str | None = None,
        reply_markup: object = None,
        message_thread_id: int | None = None,
        **kwargs: object,
    ) -> TelegramMessageProtocol:
        """发送文本消息。"""
        ...

    async def send_document(
        self,
        chat_id: int | str,
        document: object,
        filename: str | None = None,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: object = None,
        message_thread_id: int | None = None,
        **kwargs: object,
    ) -> TelegramMessageProtocol:
        """发送文件/文档。"""
        ...

    async def get_chat(self, chat_id: int | str) -> TelegramChatProtocol:
        """获取聊天群组详情。"""
        ...

    async def get_chat_member_count(self, chat_id: int | str) -> int:
        """获取群成员总数。"""
        ...

    async def get_chat_administrators(
        self, chat_id: int | str
    ) -> list[TelegramChatMemberProtocol]:
        """获取群管理员列表。"""
        ...

    async def get_chat_member(
        self, chat_id: int | str, user_id: int
    ) -> TelegramChatMemberProtocol:
        """获取群成员信息。"""
        ...

    async def get_user_profile_photos(
        self, user_id: int, offset: int | None = None, limit: int | None = None
    ) -> TelegramUserProfilePhotosProtocol:
        """获取用户头像照片列表。"""
        ...

    async def get_file(self, file_id: str) -> TelegramFileProtocol:
        """获取文件下载路径信息。"""
        ...

    async def set_message_reaction(
        self,
        chat_id: int | str,
        message_id: int,
        reaction: object = None,
        is_big: bool = False,
    ) -> bool:
        """设置消息表情回应。"""
        ...


@runtime_checkable
class DiscordUserProtocol(Protocol):
    """Discord 用户对象协议。"""

    id: int
    name: str
    bot: bool
    avatar: object
    display_name: str | None
    display_avatar: object


@runtime_checkable
class DiscordMessageProtocol(Protocol):
    """Discord 消息对象协议。"""

    id: int
    author: DiscordUserProtocol
    content: str
    created_at: datetime
    attachments: Sequence[object]
    embeds: Sequence[object]
    stickers: Sequence[object]
    reference: object | None

    async def add_reaction(self, emoji: object) -> None:
        """添加表情回应。"""
        ...

    async def remove_reaction(self, emoji: object, member: object = None) -> None:
        """移除表情回应。"""
        ...


@runtime_checkable
class DiscordChannelProtocol(Protocol):
    """Discord 频道对象协议。"""

    id: int
    name: str
    guild: object | None
    created_at: datetime | None

    async def fetch_message(self, id: int) -> DiscordMessageProtocol:
        """获取指定消息"""
        ...

    def get_partial_message(self, message_id: int) -> object:
        """获取部分消息对象"""
        ...

    async def send(
        self,
        content: str | None = None,
        file: object = None,
        files: list[object] | None = None,
        **kwargs: object,
    ) -> object:
        """向频道发送消息或文件。"""
        ...

    def history(
        self,
        limit: int | None = 100,
        before: object = None,
        after: object = None,
        around: object = None,
        oldest_first: bool | None = None,
    ) -> AsyncIterator[DiscordMessageProtocol]:
        """获取频道历史消息流。"""
        ...


@runtime_checkable
class DiscordGuildProtocol(Protocol):
    """Discord 服务器(Guild)协议。"""

    id: int
    name: str
    text_channels: Sequence[DiscordChannelProtocol]


@runtime_checkable
class DiscordClientProtocol(Protocol):
    """Discord SDK Client 行为协议。"""

    user: DiscordUserProtocol | None
    guilds: Sequence[DiscordGuildProtocol]

    def get_channel(self, channel_id: int) -> DiscordChannelProtocol | None:
        """通过 ID 获取频道对象。"""
        ...

    async def fetch_channel(self, channel_id: int) -> DiscordChannelProtocol:
        """通过网络拉取频道对象。"""
        ...

    def get_user(self, user_id: int) -> DiscordUserProtocol | None:
        """通过 ID 获取缓存用户。"""
        ...

    async def fetch_user(self, user_id: int) -> DiscordUserProtocol:
        """通过网络拉取用户信息。"""
        ...


@runtime_checkable
class QQOfficialPlatformProtocol(Protocol):
    """QQ 官方机器人平台协议。"""

    config: Mapping[str, object] | None

    def remember_session_scene(self, session_id: str, scene: str) -> None:
        """记录会话场景（用于主动发消息前恢复场景）。"""
        ...


@runtime_checkable
class QQOfficialApiProtocol(Protocol):
    """QQ 官方机器人 API 协议。"""

    def post_group_message(
        self,
        group_openid: str,
        msg_type: int,
        markdown: object,
        msg_seq: int,
    ) -> object:
        """发送 QQ 官方群 Markdown 消息。"""
        ...


@runtime_checkable
class QQOfficialBotProtocol(Protocol):
    """QQ 官方机器人客户端行为协议。"""

    api: QQOfficialApiProtocol | None
    platform: QQOfficialPlatformProtocol | None
