"""
Discord 平台适配器

为 Discord 平台提供消息获取、发送和群组管理功能。
这是一个骨架实现，展示如何为新平台创建适配器。

注意：Discord 的消息获取需要使用 Discord API，
具体实现取决于 AstrBot 的 Discord 集成方式。
"""

from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict
import asyncio
from ....utils.logger import logger

try:
    import discord
except ImportError:
    discord = None

from ....domain.value_objects.unified_message import (
    UnifiedMessage,
    MessageContent,
    MessageContentType,
)
from ....domain.value_objects.platform_capabilities import (
    PlatformCapabilities,
    DISCORD_CAPABILITIES,
)
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ..base import PlatformAdapter


class DiscordAdapter(PlatformAdapter):
    """
    Discord 平台适配器

    实现 PlatformAdapter 接口，提供 Discord 平台的消息操作。

    使用方式：
    1. 通过 PlatformAdapterFactory.create("discord", bot_instance, config) 创建
    2. 或直接实例化：DiscordAdapter(bot_instance, config)

    配置参数：
    - bot_user_id: 机器人的 Discord 用户 ID（用于过滤自己的消息）
    """

    def __init__(self, bot_instance: Any, config: dict = None):
        super().__init__(bot_instance, config)
        # 机器人自己的用户 ID，用于过滤消息
        self.bot_user_id = str(config.get("bot_user_id", "")) if config else ""

        # 缓存 Discord 客户端（懒加载）
        self._cached_client = None

    @property
    def _discord_client(self) -> Any:
        """
        获取实际的 Discord 客户端实例 (Lazy Load)
        """
        if self._cached_client:
            return self._cached_client

        # 尝试获取客户端
        self._cached_client = self._get_discord_client()

        # 尝试从 Discord 客户端获取 ID (如果之前没获取到)
        if not self.bot_user_id and self._cached_client:
            if hasattr(self._cached_client, "user") and self._cached_client.user:
                self.bot_user_id = str(self._cached_client.user.id)

        return self._cached_client

    def _get_discord_client(self) -> Any:
        """
        获取实际的 Discord 客户端实例

        AstrBot 的 DiscordPlatformAdapter 将 Discord 客户端存储在 self.client 中
        """
        # 如果 bot 本身就是 Discord client (有 get_channel 方法)
        if hasattr(self.bot, "get_channel"):
            return self.bot
        # 如果 bot 是 DiscordPlatformAdapter，client 在 self.bot.client 中
        if hasattr(self.bot, "client"):
            return self.bot.client
        # 尝试其他可能的属性名
        for attr in ["_client", "discord_client", "_discord_client"]:
            if hasattr(self.bot, attr):
                client = getattr(self.bot, attr)
                if hasattr(client, "get_channel"):
                    return client
        logger.warning(f"无法从 {type(self.bot).__name__} 获取 Discord 客户端")
        return None

    def _init_capabilities(self) -> PlatformCapabilities:
        """初始化 Discord 平台能力"""
        return DISCORD_CAPABILITIES

    # ==================== IMessageRepository ====================

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 100,
        before_id: Optional[str] = None,
    ) -> List[UnifiedMessage]:
        """
        获取 Discord 频道消息历史

        参数：
            group_id: Discord 频道 ID
            days: 获取多少天内的消息
            max_count: 最大消息数量
            before_id: 从此消息 ID 之前开始获取（用于分页）

        返回：
            UnifiedMessage 列表
        """
        if not discord:
            logger.error("未安装 py-cord 库，无法使用 Discord 适配器")
            return []

        try:
            channel_id = int(group_id)
            channel = self._discord_client.get_channel(channel_id)
            if not channel:
                # 尝试 fetch (API调用)
                try:
                    channel = await self._discord_client.fetch_channel(channel_id)
                except Exception:
                    logger.warning(f"无法找到频道 ID: {group_id}")
                    return []

            # 检查频道是否支持历史记录
            if not hasattr(channel, "history"):
                logger.warning(f"频道 {group_id} 不支持历史消息获取")
                return []

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            messages = []

            # 构建 history 参数
            history_kwargs = {"limit": max_count, "after": start_time}
            if before_id:
                try:
                    # before 可以接受 Message 对象或 ID (int)
                    history_kwargs["before"] = discord.Object(id=int(before_id))
                except ValueError:
                    pass

            # 获取消息
            async for msg in channel.history(**history_kwargs):
                # 过滤机器人自己的消息（如果配置了 ID）
                if self.bot_user_id and str(msg.author.id) == self.bot_user_id:
                    continue

                unified = self._convert_message(msg, group_id)
                if unified:
                    messages.append(unified)

            # 按时间升序排序
            messages.sort(key=lambda m: m.timestamp)
            return messages

        except Exception as e:
            logger.error(f"获取 Discord 消息失败: {e}", exc_info=True)
            return []

    def _convert_message(self, raw_msg: Any, group_id: str) -> Optional[UnifiedMessage]:
        """
        将 Discord 消息转换为统一格式

        参数：
            raw_msg: Discord 原始消息对象 (discord.Message)
            group_id: 频道 ID

        返回：
            UnifiedMessage 或 None
        """
        try:
            contents = []

            # 1. 文本内容
            if raw_msg.content:
                contents.append(
                    MessageContent(type=MessageContentType.TEXT, text=raw_msg.content)
                )

            # 2. 附件处理
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

            # 3. 嵌入内容 (Embeds) - 通常是富文本或图片
            for embed in raw_msg.embeds:
                if embed.image:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE, url=embed.image.url
                        )
                    )
                # 其他 embed 内容暂作为未知类型或文本处理
                if embed.description:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.TEXT,
                            text=f"\n[Embed] {embed.description}",
                        )
                    )

            # 4. 贴纸 (Stickers)
            if raw_msg.stickers:
                for sticker in raw_msg.stickers:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE,  # 贴纸视为图片
                            url=sticker.url,
                            raw_data={
                                "sticker_id": str(sticker.id),
                                "sticker_name": sticker.name,
                            },
                        )
                    )

            # 发送者名片 (昵称)
            sender_card = None
            if hasattr(raw_msg.author, "nick") and raw_msg.author.nick:
                sender_card = raw_msg.author.nick
            elif hasattr(raw_msg.author, "global_name") and raw_msg.author.global_name:
                sender_card = raw_msg.author.global_name

            return UnifiedMessage(
                message_id=str(raw_msg.id),
                sender_id=str(raw_msg.author.id),
                sender_name=raw_msg.author.name,  # 用户名
                sender_card=sender_card,  # 服务器昵称
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
            logger.error(f"转换 Discord 消息失败: {e}")
            return None

    def convert_to_raw_format(self, messages: List[UnifiedMessage]) -> List[dict]:
        """
        将统一消息格式转换为 OneBot 兼容格式 (用于兼容 MessageHandler)
        """
        raw_messages = []
        for msg in messages:
            # 构造 OneBot 风格的消息字典
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
            }

            # 构造消息链
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    raw_msg["message"].append(
                        {"type": "text", "data": {"text": content.text}}
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
                # 其他类型暂忽略或作为未知

            raw_messages.append(raw_msg)

        return raw_messages

    # ==================== IMessageSender ====================

    async def send_text(
        self,
        group_id: str,
        text: str,
        reply_to: Optional[str] = None,
    ) -> bool:
        """发送文本消息到 Discord 频道"""
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
                    # 创建 MessageReference
                    reference = discord.MessageReference(
                        message_id=int(reply_to), channel_id=channel_id
                    )
                except ValueError:
                    pass

            await channel.send(content=text, reference=reference)
            return True
        except Exception as e:
            logger.error(f"Discord 发送文本失败: {e}")
            return False

    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """发送图片到 Discord 频道"""
        if not discord:
            return False

        try:
            channel_id = int(group_id)
            channel = self._discord_client.get_channel(channel_id)
            if not channel:
                channel = await self._discord_client.fetch_channel(channel_id)

            if not hasattr(channel, "send"):
                return False

            # 处理本地文件或 URL
            file_to_send = None
            if image_path.startswith(("http://", "https://")):
                # URL 方式，需要下载图片后作为文件发送
                # 因为 Discord 无法访问内部 URL
                import aiohttp
                from io import BytesIO

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            image_path, timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                # 从 URL 提取文件名
                                filename = image_path.split("/")[-1].split("?")[0]
                                if not filename.lower().endswith(
                                    (".png", ".jpg", ".jpeg", ".gif", ".webp")
                                ):
                                    filename = "report.png"
                                file_to_send = discord.File(
                                    BytesIO(image_data), filename=filename
                                )
                            else:
                                logger.warning(
                                    f"Discord 下载图片失败，状态码: {response.status}"
                                )
                                # 降级：直接发送 URL
                                content = (
                                    f"{caption}\n{image_path}"
                                    if caption
                                    else image_path
                                )
                                await channel.send(content=content)
                                return True
                except Exception as download_error:
                    logger.warning(f"Discord 下载图片异常: {download_error}")
                    # 降级：直接发送 URL
                    content = f"{caption}\n{image_path}" if caption else image_path
                    await channel.send(content=content)
                    return True
            else:
                # 本地文件
                file_to_send = discord.File(image_path)

            if file_to_send:
                await channel.send(
                    content=caption if caption else None, file=file_to_send
                )
            return True

        except Exception as e:
            logger.error(f"Discord 发送图片失败: {e}")
            return False

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: Optional[str] = None,
    ) -> bool:
        """发送文件到 Discord 频道"""
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
            logger.error(f"Discord 发送文件失败: {e}")
            return False

    # ==================== IGroupInfoRepository ====================

    async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
        """获取 Discord 频道信息"""
        if not discord:
            return None

        try:
            channel_id = int(group_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            # 尝试获取 Guild 信息
            guild = getattr(channel, "guild", None)

            group_name = getattr(channel, "name", str(channel.id))
            if guild:
                # 如果是公会频道，可以用 Guild 信息补充
                member_count = guild.member_count
                owner_id = str(guild.owner_id)
            else:
                # 私信或群组私信
                member_count = len(getattr(channel, "recipients", [])) + 1  # +1 for bot
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
            logger.error(f"Discord 获取群组信息失败: {e}")
            return None

    async def get_group_list(self) -> List[str]:
        """获取机器人所在的所有频道 ID (仅列出 TextChannel)"""
        if not discord:
            return []

        try:
            # 遍历所有 Guilds 和 Channels
            channel_ids = []
            for guild in self._discord_client.guilds:
                for channel in guild.text_channels:
                    channel_ids.append(str(channel.id))
            return channel_ids
        except Exception as e:
            logger.error(f"Discord 获取群组列表失败: {e}")
            return []

    async def get_member_list(self, group_id: str) -> List[UnifiedMember]:
        """获取 Discord 服务器成员列表"""
        if not discord:
            return []

        try:
            channel_id = int(group_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            guild = getattr(channel, "guild", None)
            if not guild:
                # 非公会频道（如 DM），返回收件人
                members = []
                for user in getattr(channel, "recipients", []):
                    members.append(
                        UnifiedMember(
                            user_id=str(user.id),
                            nickname=user.display_name,
                            card=None,
                            role="member",
                            join_time=None,
                        )
                    )
                return members

            # 公会频道
            members = []
            # 注意：如果 member_count 很大，members 可能不全（取决于 intent 和 cache）
            # 需要启用 GUILD_MEMBERS intent
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
                        card=member.nick or member.global_name,  # 优先显示服务器昵称
                        role=role,
                        join_time=int(member.joined_at.timestamp())
                        if member.joined_at
                        else None,
                    )
                )
            return members
        except Exception as e:
            logger.error(f"Discord 获取成员列表失败: {e}")
            return []

    async def get_member_info(
        self,
        group_id: str,
        user_id: str,
    ) -> Optional[UnifiedMember]:
        """获取特定成员信息"""
        if not discord:
            return None

        try:
            channel_id = int(group_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            guild = getattr(channel, "guild", None)
            if not guild:
                # 私信，尝试 fetch user
                user = await self.bot.fetch_user(int(user_id))
                return UnifiedMember(
                    user_id=str(user.id),
                    nickname=user.name,
                    card=user.display_name,
                    role="member",
                    join_time=None,
                )

            member = guild.get_member(int(user_id))
            if not member:
                member = await guild.fetch_member(int(user_id))

            if not member:
                return None

            role = "member"
            if member.id == guild.owner_id:
                role = "owner"
            elif member.guild_permissions.administrator:
                role = "admin"

            return UnifiedMember(
                user_id=str(member.id),
                nickname=member.name,
                card=member.nick or member.global_name,
                role=role,
                join_time=int(member.joined_at.timestamp())
                if member.joined_at
                else None,
            )
        except Exception as e:
            logger.error(f"Discord 获取成员信息失败: {e}")
            return None

    # ==================== IAvatarRepository ====================

    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Discord 用户头像 URL"""
        if not discord:
            logger.warning("[群分析插件 DiscordAdapter] py-cord 未安装")
            return None

        try:
            logger.debug(f"[群分析插件 DiscordAdapter] 正在获取用户头像 {user_id}")
            if not self._discord_client:
                logger.warning("[群分析插件 DiscordAdapter] Discord 客户端未准备就绪")
                return None

            user = self._discord_client.get_user(int(user_id))
            if not user:
                logger.debug(
                    f"[群分析插件 DiscordAdapter] 用户 {user_id} 不在缓存中，正在获取..."
                )
                user = await self._discord_client.fetch_user(int(user_id))

            if user:
                # 调整 size 到最接近的 2 的幂次方
                allowed_sizes = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
                target_size = min(allowed_sizes, key=lambda x: abs(x - size))

                url = user.display_avatar.with_size(target_size).url
                logger.debug(
                    f"[群分析插件 DiscordAdapter] 获取用户头像 {user_id} 成功: {url}"
                )
                return url

            logger.warning(f"[群分析插件 DiscordAdapter] 用户 {user_id} 未找到")
            return None
        except Exception as e:
            logger.error(
                f"[群分析插件 DiscordAdapter] 获取用户头像 {user_id} 失败: {e}"
            )
            return None

    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Discord 用户头像 Base64 数据"""
        # 暂时只返回 None，让上层使用 URL
        return None

    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 Discord 服务器图标 URL"""
        if not discord:
            return None

        try:
            channel_id = int(group_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)

            guild = getattr(channel, "guild", None)
            if guild and guild.icon:
                allowed_sizes = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
                target_size = min(allowed_sizes, key=lambda x: abs(x - size))
                return guild.icon.with_size(target_size).url
            return None
        except Exception:
            return None

    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """批量获取 Discord 用户头像 URL"""
        return {
            user_id: await self.get_user_avatar_url(user_id, size)
            for user_id in user_ids
        }
