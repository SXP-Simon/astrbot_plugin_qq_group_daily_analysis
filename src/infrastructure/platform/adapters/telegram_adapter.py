"""
Telegram 平台适配器

支持 Telegram Bot API 的消息发送功能。
通过 AstrBot 的 message_history_manager 存储和读取消息历史。
"""

from datetime import datetime, timedelta
from io import BytesIO
from typing import TYPE_CHECKING, Any

from ....domain.value_objects.platform_capabilities import (
    PlatformCapabilities,
)
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ....domain.value_objects.unified_message import (
    MessageContent,
    MessageContentType,
    UnifiedMessage,
)
from ....utils.logger import logger
from ..base import PlatformAdapter

if TYPE_CHECKING:
    from astrbot.api.star import Context

# Telegram 依赖
try:
    from telegram.ext import ExtBot

    TELEGRAM_AVAILABLE = True
except ImportError:
    ExtBot = None
    TELEGRAM_AVAILABLE = False


class TelegramAdapter(PlatformAdapter):
    """
    Telegram Bot API 适配器

    实现 PlatformAdapter 接口，支持：
    - 消息发送（文本、图片、文件）
    - 头像获取
    - 群组信息获取
    - 消息历史（通过 AstrBot 的 message_history_manager）

    消息历史机制：
    - 消息通过拦截器存储到 AstrBot 数据库
    - fetch_messages 从数据库读取历史消息
    """

    def __init__(self, bot_instance: Any, config: dict | None = None):
        super().__init__(bot_instance, config)
        self._cached_client: ExtBot | None = None
        self._context: Context | None = None

        # 机器人自身 ID（用于消息过滤）
        self.bot_user_id = str(config.get("bot_user_id", "")) if config else ""

        # 尝试从配置获取 bot self ids 列表
        self.bot_self_ids: list[str] = []
        if config:
            ids = config.get("bot_self_ids", [])
            self.bot_self_ids = [str(i) for i in ids] if ids else []

    def set_context(self, context: "Context") -> None:
        """
        设置 AstrBot 上下文

        用于访问 message_history_manager 等核心服务。
        """
        self._context = context

    @property
    def _telegram_client(self) -> "ExtBot | None":
        """
        懒加载获取 Telegram 客户端

        支持多种获取路径，适应 AstrBot 不同版本。
        """
        if self._cached_client is not None:
            return self._cached_client

        if not TELEGRAM_AVAILABLE:
            logger.warning("python-telegram-bot 库未安装，Telegram 适配器不可用")
            return None

        # 路径 A: bot 本身就是 ExtBot
        if isinstance(self.bot, ExtBot):
            self._cached_client = self.bot
            return self._cached_client

        # 路径 B: bot.client
        if hasattr(self.bot, "client"):
            client = self.bot.client
            if isinstance(client, ExtBot):
                self._cached_client = client
                return self._cached_client

        # 路径 C: bot 有 send_message 方法（ExtBot 的特征）
        if hasattr(self.bot, "send_message") and hasattr(self.bot, "send_photo"):
            self._cached_client = self.bot
            return self._cached_client

        # 尝试从 bot 的其他属性获取
        for attr in ("_client", "telegram_client", "_telegram_client", "bot"):
            if hasattr(self.bot, attr):
                client = getattr(self.bot, attr)
                if hasattr(client, "send_message"):
                    self._cached_client = client
                    return self._cached_client

        logger.warning("无法从 bot_instance 获取 Telegram 客户端")
        return None

    def _init_capabilities(self) -> PlatformCapabilities:
        """返回 Telegram 平台能力声明"""
        # 通过数据库存储支持消息历史
        return PlatformCapabilities(
            platform_name="telegram",
            platform_version="bot_api_7.x",
            supports_message_history=True,  # 通过数据库支持
            max_message_history_days=7,  # 取决于存储时长
            max_message_count=1000,
            supports_group_list=False,
            supports_group_info=True,
            supports_member_list=True,
            supports_text_message=True,
            supports_image_message=True,
            supports_file_message=True,
            supports_reply_message=True,
            max_text_length=4096,
            max_image_size_mb=50.0,
            supports_edit=True,
            supports_user_avatar=True,
            supports_group_avatar=True,
            avatar_needs_api_call=True,
            avatar_sizes=(160, 320, 640),
        )

    # ==================== IMessageRepository ====================

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 100,
        before_id: str | None = None,
    ) -> list[UnifiedMessage]:
        """
        获取历史消息

        从 AstrBot 的 message_history_manager 读取存储的消息。
        消息需要事先通过拦截器存储到数据库。
        """
        if not self._context:
            logger.warning("[Telegram] 未设置 context，无法获取消息历史")
            return []

        try:
            # 从 message_history_manager 获取消息
            history_mgr = self._context.message_history_manager

            # 获取平台 ID（从 bot 实例获取）
            platform_id = self._get_platform_id()

            # 获取消息历史
            history_records = await history_mgr.get(
                platform_id=platform_id,
                user_id=group_id,
                page=1,
                page_size=max_count,
            )

            if not history_records:
                logger.info(
                    f"[Telegram] 群 {group_id} 没有存储的消息。"
                    f"提示：消息需要通过拦截器实时存储。"
                )
                return []

            # 时间过滤
            cutoff_time = datetime.now() - timedelta(days=days)

            messages = []
            for record in history_records:
                # 检查时间
                if record.created_at < cutoff_time:
                    continue

                # 转换为 UnifiedMessage
                msg = self._convert_history_record(record, group_id)
                if msg:
                    # 过滤机器人自己的消息
                    if self.bot_user_id and msg.sender_id == self.bot_user_id:
                        continue
                    if msg.sender_id in self.bot_self_ids:
                        continue
                    messages.append(msg)

            logger.info(
                f"[Telegram] 从数据库获取群 {group_id} 的消息: "
                f"{len(messages)}/{len(history_records)} 条"
            )

            return messages

        except Exception as e:
            logger.error(f"[Telegram] 获取消息历史失败: {e}")
            return []

    def _get_platform_id(self) -> str:
        """获取平台 ID"""
        # 尝试从 bot 实例获取
        if hasattr(self.bot, "meta"):
            meta = self.bot.meta()
            if hasattr(meta, "id"):
                return meta.id
        return "telegram"

    def _convert_history_record(
        self, record: Any, group_id: str
    ) -> UnifiedMessage | None:
        """
        将数据库记录转换为 UnifiedMessage
        """
        try:
            content = record.content
            if not content:
                return None

            # 提取消息内容
            message_parts = content.get("message", [])
            text_content = ""
            contents = []

            for part in message_parts:
                if isinstance(part, dict):
                    part_type = part.get("type", "")
                    if part_type == "plain" or part_type == "text":
                        text = part.get("text", "")
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
                                url=part.get("url", "")
                                or part.get("attachment_id", ""),
                            )
                        )
                    elif part_type == "at":
                        contents.append(
                            MessageContent(
                                type=MessageContentType.AT,
                                target_id=part.get("target_id", ""),
                            )
                        )

            if not contents:
                contents.append(
                    MessageContent(
                        type=MessageContentType.TEXT,
                        text=text_content,
                    )
                )

            return UnifiedMessage(
                message_id=str(record.id),
                sender_id=record.sender_id or "",
                sender_name=record.sender_name or "Unknown",
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

    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        """
        将统一消息格式转换为 OneBot 兼容格式

        用于向后兼容现有分析逻辑。
        """
        result = []
        for msg in messages:
            raw = {
                "message_id": msg.message_id,
                "group_id": msg.group_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card or "",
                },
                "message": [],
                "user_id": msg.sender_id,
            }

            # 转换消息内容
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    raw["message"].append(
                        {"type": "text", "data": {"text": content.text or ""}}
                    )
                elif content.type == MessageContentType.IMAGE:
                    raw["message"].append(
                        {"type": "image", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.AT:
                    raw["message"].append(
                        {"type": "at", "data": {"qq": content.target_id or ""}}
                    )

            result.append(raw)

        return result

    # ==================== IMessageSender ====================

    async def send_text(
        self,
        group_id: str,
        text: str,
        reply_to: str | None = None,
    ) -> bool:
        """发送文本消息"""
        client = self._telegram_client
        if not client:
            logger.error("[Telegram] 客户端未初始化，无法发送文本")
            return False

        try:
            # 处理群组话题 ID
            chat_id, message_thread_id = self._parse_group_id(group_id)

            kwargs: dict[str, Any] = {"chat_id": chat_id, "text": text}
            if message_thread_id:
                kwargs["message_thread_id"] = int(message_thread_id)
            if reply_to:
                kwargs["reply_to_message_id"] = int(reply_to)

            await client.send_message(**kwargs)
            return True
        except Exception as e:
            logger.error(f"[Telegram] 发送文本失败: {e}")
            return False

    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """发送图片消息"""
        client = self._telegram_client
        if not client:
            logger.error("[Telegram] 客户端未初始化，无法发送图片")
            return False

        try:
            chat_id, message_thread_id = self._parse_group_id(group_id)

            kwargs: dict[str, Any] = {"chat_id": chat_id}
            if message_thread_id:
                kwargs["message_thread_id"] = int(message_thread_id)
            if caption:
                kwargs["caption"] = caption

            # 处理本地文件或 URL
            if image_path.startswith(("http://", "https://")):
                # 远程 URL - 需要下载后发送
                try:
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            image_path, timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                kwargs["photo"] = BytesIO(data)
                            else:
                                # 尝试直接发送 URL
                                kwargs["photo"] = image_path
                except Exception as e:
                    logger.warning(f"[Telegram] 下载图片失败，尝试直接发送: {e}")
                    kwargs["photo"] = image_path
            else:
                # 本地文件
                kwargs["photo"] = open(image_path, "rb")

            await client.send_photo(**kwargs)

            # 关闭文件句柄
            if not isinstance(kwargs["photo"], (str, BytesIO)):
                kwargs["photo"].close()

            return True
        except Exception as e:
            logger.error(f"[Telegram] 发送图片失败: {e}")
            return False

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: str | None = None,
    ) -> bool:
        """发送文件消息"""
        client = self._telegram_client
        if not client:
            logger.error("[Telegram] 客户端未初始化，无法发送文件")
            return False

        try:
            import os

            chat_id, message_thread_id = self._parse_group_id(group_id)

            kwargs: dict[str, Any] = {"chat_id": chat_id}
            if message_thread_id:
                kwargs["message_thread_id"] = int(message_thread_id)
            if filename:
                kwargs["filename"] = filename
            else:
                kwargs["filename"] = os.path.basename(file_path)

            # 打开文件
            with open(file_path, "rb") as f:
                kwargs["document"] = f
                await client.send_document(**kwargs)

            return True
        except Exception as e:
            logger.error(f"[Telegram] 发送文件失败: {e}")
            return False

    async def send_forward_msg(self, group_id: str, nodes: list[dict]) -> bool:
        """
        发送合并转发消息

        Telegram 不支持原生转发消息链，转换为格式化文本发送。
        """
        if not nodes:
            return True

        lines = ["📊 **分析报告**\n"]
        for node in nodes:
            data = node.get("data", node)
            name = data.get("name", "AstrBot")
            content = data.get("content", "")
            if isinstance(content, list):
                # 消息链
                text_parts = []
                for seg in content:
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        text_parts.append(seg.get("data", {}).get("text", ""))
                content = "".join(text_parts)
            lines.append(f"**[{name}]**\n{content}\n")

        full_text = "\n".join(lines)

        # 分段发送（Telegram 限制 4096 字符）
        max_len = 4000
        if len(full_text) > max_len:
            parts = [
                full_text[i : i + max_len] for i in range(0, len(full_text), max_len)
            ]
            for part in parts:
                if not await self.send_text(group_id, part):
                    return False
            return True
        else:
            return await self.send_text(group_id, full_text)

    # ==================== IGroupInfoRepository ====================

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        """获取群组信息"""
        client = self._telegram_client
        if not client:
            return None

        try:
            chat_id, _ = self._parse_group_id(group_id)
            chat = await client.get_chat(chat_id=chat_id)

            return UnifiedGroup(
                group_id=str(chat.id),
                group_name=chat.title or "Unknown",
                member_count=await client.get_chat_member_count(chat_id) or 0,
                description=chat.description,
                platform="telegram",
            )
        except Exception as e:
            logger.debug(f"[Telegram] 获取群信息失败: {e}")
            return None

    async def get_group_list(self) -> list[str]:
        """
        获取群组列表

        Telegram Bot API 不支持获取群列表。
        """
        logger.debug("[Telegram] Bot API 不支持获取群列表")
        return []

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        """
        获取成员列表

        Telegram Bot API 对成员列表获取有限制。
        """
        client = self._telegram_client
        if not client:
            return []

        try:
            chat_id, _ = self._parse_group_id(group_id)
            # Telegram Bot API 需要使用 getChatAdministrators
            # 只能获取管理员列表，无法获取全部成员
            admins = await client.get_chat_administrators(chat_id=chat_id)

            members = []
            for admin in admins:
                user = admin.user
                members.append(
                    UnifiedMember(
                        user_id=str(user.id),
                        nickname=user.first_name or user.username or "Unknown",
                        card=user.username,
                        role="admin" if admin.status == "administrator" else "owner",
                    )
                )
            return members
        except Exception as e:
            logger.debug(f"[Telegram] 获取成员列表失败: {e}")
            return []

    async def get_member_info(
        self,
        group_id: str,
        user_id: str,
    ) -> UnifiedMember | None:
        """获取成员信息"""
        client = self._telegram_client
        if not client:
            return None

        try:
            chat_id, _ = self._parse_group_id(group_id)
            member = await client.get_chat_member(chat_id=chat_id, user_id=int(user_id))
            user = member.user

            role = "member"
            if member.status in ("creator", "owner"):
                role = "owner"
            elif member.status == "administrator":
                role = "admin"

            return UnifiedMember(
                user_id=str(user.id),
                nickname=user.first_name or user.username or "Unknown",
                card=user.username,
                role=role,
            )
        except Exception as e:
            logger.debug(f"[Telegram] 获取成员信息失败: {e}")
            return None

    # ==================== IAvatarRepository ====================

    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> str | None:
        """
        获取用户头像 URL

        Telegram 需要调用 API 获取头像文件。
        """
        client = self._telegram_client
        if not client:
            return None

        try:
            photos = await client.get_user_profile_photos(user_id=int(user_id), limit=1)
            if photos.photos:
                # 获取最大尺寸的头像
                photo_sizes = photos.photos[0]
                if photo_sizes:
                    # 选择最接近请求尺寸的
                    best = photo_sizes[-1]  # 通常最后一个是最大的
                    file = await client.get_file(best.file_id)
                    if file.file_path:
                        # 构建完整 URL
                        # 格式: https://api.telegram.org/file/bot<token>/<file_path>
                        # python-telegram-bot 的 File.file_path 属性通常只返回路径部分
                        # 需要手动拼接或使用 instance.file.file_path (取决于版本)

                        file_path = file.file_path
                        if file_path.startswith("http"):
                            return file_path

                        # 尝试构建完整 URL
                        if hasattr(client, "token"):
                            return f"https://api.telegram.org/file/bot{client.token}/{file_path}"

                        # 如果无法获取 token，返回 None
                        return None
            return None
        except Exception as e:
            logger.debug(f"[Telegram] 获取用户头像失败: {e}")
            return None

    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> str | None:
        """获取头像的 Base64 数据"""
        # 暂不实现，返回 None
        return None

    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> str | None:
        """获取群组头像 URL"""
        client = self._telegram_client
        if not client:
            return None

        try:
            chat_id, _ = self._parse_group_id(group_id)
            chat = await client.get_chat(chat_id=chat_id)

            if chat.photo:
                file = await client.get_file(chat.photo.big_file_id)
                if file.file_path:
                    file_path = file.file_path
                    if file_path.startswith("http"):
                        return file_path

                    if hasattr(client, "token"):
                        return f"https://api.telegram.org/file/bot{client.token}/{file_path}"

                    return None
            return None
        except Exception as e:
            logger.debug(f"[Telegram] 获取群头像失败: {e}")
            return None

    async def batch_get_avatar_urls(
        self,
        user_ids: list[str],
        size: int = 100,
    ) -> dict[str, str | None]:
        """批量获取头像 URL"""
        result = {}
        for uid in user_ids:
            result[uid] = await self.get_user_avatar_url(uid, size)
        return result

    # ==================== 辅助方法 ====================

    def _parse_group_id(self, group_id: str) -> tuple[str, str | None]:
        """
        解析群组 ID

        Telegram 话题群的 ID 格式为: "chat_id#thread_id"

        Returns:
            tuple[str, str | None]: (chat_id, message_thread_id)
        """
        if "#" in group_id:
            parts = group_id.split("#", 1)
            return parts[0], parts[1]
        return group_id, None
