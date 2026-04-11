"""
Telegram 平台适配器

支持 Telegram Bot API 的消息发送功能。
通过 AstrBot 的 message_history_manager 存储和读取消息历史。
"""

import asyncio
import base64
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import TYPE_CHECKING, Any

from ....domain.value_objects.platform_capabilities import (
    TELEGRAM_CAPABILITIES,
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
        self._cached_client: Any = None
        self._context: Context | None = None

        # 机器人自身 ID（用于消息过滤）
        self.bot_user_id = str(config.get("bot_user_id", "")) if config else ""

        # 尝试从配置获取 bot self ids 列表
        self.bot_self_ids: list[str] = []
        if config:
            ids = config.get("bot_self_ids", [])
            self.bot_self_ids = [str(i) for i in ids] if ids else []
            self._plugin_instance = config.get("plugin_instance")
        else:
            self._plugin_instance = None
        self._platform_id = str(config.get("platform_id", "")).strip() if config else ""

    def set_context(self, context: "Context") -> None:
        """
        设置 AstrBot 上下文

        用于访问 message_history_manager 等核心服务。
        """
        self._context = context

    def _init_capabilities(self) -> PlatformCapabilities:
        """返回 Telegram 平台能力声明"""
        return TELEGRAM_CAPABILITIES

    async def get_group_list(self) -> list[str]:
        """
        获取群组列表

        Telegram Bot API 不支持直接获取群列表。
        因此这里尝试结合多种策略：
        1. 尝试调用 API (如果未来支持)
        2. 回退：从插件的 KV 存储中获取已知群组 (需注入插件实例)
        """
        groups = []

        # 1. 尝试 API (目前 python-telegram-bot 不支持直接列出所有 chat)
        # 如果 client 有扩展方法或未来支持，可在此实现

        # 2. 回退：使用 KV 注册表
        if not groups and self._plugin_instance:
            try:
                # 检查插件实例是否有 get_telegram_seen_group_ids 方法
                if hasattr(self._plugin_instance, "get_telegram_seen_group_ids"):
                    kv_groups = await self._plugin_instance.get_telegram_seen_group_ids(
                        self._platform_id
                    )
                    if kv_groups:
                        groups.extend(kv_groups)
                        logger.debug(
                            f"[Telegram] 通过 KV 回退获取到 {len(kv_groups)} 个群组"
                        )
            except Exception as e:
                logger.warning(f"[Telegram] KV 回退获取群列表失败: {e}")

        if not groups:
            logger.debug("[Telegram] 无法获取群列表 (API不支持且无KV记录)")

        return list(set(groups))

    @property
    def _telegram_client(self) -> Any:
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
        if ExtBot is not None and isinstance(self.bot, ExtBot):
            self._cached_client = self.bot
            return self._cached_client

        # 路径 B: bot.client
        if hasattr(self.bot, "client"):
            client = self.bot.client
            if ExtBot is not None and isinstance(client, ExtBot):
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

    # ==================== IMessageRepository ====================

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 100,
        before_id: str | None = None,
        since_ts: int | None = None,
    ) -> list[UnifiedMessage]:
        """
        获取历史消息。

        从 AstrBot 的 message_history_manager 读取存储的消息。
        """
        if not self._context:
            logger.warning("[Telegram] 未设置 context，无法获取消息历史")
            return []

        try:
            history_mgr = self._context.message_history_manager

            platform_id = self._get_platform_id()
            logger.info(
                f"[Telegram] 正在获取群 {group_id} 的历史消息，使用 platform_id: {platform_id}"
            )
            before_id_int: int | None = None
            if before_id:
                try:
                    before_id_int = int(before_id)
                except (TypeError, ValueError):
                    logger.warning(f"[Telegram] before_id invalid: {before_id}")

            if since_ts and since_ts > 0:
                # 统一使用 UTC 以兼容数据库记录的时间存储
                cutoff_time = datetime.fromtimestamp(since_ts, timezone.utc)
            else:
                cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
            target_count = max(1, int(max_count))
            page_size = target_count
            current_page = 1

            messages: list[UnifiedMessage] = []
            sender_name_cache: dict[str, str] = {}
            total_records_loaded = 0

            while len(messages) < target_count:
                history_records = await history_mgr.get(
                    platform_id=platform_id,
                    user_id=group_id,
                    page=current_page,
                    page_size=page_size,
                )
                if not history_records:
                    if current_page == 1:
                        logger.info(
                            f"[Telegram] 群 {group_id} 没有存储的消息。"
                            f"提示：消息需要通过拦截器实时存储。"
                        )
                    break

                total_records_loaded += len(history_records)

                # 先用当前页已有的有效昵称预热缓存，减少额外 API 请求
                for record in history_records:
                    sender_id = str(getattr(record, "sender_id", "") or "").strip()
                    sender_name = str(getattr(record, "sender_name", "") or "").strip()
                    if sender_id and not self._is_placeholder_sender_name(
                        sender_name, sender_id
                    ):
                        sender_name_cache[sender_id] = sender_name

                oldest_record_time: datetime | None = None
                for record in history_records:
                    if before_id_int is not None:
                        try:
                            rec_id = getattr(record, "id", None)
                            if rec_id is not None and int(rec_id) >= before_id_int:
                                continue
                        except (TypeError, ValueError):
                            pass

                    record_time = getattr(record, "created_at", None)
                    if not record_time:
                        continue
                    if record_time.tzinfo is None:
                        record_time = record_time.replace(tzinfo=timezone.utc)
                    if oldest_record_time is None or record_time < oldest_record_time:
                        oldest_record_time = record_time
                    if record_time < cutoff_time:
                        continue

                    msg = self._convert_history_record(record, group_id)
                    if not msg:
                        continue

                    # 过滤机器人自己的消息
                    if self.bot_user_id and msg.sender_id == self.bot_user_id:
                        continue
                    if msg.sender_id in self.bot_self_ids:
                        continue

                    msg = await self._fix_sender_name_if_needed(
                        group_id, msg, sender_name_cache
                    )
                    messages.append(msg)

                # 当前页完整处理后已足够，停止继续翻更旧页面。
                if len(messages) >= target_count:
                    break

                # 下一页一定更旧，若当前页最旧记录已越过时间窗口则可提前停止
                if oldest_record_time and oldest_record_time < cutoff_time:
                    break
                if len(history_records) < page_size:
                    break
                current_page += 1

            messages.sort(key=lambda m: m.timestamp)
            if len(messages) > target_count:
                messages = messages[-target_count:]

            logger.info(
                f"[Telegram] 从数据库获取群 {group_id} 的消息: "
                f"{len(messages)}/{total_records_loaded} 条"
            )
            return messages

        except Exception as e:
            logger.error(f"[Telegram] 获取消息历史失败: {e}")
            return []

    def _get_platform_id(self) -> str:
        """获取平台 ID"""
        if self._platform_id:
            return self._platform_id

        if isinstance(self.config, dict):
            config_platform_id = str(self.config.get("platform_id", "")).strip()
            if config_platform_id:
                return config_platform_id

        # 尝试从 bot 实例获取
        if hasattr(self.bot, "meta") and callable(self.bot.meta):
            try:
                meta = self.bot.meta()  # type: ignore
                if hasattr(meta, "id"):
                    return str(getattr(meta, "id", "telegram"))
            except Exception:
                pass
        return "telegram"

    @staticmethod
    def _is_placeholder_sender_name(name: str | None, sender_id: str | None) -> bool:
        """判断 sender_name 是否属于占位值。"""
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized.lower() in {"unknown", "none", "null", "nil", "undefined"}:
            return True
        if sender_id and normalized == str(sender_id).strip():
            return True
        return False

    async def _fix_sender_name_if_needed(
        self,
        group_id: str,
        msg: UnifiedMessage,
        sender_name_cache: dict[str, str],
    ) -> UnifiedMessage:
        """
        如果 sender_name 是占位值，尝试通过 get_member_info 修复。

        说明：
        - 兼容历史脏数据（sender_name 写成 user_id / Unknown）
        - 使用 sender_id 级缓存，避免重复请求 Telegram API
        """
        if not self._is_placeholder_sender_name(msg.sender_name, msg.sender_id):
            return msg

        sender_id = str(msg.sender_id)
        if sender_id in sender_name_cache:
            cached_name = sender_name_cache[sender_id]
            if cached_name == msg.sender_name:
                return msg
            return replace(msg, sender_name=cached_name)

        resolved_name = msg.sender_name
        try:
            member = await self.get_member_info(group_id, sender_id)
            if member:
                candidate = str(member.nickname or "").strip()
                if self._is_placeholder_sender_name(candidate, sender_id):
                    candidate = str(member.card or "").strip()
                if not self._is_placeholder_sender_name(candidate, sender_id):
                    resolved_name = candidate
        except Exception as e:
            logger.debug(f"[Telegram] 修复 sender_name 失败 (uid={sender_id}): {e}")

        sender_name_cache[sender_id] = resolved_name
        if resolved_name == msg.sender_name:
            return msg
        return replace(msg, sender_name=resolved_name)

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
                        {"type": "at", "data": {"qq": content.at_user_id or ""}}
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
            file_obj: Any = None
            is_temp_obj = False

            kwargs: dict[str, Any] = {"chat_id": chat_id}
            if message_thread_id:
                kwargs["message_thread_id"] = int(message_thread_id)
            if caption:
                kwargs["caption"] = caption

            # 1. 统一处理输入源 (Base64 / URL / Local File)
            if image_path.startswith("base64://"):
                data = base64.b64decode(image_path[len("base64://") :])
                file_obj = BytesIO(data)
                is_temp_obj = True
            elif image_path.startswith("data:"):
                parts = image_path.split(",", 1)
                if len(parts) == 2:
                    data = base64.b64decode(parts[1])
                    file_obj = BytesIO(data)
                    is_temp_obj = True
            elif image_path.startswith(("http://", "https://")):
                try:
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            image_path, timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                file_obj = BytesIO(data)
                                is_temp_obj = True
                            else:
                                file_obj = image_path  # 尝试直接发 URL
                except Exception as e:
                    logger.warning(f"[Telegram] 下载图片失败，尝试直接发送: {e}")
                    file_obj = image_path
            else:
                # 本地文件
                if os.path.exists(image_path):
                    file_obj = open(image_path, "rb")
                    is_temp_obj = True
                else:
                    file_obj = image_path

            # 2. 发送图片
            kwargs["photo"] = file_obj
            try:
                await client.send_photo(**kwargs)
            finally:
                if is_temp_obj and hasattr(file_obj, "close"):
                    file_obj.close()

            return True

        except Exception as e:
            err_msg = str(e)
            # Photo_invalid_dimensions: Telegram 报错提示图片长宽比例或总尺寸不合规
            if (
                "Photo_invalid_dimensions" in err_msg
                or "Photo invalid dimensions" in err_msg
            ):
                logger.warning("[Telegram] 图片尺寸超限，正在尝试以文件形式发送...")
                # 构造一个更有意义的文件名
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = f"analysis_report_{group_id}_{ts}.png"
                return await self.send_file(group_id, image_path, filename=fn)

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
            chat_id, message_thread_id = self._parse_group_id(group_id)
            file_obj: Any = None
            is_temp_obj = False

            kwargs: dict[str, Any] = {"chat_id": chat_id}
            if message_thread_id:
                kwargs["message_thread_id"] = int(message_thread_id)

            # 1. 统一处理输入源 (Base64 / Local File)
            if file_path.startswith("base64://"):
                data = base64.b64decode(file_path[len("base64://") :])
                file_obj = BytesIO(data)
                is_temp_obj = True
                if not filename:
                    filename = "file.png"
            elif file_path.startswith("data:"):
                parts = file_path.split(",", 1)
                if len(parts) == 2:
                    data = base64.b64decode(parts[1])
                    file_obj = BytesIO(data)
                    is_temp_obj = True
                    if not filename:
                        filename = "file.png"
            elif os.path.isfile(file_path):
                file_obj = open(file_path, "rb")
                is_temp_obj = True
                if not filename:
                    filename = os.path.basename(file_path)
            else:
                # 可能是 URL 或缓存 ID
                file_obj = file_path
                if not filename:
                    filename = "file"

            kwargs["document"] = file_obj
            kwargs["filename"] = filename

            try:
                await client.send_document(**kwargs)
            finally:
                if is_temp_obj and hasattr(file_obj, "close"):
                    file_obj.close()

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
                        nickname=user.full_name
                        or user.first_name
                        or user.username
                        or "Unknown",
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
                nickname=user.full_name
                or user.first_name
                or user.username
                or "Unknown",
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
        if not user_ids:
            return {}

        # 适度并发，避免串行等待过久，也避免瞬时过载 Telegram API
        semaphore = asyncio.Semaphore(8)

        async def _fetch_avatar(uid: str) -> tuple[str, str | None]:
            async with semaphore:
                try:
                    return uid, await self.get_user_avatar_url(uid, size)
                except Exception as e:
                    logger.debug(f"[Telegram] 批量获取头像失败 uid={uid}: {e}")
                    return uid, None

        pairs = await asyncio.gather(*(_fetch_avatar(uid) for uid in user_ids))
        return dict(pairs)

    async def set_reaction(
        self, group_id: str, message_id: str, emoji: str | int, is_add: bool = True
    ) -> bool:
        """
        Telegram 实现消息回应。
        """
        client = self._telegram_client
        if not client:
            return False

        try:
            chat_id, _ = self._parse_group_id(group_id)

            # 只有开启了库支持且版本符合时才尝试。set_message_reaction 是 Bot API 7.0 (PTB 20.8+) 特性。
            if not hasattr(client, "set_message_reaction"):
                return False

            if not is_add:
                try:
                    from telegram import ReactionTypeEmoji

                    await client.set_message_reaction(
                        chat_id=chat_id,
                        message_id=int(message_id),
                        reaction=[],
                    )
                    return True
                except ImportError:
                    await client.set_message_reaction(
                        chat_id=chat_id,
                        message_id=int(message_id),
                        reaction=None,
                    )
                    return True

            reaction_key = str(emoji)
            candidates = {
                "analysis_started": ("👀", "🤔", "👍"),
                "analysis_done": ("👌", "👍", "🎉"),
                "🔍": ("👀", "🤔", "👍"),
                "📊": ("👌", "👍", "🎉"),
                "289": ("👀", "🤔", "👍"),
                "124": ("👌", "👍", "🎉"),
                "424": ("👌", "👍", "🎉"),
                "✅": ("👌", "👍", "🎉"),
            }.get(reaction_key, (reaction_key,))

            try:
                from telegram import ReactionTypeEmoji

                for candidate in candidates:
                    try:
                        await client.set_message_reaction(
                            chat_id=chat_id,
                            message_id=int(message_id),
                            reaction=[ReactionTypeEmoji(emoji=candidate)],
                        )
                        return True
                    except Exception:
                        continue
            except ImportError:
                for candidate in candidates:
                    try:
                        await client.set_message_reaction(
                            chat_id=chat_id,
                            message_id=int(message_id),
                            reaction=candidate,
                        )
                        return True
                    except Exception:
                        continue

            logger.debug(
                f"[Telegram] set_reaction 未匹配到可用表情: emoji={emoji}, candidates={candidates}"
            )
            return False
        except Exception as e:
            logger.debug(f"[Telegram] set_reaction 失败: {e}")
            return False

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
