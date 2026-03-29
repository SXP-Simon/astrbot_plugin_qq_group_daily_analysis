# mypy: ignore-errors
# pyright: reportMissingImports=false
"""
Discord 平台适配器

为 Discord 平台提供消息获取、发送和群组管理功能。
这是一个骨架实现，展示如何为新平台创建适配器。

注意：Discord 的消息获取需要使用 Discord API，
具体实现取决于 AstrBot 的 Discord 集成方式。
"""

from collections.abc import AsyncIterable, Mapping
from datetime import datetime, timedelta
from typing import Protocol, cast

from ....utils.logger import logger

try:
    import discord
except ImportError:
    discord = None

from ....domain.value_objects.platform_capabilities import (
    DISCORD_CAPABILITIES,
    PlatformCapabilities,
)
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ..base import PlatformAdapter


class _DiscordClientLike(Protocol):
    user: "_DiscordUserLike | None"
    guilds: list["_DiscordGuildLike"]

    def get_channel(self, channel_id: int) -> "_DiscordChannelLike | None": ...
    async def fetch_channel(self, channel_id: int) -> "_DiscordChannelLike": ...
    async def fetch_user(self, user_id: int) -> "_DiscordUserLike | None": ...
    def get_user(self, user_id: int) -> "_DiscordUserLike | None": ...


class _DiscordAvatarLike(Protocol):
    url: str

    def with_size(self, size: int) -> "_DiscordAvatarLike": ...


class _DiscordDateTimeLike(Protocol):
    def timestamp(self) -> float: ...


class _DiscordUserLike(Protocol):
    id: int
    name: str
    display_name: str
    global_name: str | None
    nick: str | None
    display_avatar: _DiscordAvatarLike


class _DiscordAttachmentLike(Protocol):
    content_type: str | None
    url: str
    filename: str
    size: int


class _DiscordEmbedImageLike(Protocol):
    url: str | None


class _DiscordEmbedLike(Protocol):
    image: _DiscordEmbedImageLike | None
    description: str | None


class _DiscordStickerLike(Protocol):
    id: int
    name: str
    url: str


class _DiscordReferenceLike(Protocol):
    message_id: int | None


class _DiscordGuildPermissionsLike(Protocol):
    administrator: bool


class _DiscordMemberLike(Protocol):
    id: int
    name: str
    nick: str | None
    global_name: str | None
    joined_at: _DiscordDateTimeLike | None
    guild_permissions: _DiscordGuildPermissionsLike


class _DiscordGuildLike(Protocol):
    member_count: int
    owner_id: int
    members: list[_DiscordMemberLike]
    text_channels: list["_DiscordChannelLike"]
    icon: _DiscordAvatarLike | None

    def get_member(self, user_id: int) -> _DiscordMemberLike | None: ...
    async def fetch_member(self, user_id: int) -> _DiscordMemberLike: ...


class _DiscordMessageLike(Protocol):
    id: int
    content: str | None
    attachments: list[_DiscordAttachmentLike]
    embeds: list[_DiscordEmbedLike]
    stickers: list[_DiscordStickerLike]
    author: _DiscordUserLike | None
    created_at: _DiscordDateTimeLike | None
    reference: _DiscordReferenceLike | None


class _DiscordReactionMessageLike(Protocol):
    async def add_reaction(self, emoji: object) -> object: ...
    async def remove_reaction(self, emoji: object, user: object) -> object: ...


class _DiscordChannelLike(Protocol):
    id: int
    name: str
    guild: _DiscordGuildLike | None
    created_at: _DiscordDateTimeLike | None
    recipients: list[_DiscordUserLike]
    owner_id: int | None

    def history(
        self, *args: object, **kwargs: object
    ) -> AsyncIterable[_DiscordMessageLike]: ...
    async def send(self, *args: object, **kwargs: object) -> object: ...
    async def fetch_message(self, message_id: int) -> _DiscordReactionMessageLike: ...
    def get_partial_message(self, message_id: int) -> _DiscordReactionMessageLike: ...


class DiscordAdapter(PlatformAdapter):
    """
    具体实现：Discord 平台适配器

    利用 Discord API 为群组（频道）提供消息获取、发送及基础元数据查询功能。
    由于 Discord 的高度异步特性和复杂的权限模型，该适配器集成了懒加载客户端和多级频道查询机制。

    Attributes:
        bot_user_id (str): 机器人自身的 Discord 用户 ID
    """

    def __init__(self, bot_instance: object, config: dict[str, object] | None = None):
        """
        初始化 Discord 适配器。

        Args:
            bot_instance (object): 宿主机器人实例
            config (dict, optional): 配置项，用于提取机器人自身的 Discord ID
        """
        super().__init__(bot_instance, config)
        # 机器人自己的用户 ID，用于消息过滤（避免分析博取回复）
        self.bot_user_id = str(config.get("bot_user_id", "")) if config else ""

        # 缓存 Discord 客户端（Lazy Loading）
        self._cached_client: _DiscordClientLike | None = None

    @property
    def _discord_client(self) -> _DiscordClientLike | None:
        """
        内部属性：获取实际的 Discord 客户端实例。

        具备懒加载和自动身份嗅探功能。

        Returns:
            object | None: Discord Client 对象
        """
        if self._cached_client:
            return self._cached_client

        # 执行路径探测逻辑，兼容不同版本的 AstrBot 宿主结构
        self._cached_client = self._get_discord_client()

        # 兜底：尝试从客户端连接状态中补全机器人 ID
        if not self.bot_user_id and self._cached_client:
            client_user = self._cached_client.user
            if client_user is not None:
                self.bot_user_id = str(client_user.id)

        return self._cached_client

    def _get_discord_client(self) -> _DiscordClientLike | None:
        """内部方法：通过多级探测从 bot_instance 中提取 Discord SDK 客户端。"""
        # 路径 A：bot 本身就是 Client (如小型集成)
        if hasattr(self.bot, "get_channel"):
            return cast(_DiscordClientLike, self.bot)
        # 路径 B：bot 是包装器，client 在标准成员变量中
        client = getattr(self.bot, "client", None)
        if client is not None:
            return cast(_DiscordClientLike, client)
        # 路径 C：其他常见私有属性名
        for attr in ("_client", "discord_client", "_discord_client"):
            if hasattr(self.bot, attr):
                client = getattr(self.bot, attr)
                if hasattr(client, "get_channel"):
                    return cast(_DiscordClientLike, client)
        logger.warning(f"无法从 {type(self.bot).__name__} 中提取 Discord 客户端实例")
        return None

    async def _get_channel_safe(self, channel_id: int) -> _DiscordChannelLike | None:
        """通过客户端安全获取频道对象。"""
        client = self._discord_client
        if client is None:
            return None

        channel = client.get_channel(channel_id)
        if channel is not None:
            return channel
        return await client.fetch_channel(channel_id)

    async def _fetch_user_safe(self, user_id: int) -> _DiscordUserLike | None:
        """通过客户端安全获取用户对象。"""
        client = self._discord_client
        if client is None:
            return None
        return await client.fetch_user(user_id)

    def _init_capabilities(self) -> PlatformCapabilities:
        """返回预定义的 Discord 平台能力集。"""
        return DISCORD_CAPABILITIES

    # ==================== IMessageRepository 实现 ====================

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 100,
        before_id: str | None = None,
        since_ts: int | None = None,
    ) -> list[UnifiedMessage]:
        """
        从 Discord 频道异步拉取历史消息记录。

        Args:
            group_id (str): Discord 频道 (Channel) ID
            days (int): 查询天数范围
            max_count (int): 最大拉取消息数量上限
            before_id (str, optional): 锚点消息 ID，从此之前开始拉取

        Returns:
            list[UnifiedMessage]: 统一格式的消息对象列表
        """
        if not discord:
            logger.error("Discord module (py-cord) not found. Cannot fetch messages.")
            return []

        try:
            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                logger.debug(f"拉取 Discord 频道 {group_id} 失败: channel is None")
                return []

            # 验证权限：确保支持历史消息流
            if since_ts and since_ts > 0:
                start_time = datetime.fromtimestamp(since_ts)
            else:
                end_time = datetime.now()
                start_time = end_time - timedelta(days=days)

            messages = []

            # 构建 Discord SDK 的 history 查询参数
            history_kwargs = {"limit": max_count, "after": start_time}
            if before_id:
                try:
                    # py-cord 的 history 参数兼容消息 ID（int）
                    history_kwargs["before"] = int(before_id)
                except (ValueError, TypeError):
                    pass

            # 消息迭代处理
            history_iter = channel.history(**history_kwargs)
            async for msg in history_iter:
                # 排除机器人自身发布的消息
                author = msg.author
                author_id = author.id if author is not None else None
                if self.bot_user_id and str(author_id) == self.bot_user_id:
                    continue

                unified = self._convert_message(msg, group_id)
                if unified:
                    messages.append(unified)

            # 排序回升序（SDK 通常返回降序）
            messages.sort(key=lambda m: m.timestamp)
            return messages

        except Exception as e:
            logger.error(f"Discord fetch_messages failed: {e}", exc_info=True)
            return []

    def _convert_message(
        self, raw_msg: _DiscordMessageLike, group_id: str
    ) -> UnifiedMessage | None:
        """内部方法：将 `discord.Message` 对象转换为统一的 `UnifiedMessage`。"""
        try:
            contents = []
            content_text = str(raw_msg.content or "")

            # 1. 基础文本
            if content_text:
                contents.append(
                    MessageContent(type=MessageContentType.TEXT, text=content_text)
                )

            # 2. 附件处理 (图片/视频/语音/普通文件)
            for attachment in raw_msg.attachments:
                content_type = str(attachment.content_type or "")
                if content_type.startswith("image/"):
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE, url=attachment.url
                        )
                    )
                elif content_type.startswith("video/"):
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VIDEO, url=attachment.url
                        )
                    )
                elif content_type.startswith("audio/"):
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VOICE, url=attachment.url
                        )
                    )
                else:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.FILE,
                            url=attachment.url,
                            raw_data={
                                "filename": attachment.filename,
                                "size": attachment.size,
                            },
                        )
                    )

            # 3. 嵌入内容处理 (部分 Embed 可能包含富文本描述)
            for embed in raw_msg.embeds:
                if embed.image and embed.image.url:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE, url=embed.image.url
                        )
                    )
                if embed.description:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.TEXT,
                            text=f"\n[Embed] {embed.description}",
                        )
                    )

            # 4. 贴纸处理 (Stickers)
            stickers = raw_msg.stickers
            if stickers:
                for sticker in stickers:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE,  # 贴纸在逻辑上按图片处理
                            url=sticker.url,
                            raw_data={
                                "sticker_id": str(sticker.id),
                                "sticker_name": sticker.name,
                            },
                        )
                    )

            # 确定发送者的显示名称（服务器昵称 > 全局名称 > 用户名）
            sender_card = None
            author = raw_msg.author
            if author is not None:
                if author.nick:
                    sender_card = author.nick
                elif author.global_name:
                    sender_card = author.global_name

            raw_reference = raw_msg.reference
            reply_message_id = (
                str(raw_reference.message_id)
                if raw_reference is not None and raw_reference.message_id is not None
                else None
            )
            timestamp = (
                int(raw_msg.created_at.timestamp())
                if raw_msg.created_at is not None
                else 0
            )

            return UnifiedMessage(
                message_id=str(raw_msg.id),
                sender_id=str(author.id) if author is not None else "",
                sender_name=author.name if author is not None else "",
                sender_card=sender_card,
                group_id=group_id,
                text_content=content_text,
                contents=tuple(contents),
                timestamp=timestamp,
                platform="discord",
                reply_to_id=reply_message_id,
            )
        except Exception as e:
            logger.debug(f"Discord 消息转换错误: {e}")
            return None

    def convert_to_raw_format(
        self, messages: list[UnifiedMessage]
    ) -> list[dict[str, object]]:
        """将统一格式降级转换为 OneBot 风格的字典，以适配下游组件。"""
        raw_messages: list[dict[str, object]] = []
        for msg in messages:
            message_items: list[dict[str, object]] = []
            raw_msg: dict[str, object] = {
                "message_id": msg.message_id,
                "group_id": msg.group_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card,
                },
                "message": message_items,
                "user_id": msg.sender_id,  # 后向兼容
            }

            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    message_items.append(
                        {"type": "text", "data": {"text": content.text or ""}}
                    )
                elif content.type == MessageContentType.IMAGE:
                    message_items.append(
                        {
                            "type": "image",
                            "data": {"url": content.url, "file": content.url},
                        }
                    )
                elif content.type == MessageContentType.AT:
                    message_items.append(
                        {"type": "at", "data": {"qq": content.at_user_id}}
                    )
                elif content.type == MessageContentType.REPLY:
                    if (
                        isinstance(content.raw_data, dict)
                        and "reply_id" in content.raw_data
                    ):
                        message_items.append(
                            {
                                "type": "reply",
                                "data": {"id": content.raw_data["reply_id"]},
                            }
                        )

            raw_messages.append(raw_msg)
        return raw_messages

    # ==================== IMessageSender 实现 ====================

    async def send_text(
        self,
        group_id: str,
        text: str,
        reply_to: str | None = None,
    ) -> bool:
        """
        向 Discord 频道发送文本消息。

        Args:
            group_id (str): 频道 ID
            text (str): 文本内容
            reply_to (str, optional): 引用的消息 ID

        Returns:
            bool: 是否发送成功
        """
        if not discord:
            return False

        try:
            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                return False

            reference = None
            if reply_to:
                try:
                    reference = discord.MessageReference(
                        message_id=int(reply_to), channel_id=channel_id
                    )
                except (ValueError, TypeError):
                    pass

            await channel.send(content=text, reference=reference)
            return True
        except Exception as e:
            logger.error(f"Discord 文本发送失败: {e}")
            return False

    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """
        向 Discord 频道异步发送图片。

        对于远程 URL，会先下载到内存再通过 Discord API 发送。

        Args:
            group_id (str): 频道 ID
            image_path (str): 本地路径或 http URL
            caption (str): 可选说明文字

        Returns:
            bool: 是否发送成功
        """
        if not discord:
            return False

        try:
            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                return False

            file_to_send = None
            if image_path.startswith("base64://"):
                # Base64 图片：解码 -> 内存 Object -> Discord
                import base64  # Fix: Ensure base64 is imported
                from io import BytesIO

                try:
                    base64_data = image_path.split("base64://")[1]
                    image_bytes = base64.b64decode(base64_data)
                    file_to_send = discord.File(
                        BytesIO(image_bytes), filename="daily_report_image.png"
                    )
                except Exception as e:
                    logger.error(f"Discord Base64 图片解码失败: {e}")
                    return False

            elif image_path.startswith(("http://", "https://")):
                # 远程图片：下载 -> 内存 Object -> Discord
                from io import BytesIO

                import aiohttp

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            image_path, timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                # 尽量保留原始后缀
                                filename = image_path.split("/")[-1].split("?")[0]
                                if not filename.lower().endswith(
                                    (".png", ".jpg", ".jpeg", ".gif", ".webp")
                                ):
                                    filename = "daily_report_image.png"

                                file_to_send = discord.File(
                                    BytesIO(data), filename=filename
                                )
                            else:
                                # 兜底：如果下载失败，直接发 URL 给 Discord 尝试自动解析
                                content = (
                                    f"{caption}\n{image_path}"
                                    if caption
                                    else image_path
                                )
                                await channel.send(content=content)
                                return True
                except Exception as de:
                    logger.warning(
                        f"Discord 远程图片下载失败: {de}，将回退为发送 URL。"
                    )
                    content = f"{caption}\n{image_path}" if caption else image_path
                    await channel.send(content=content)
                    return True
            else:
                # 本地图片
                file_to_send = discord.File(image_path)

            if file_to_send:
                await channel.send(content=caption or None, file=file_to_send)
            return True

        except Exception as e:
            logger.error(f"Discord 图片发送失败: {e}")
            return False

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: str | None = None,
    ) -> bool:
        """向 Discord 频道上传任意文件。"""
        if not discord:
            return False

        try:
            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                return False

            file_to_send = discord.File(file_path, filename=filename)
            await channel.send(file=file_to_send)
            return True
        except Exception as e:
            logger.error(f"Discord 文件发送失败: {e}")
            return False

    async def send_forward_msg(
        self,
        group_id: str,
        nodes: list[Mapping[str, object]],
    ) -> bool:
        """
        在 Discord 模拟合并转发。

        由于 Discord 没有原生节点转发 API，我们将其转换为一组文本消息发送。
        """
        if not discord:
            return False

        try:
            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                return False

            # 将节点汇总为美化的文本块
            lines = ["📊 **结构化报告摘要 (Structured Report)**\n"]
            for node in nodes:
                node_data = node.get("data", node)  # 兼容不同格式
                data = node_data if isinstance(node_data, dict) else node
                name = str(data.get("name", "AstrBot"))
                content = str(data.get("content", ""))
                lines.append(f"**[{name}]**:\n{content}\n")

            full_text = "\n".join(lines)

            # 分段处理大消息
            if len(full_text) > 1900:
                parts = [
                    full_text[i : i + 1900] for i in range(0, len(full_text), 1900)
                ]
                for part in parts:
                    await channel.send(content=part)
            else:
                await channel.send(content=full_text)

            return True
        except Exception as e:
            logger.error(f"Discord 模拟转发失败: {e}")
            return False

    # ==================== IGroupInfoRepository 实现 ====================

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        """解析 Discord 频道及所属服务器的基本信息。"""
        if not discord:
            return None

        try:
            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                return None

            guild = channel.guild
            channel_id_value = str(channel.id)
            group_name = channel.name

            if guild:
                # 群聊（服务器频道）
                member_count = guild.member_count
                owner_id = str(guild.owner_id)
            else:
                # 私人对话（DM）
                member_count = len(channel.recipients) + 1
                owner_id = str(channel.owner_id or "")

            return UnifiedGroup(
                group_id=channel_id_value,
                group_name=group_name,
                member_count=member_count,
                owner_id=owner_id or None,
                create_time=(
                    int(channel.created_at.timestamp())
                    if channel.created_at is not None
                    else 0
                ),
                platform="discord",
            )
        except Exception as e:
            logger.debug(f"Discord 获取群组信息错误: {e}")
            return None

    async def get_group_list(self) -> list[str]:
        """列出机器人所在服务器中所有可访问的文本频道 ID。"""
        if not discord:
            return []

        try:
            channel_ids = []
            client = self._discord_client
            if client is None:
                return []
            for guild in client.guilds:
                for channel in guild.text_channels:
                    channel_ids.append(str(channel.id))
            return channel_ids
        except Exception:
            return []

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        """
        获取频道对应的成员列表。

        注意：对于大型服务器，建议启用 GUILD_MEMBERS 意图以保证列表完整性。
        """
        if not discord:
            return []

        try:
            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                return []

            guild = channel.guild
            if not guild:
                # 私聊收件人
                return [
                    UnifiedMember(
                        user_id=str(u.id),
                        nickname=u.name,
                        card=u.display_name,
                        role="member",
                    )
                    for u in channel.recipients
                ]

            members = []
            for member in guild.members:
                role = "member"
                if member.id == guild.owner_id:
                    role = "owner"
                elif member.guild_permissions.administrator:
                    role = "admin"

                members.append(
                    UnifiedMember(
                        user_id=str(member.id),
                        nickname=member.name,
                        card=member.nick or member.global_name,
                        role=role,
                        join_time=int(member.joined_at.timestamp())
                        if member.joined_at
                        else None,
                    )
                )
            return members
        except Exception:
            return []

    async def get_member_info(
        self,
        group_id: str,
        user_id: str,
    ) -> UnifiedMember | None:
        """获取并解析特定 Discord 用户的身份信息。"""
        if not discord:
            return None

        try:
            uid = int(user_id)
            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                return None

            guild = channel.guild
            if not guild:
                # 跨频道/私聊探测
                user = await self._fetch_user_safe(uid)
                if user is None:
                    return None
                return UnifiedMember(
                    user_id=str(user.id),
                    nickname=user.name,
                    card=user.display_name,
                )

            member = guild.get_member(uid) or await guild.fetch_member(uid)
            if not member:
                return None

            role = (
                "owner"
                if member.id == guild.owner_id
                else ("admin" if member.guild_permissions.administrator else "member")
            )

            return UnifiedMember(
                user_id=str(member.id),
                nickname=member.name,
                card=member.nick or member.global_name,
                role=role,
                join_time=int(member.joined_at.timestamp())
                if member.joined_at
                else None,
            )
        except Exception:
            return None

    # ==================== IAvatarRepository 实现 ====================

    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> str | None:
        """根据 Discord 用户 ID 动态解析其头像 CDN 地址。"""
        if not discord or not self._discord_client:
            return None

        try:
            uid = int(user_id)
            client = cast(_DiscordClientLike | None, self._discord_client)
            if client is None:
                return None
            user = client.get_user(uid) or await client.fetch_user(uid)

            if user is not None:
                # 自动对齐 Discord 支持的尺寸 (2的幂)
                allowed_sizes = (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
                target_size = min(allowed_sizes, key=lambda x: abs(x - size))
                return user.display_avatar.with_size(target_size).url

            return None
        except Exception as e:
            logger.debug(f"Discord 获取用户头像 URL 错误: {e}")
            return None

    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> str | None:
        """暂不提供 Base64 转换服务，优先使用 CDN 链接。"""
        return None

    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> str | None:
        """获取 Discord 服务器（Guild）的图标地址。"""
        if not discord:
            return None

        try:
            channel = await self._get_channel_safe(int(group_id))
            if channel is None:
                return None
            guild = channel.guild
            if guild and guild.icon:
                allowed_sizes = (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
                target_size = min(allowed_sizes, key=lambda x: abs(x - size))
                return guild.icon.with_size(target_size).url
            return None
        except Exception:
            return None

    async def batch_get_avatar_urls(
        self,
        user_ids: list[str],
        size: int = 100,
    ) -> dict[str, str | None]:
        """批量获取头像的最佳实践。"""
        return {uid: await self.get_user_avatar_url(uid, size) for uid in user_ids}

    async def set_reaction(
        self, group_id: str, message_id: str, emoji: str | int, is_add: bool = True
    ) -> bool:
        """
        Discord 实现消息回应。
        """
        if not discord:
            return False

        try:
            # 映射常见的表情 ID 为文字表情，使分析状态在跨平台保持一致
            mapping = {289: "🔍", 424: "📊", 124: "✅"}
            emoji_to_use = emoji
            if isinstance(emoji, int):
                emoji_to_use = mapping.get(emoji, str(emoji))
            elif emoji.isdigit():
                emoji_int = int(emoji)
                emoji_to_use = mapping.get(emoji_int, emoji)

            channel_id = int(group_id)
            channel = await self._get_channel_safe(channel_id)
            if channel is None:
                return False

            msg: _DiscordReactionMessageLike
            try:
                msg = channel.get_partial_message(int(message_id))
            except Exception:
                msg = await channel.fetch_message(int(message_id))

            if is_add:
                await msg.add_reaction(emoji_to_use)
            else:
                client = self._discord_client
                if client is None or client.user is None:
                    return False
                await msg.remove_reaction(emoji_to_use, client.user)
            return True
        except Exception as e:
            logger.debug(f"Discord set_reaction 失败: {e}")
            return False
