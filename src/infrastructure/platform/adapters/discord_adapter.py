"""
Discord 平台适配器

为 Discord 平台提供消息获取、发送和群组管理功能。
这是一个骨架实现，展示如何为新平台创建适配器。

注意：Discord 的消息获取需要使用 Discord API，
具体实现取决于 AstrBot 的 Discord 集成方式。
"""

from datetime import datetime, timedelta
from typing import Any

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


class DiscordAdapter(PlatformAdapter):
    """
    具体实现：Discord 平台适配器

    利用 Discord API 为群组（频道）提供消息获取、发送及基础元数据查询功能。
    由于 Discord 的高度异步特性和复杂的权限模型，该适配器集成了懒加载客户端和多级频道查询机制。

    Attributes:
        bot_user_id (str): 机器人自身的 Discord 用户 ID
    """

    def __init__(self, bot_instance: Any, config: dict | None = None):
        """
        初始化 Discord 适配器。

        Args:
            bot_instance (Any): 宿主机器人实例
            config (dict, optional): 配置项，用于提取机器人自身的 Discord ID
        """
        super().__init__(bot_instance, config)
        # 机器人自己的用户 ID，用于消息过滤（避免分析博取回复）
        self.bot_user_id = str(config.get("bot_user_id", "")) if config else ""

        # 缓存 Discord 客户端（Lazy Loading）
        self._cached_client = None

    @property
    def _discord_client(self) -> Any:
        """
        内部属性：获取实际的 Discord 客户端实例。

        具备懒加载和自动身份嗅探功能。

        Returns:
            Any: Discord Client 对象
        """
        if self._cached_client:
            return self._cached_client

        # 执行路径探测逻辑，兼容不同版本的 AstrBot 宿主结构
        self._cached_client = self._get_discord_client()

        # 兜底：尝试从客户端连接状态中补全机器人 ID
        if not self.bot_user_id and self._cached_client:
            if hasattr(self._cached_client, "user") and self._cached_client.user:
                self.bot_user_id = str(self._cached_client.user.id)

        return self._cached_client

    def _get_discord_client(self) -> Any:
        """内部方法：通过多级探测从 bot_instance 中提取 Discord SDK 客户端。"""
        # 路径 A：bot 本身就是 Client (如小型集成)
        if hasattr(self.bot, "get_channel"):
            return self.bot
        # 路径 B：bot 是包装器，client 在标准成员变量中
        if hasattr(self.bot, "client"):
            return self.bot.client
        # 路径 C：其他常见私有属性名
        for attr in ("_client", "discord_client", "_discord_client"):
            if hasattr(self.bot, attr):
                client = getattr(self.bot, attr)
                if hasattr(client, "get_channel"):
                    return client
        logger.warning(f"无法从 {type(self.bot).__name__} 中提取 Discord 客户端实例")
        return None

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
            # 先从缓存尝试获取频道
            channel = self._discord_client.get_channel(channel_id)
            if not channel:
                # 缓存未命中则通过网络 fetch
                try:
                    channel = await self._discord_client.fetch_channel(channel_id)
                except Exception as e:
                    logger.debug(f"拉取 Discord 频道 {group_id} 失败: {e}")
                    return []

            # 验证权限：确保支持历史消息流
            if not hasattr(channel, "history"):
                logger.warning(f"频道 {group_id} 不支持历史消息访问。")
                return []

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            messages = []

            # 构建 Discord SDK 的 history 查询参数
            history_kwargs = {"limit": max_count, "after": start_time}
            if before_id:
                try:
                    # 使用 Snowflake ID 指向特定消息
                    history_kwargs["before"] = discord.Object(id=int(before_id))
                except (ValueError, TypeError):
                    pass

            # 消息迭代处理
            async for msg in channel.history(**history_kwargs):
                # 排除机器人自身发布的消息
                if self.bot_user_id and str(msg.author.id) == self.bot_user_id:
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

    def _convert_message(self, raw_msg: Any, group_id: str) -> UnifiedMessage | None:
        """内部方法：将 `discord.Message` 对象转换为统一的 `UnifiedMessage`。"""
        try:
            contents = []

            # 1. 基础文本
            if raw_msg.content:
                contents.append(
                    MessageContent(type=MessageContentType.TEXT, text=raw_msg.content)
                )

            # 2. 附件处理 (图片/视频/语音/普通文件)
            for attachment in raw_msg.attachments:
                content_type = attachment.content_type or ""
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
                if embed.image:
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
            if raw_msg.stickers:
                for sticker in raw_msg.stickers:
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
            if hasattr(raw_msg.author, "nick") and raw_msg.author.nick:
                sender_card = raw_msg.author.nick
            elif hasattr(raw_msg.author, "global_name") and raw_msg.author.global_name:
                sender_card = raw_msg.author.global_name

            return UnifiedMessage(
                message_id=str(raw_msg.id),
                sender_id=str(raw_msg.author.id),
                sender_name=raw_msg.author.name,
                sender_card=sender_card,
                group_id=group_id,
                text_content=raw_msg.content,
                contents=tuple(contents),
                timestamp=int(raw_msg.created_at.timestamp()),
                platform="discord",
                reply_to_id=str(raw_msg.reference.message_id)
                if raw_msg.reference
                else None,
            )
        except Exception as e:
            logger.debug(f"Discord 消息转换错误: {e}")
            return None

    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        """将统一格式降级转换为 OneBot 风格的字典，以适配下游组件。"""
        raw_messages = []
        for msg in messages:
            raw_msg = {
                "message_id": msg.message_id,
                "group_id": msg.group_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card,
                },
                "message": [],
                "user_id": msg.sender_id,  # 后向兼容
            }

            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    raw_msg["message"].append(
                        {"type": "text", "data": {"text": content.text or ""}}
                    )
                elif content.type == MessageContentType.IMAGE:
                    raw_msg["message"].append(
                        {
                            "type": "image",
                            "data": {"url": content.url, "file": content.url},
                        }
                    )
                elif content.type == MessageContentType.AT:
                    raw_msg["message"].append(
                        {"type": "at", "data": {"qq": content.at_user_id}}
                    )
                elif content.type == MessageContentType.REPLY:
                    if content.raw_data and "reply_id" in content.raw_data:
                        raw_msg["message"].append(
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
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            if not hasattr(channel, "send"):
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
            channel = self._discord_client.get_channel(channel_id)
            if not channel:
                channel = await self._discord_client.fetch_channel(channel_id)

            if not hasattr(channel, "send"):
                return False

            file_to_send = None
            if image_path.startswith(("http://", "https://")):
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
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            if not hasattr(channel, "send"):
                return False

            file_to_send = discord.File(file_path, filename=filename)
            await channel.send(file=file_to_send)
            return True
        except Exception as e:
            logger.error(f"Discord 文件发送失败: {e}")
            return False

    # ==================== IGroupInfoRepository 实现 ====================

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        """解析 Discord 频道及所属服务器的基本信息。"""
        if not discord:
            return None

        try:
            channel_id = int(group_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            guild = getattr(channel, "guild", None)
            group_name = getattr(channel, "name", str(channel.id))

            if guild:
                # 群聊（服务器频道）
                member_count = guild.member_count
                owner_id = str(guild.owner_id)
            else:
                # 私人对话（DM）
                member_count = len(getattr(channel, "recipients", [])) + 1
                owner_id = str(getattr(channel, "owner_id", ""))

            return UnifiedGroup(
                group_id=str(channel.id),
                group_name=group_name,
                member_count=member_count,
                owner_id=owner_id or None,
                create_time=int(channel.created_at.timestamp()),
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
            for guild in self._discord_client.guilds:
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
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            guild = getattr(channel, "guild", None)
            if not guild:
                # 私聊收件人
                return [
                    UnifiedMember(
                        user_id=str(u.id),
                        nickname=u.name,
                        card=u.display_name,
                        role="member",
                    )
                    for u in getattr(channel, "recipients", [])
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
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            guild = getattr(channel, "guild", None)
            if not guild:
                # 跨频道/私聊探测
                user = await self.bot.fetch_user(uid)
                return UnifiedMember(
                    user_id=str(user.id), nickname=user.name, card=user.display_name
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
            user = self._discord_client.get_user(
                uid
            ) or await self._discord_client.fetch_user(uid)

            if user:
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
            channel = self.bot.get_channel(
                int(group_id)
            ) or await self.bot.fetch_channel(int(group_id))
            guild = getattr(channel, "guild", None)
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
