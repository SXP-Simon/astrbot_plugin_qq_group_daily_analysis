"""
Telegram 平台适配器

支持 Telegram Bot API 的消息发送功能。
通过 AstrBot 的 message_history_manager 存储和读取消息历史。
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from ....domain.value_objects.platform_capabilities import (
    TELEGRAM_CAPABILITIES,
    PlatformCapabilities,
)
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ....utils.logger import logger
from ..base import PlatformAdapter
from .telegram_message_converter import TelegramMessageConverter

if TYPE_CHECKING:
    from astrbot.api.star import Context

    from ....domain.repositories.bot_client_protocol import (
        HistoryRecordProtocol,
        TelegramClientProtocol,
    )
    from ....domain.repositories.plugin_host_repository import PluginHostProtocol
    from ....domain.value_objects.unified_message import UnifiedMessage

# Telegram 依赖
try:
    from telegram.ext import ExtBot

    _telegram_available = True
except ImportError:
    ExtBot = None
    _telegram_available = False

TELEGRAM_AVAILABLE: bool = _telegram_available


TELEGRAM_AVATAR_NEGATIVE_CACHE_TTL = 600
TELEGRAM_AVATAR_NEGATIVE_CACHE_MAX_SIZE = 1024


class TelegramAdapter(PlatformAdapter):
    """Telegram Bot API 适配器。

    实现 PlatformAdapter 接口，支持：
    - 消息发送（文本、图片、文件）
    - 头像获取
    - 群组信息获取
    - 消息历史（通过 AstrBot 的 message_history_manager）
    """

    def __init__(
        self, bot_instance: object, config: dict[str, object] | None = None
    ) -> None:
        super().__init__(bot_instance, config)
        self._cached_client: TelegramClientProtocol | None = None
        self._context: Context | None = None

        # 机器人自身 ID（用于消息过滤）
        self.bot_user_id = str(config.get("bot_user_id", "")) if config else ""

        # 尝试从配置获取 bot self ids 列表
        self.bot_self_ids: list[str] = []
        if config:
            ids = config.get("bot_self_ids", [])
            self.bot_self_ids = [str(i) for i in ids] if isinstance(ids, list) else []
            self._plugin_instance = config.get("plugin_instance")
        else:
            self._plugin_instance = None
        self._platform_id = str(config.get("platform_id", "")).strip() if config else ""
        # user_id -> (expires_at, reason)
        self._avatar_negative_cache: dict[str, tuple[float, str]] = {}

    def set_context(self, context: Context | object) -> None:
        """设置 AstrBot 上下文。

        用于访问 message_history_manager 等核心服务。
        """
        if hasattr(context, "message_history_manager") or hasattr(context, "get_event_queue"):
            self._context = context  # type: ignore[assignment]

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
                registry = getattr(self._plugin_instance, "platform_group_registry", None)
                if registry is not None and hasattr(registry, "get_seen_groups"):
                    kv_groups = await registry.get_seen_groups(self._platform_id)
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
    def _telegram_client(self) -> TelegramClientProtocol | None:
        """懒加载获取 Telegram 客户端。

        支持多种获取路径，适应 AstrBot 不同版本。
        """
        if self._cached_client is not None:
            return self._cached_client

        if not TELEGRAM_AVAILABLE:
            logger.warning("python-telegram-bot 库未安装，Telegram 适配器不可用")
            return None

        # 路径 A: bot 本身就是 ExtBot
        if ExtBot is not None and isinstance(self.bot, ExtBot):
            self._cached_client = self.bot  # type: ignore[assignment]
            return self._cached_client

        # 路径 B: bot.client
        if hasattr(self.bot, "client"):
            client = getattr(self.bot, "client", None)
            if ExtBot is not None and isinstance(client, ExtBot):
                self._cached_client = client  # type: ignore[assignment]
                return self._cached_client

        # 路径 C: bot 有 send_message 方法（ExtBot 的特征）
        if hasattr(self.bot, "send_message") and hasattr(self.bot, "send_photo"):
            self._cached_client = self.bot  # type: ignore[assignment]
            return self._cached_client

        # 尝试从 bot 的其他属性获取
        for attr in ("_client", "telegram_client", "_telegram_client", "bot"):
            if hasattr(self.bot, attr):
                client = getattr(self.bot, attr)
                if hasattr(client, "send_message"):
                    self._cached_client = client  # type: ignore[assignment]
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
        since_ts: int | float | None = None,
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

            cutoff_time = self.calculate_effective_cutoff_datetime(
                days=days, since_ts=since_ts, tz=UTC
            )
            target_count = max(1, int(max_count))
            page_size = target_count
            current_page = 1

            messages: list[UnifiedMessage] = []
            seen_message_ids: set[str] = set()
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
                # 先用当前页已有的有效昵称预热缓存，减少额外 API 请求
                for record in history_records:
                    sender_id = str(getattr(record, "sender_id", "") or "").strip()
                    sender_name = str(getattr(record, "sender_name", "") or "").strip()
                    if (
                        sender_id
                        and not TelegramMessageConverter.is_placeholder_sender_name(
                            sender_name, sender_id
                        )
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
                        record_time = record_time.replace(tzinfo=UTC)
                    if oldest_record_time is None or record_time < oldest_record_time:
                        oldest_record_time = record_time
                    if record_time < cutoff_time:
                        continue

                    msg = TelegramMessageConverter.to_unified_message(record, group_id)
                    if not msg:
                        continue

                    # 过滤机器人自己的消息
                    if self.bot_user_id and msg.sender_id == self.bot_user_id:
                        continue
                    if msg.sender_id in self.bot_self_ids:
                        continue

                    msg = await TelegramMessageConverter.fix_sender_name_if_needed(
                        group_id, msg, sender_name_cache, self.get_member_info
                    )
                    if msg.message_id in seen_message_ids:
                        continue
                    seen_message_ids.add(msg.message_id)
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

        if self.config:
            config_platform_id = str(self.config.get("platform_id", "")).strip()
            if config_platform_id:
                return config_platform_id

        # 尝试从 bot 实例获取
        meta_func = getattr(self.bot, "meta", None)
        if callable(meta_func):
            try:
                meta = meta_func()
                if hasattr(meta, "id"):
                    return str(getattr(meta, "id", "telegram"))
            except Exception:
                pass
        return "telegram"

    @staticmethod
    def _is_placeholder_sender_name(name: str | None, sender_id: str | None) -> bool:
        """判断 sender_name 是否属于占位值（委托 TelegramMessageConverter）。"""
        return TelegramMessageConverter.is_placeholder_sender_name(name, sender_id)

    async def _fix_sender_name_if_needed(
        self,
        group_id: str,
        msg: UnifiedMessage,
        sender_name_cache: dict[str, str],
    ) -> UnifiedMessage:
        """若 sender_name 是占位值，尝试通过 get_member_info 修复（委托 TelegramMessageConverter）。"""
        return await TelegramMessageConverter.fix_sender_name_if_needed(
            group_id, msg, sender_name_cache, self.get_member_info
        )

    def _convert_history_record(
        self, record: HistoryRecordProtocol, group_id: str
    ) -> UnifiedMessage | None:
        """将数据库记录转换为 UnifiedMessage（委托 TelegramMessageConverter）。"""
        return TelegramMessageConverter.to_unified_message(record, group_id)

    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        """将统一消息格式转换为 OneBot 兼容格式（委托 TelegramMessageConverter）。

        用于向后兼容现有分析逻辑。
        """
        return TelegramMessageConverter.to_raw_format(messages)

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

            await client.send_message(
                chat_id=chat_id,
                text=text,
                message_thread_id=int(message_thread_id) if message_thread_id else None,
                reply_to_message_id=int(reply_to) if reply_to else None,
            )
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
            file_obj: BytesIO | str | None = None
            is_temp_obj = False

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

                    async with (
                        aiohttp.ClientSession() as session,
                        session.get(
                            image_path, timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp,
                    ):
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
                    file_obj = BytesIO(Path(image_path).read_bytes())
                    is_temp_obj = True
                else:
                    file_obj = image_path

            # 2. 发送图片
            try:
                await client.send_photo(
                    chat_id=chat_id,
                    photo=file_obj,
                    caption=caption if caption else None,
                    message_thread_id=int(message_thread_id) if message_thread_id else None,
                )
            finally:
                if is_temp_obj and isinstance(file_obj, BytesIO):
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
            file_obj: BytesIO | str | None = None
            is_temp_obj = False

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
                file_obj = BytesIO(Path(file_path).read_bytes())
                is_temp_obj = True
                if not filename:
                    filename = os.path.basename(file_path)
            else:
                # 可能是 URL 或缓存 ID
                file_obj = file_path
                if not filename:
                    filename = "file"

            try:
                await client.send_document(
                    chat_id=chat_id,
                    document=file_obj,
                    filename=filename,
                    message_thread_id=int(message_thread_id) if message_thread_id else None,
                )
            finally:
                if is_temp_obj and isinstance(file_obj, BytesIO):
                    file_obj.close()

            return True
        except Exception as e:
            logger.error(f"[Telegram] 发送文件失败: {e}")
            return False

    async def send_forward_msg(self, group_id: str, nodes: list[dict]) -> bool:
        """发送合并转发消息。

        Telegram 不支持原生转发消息链，转换为格式化文本发送。
        """
        if not nodes:
            return True

        full_text = TelegramMessageConverter.format_forward_nodes_to_text(nodes)

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
            logger.warning(
                f"[Telegram] 获取用户头像失败 uid={user_id}: Telegram 客户端未初始化"
            )
            return None

        user_id_str = str(user_id).strip()
        cached_reason = self._get_avatar_negative_cache_reason(user_id_str)
        if cached_reason:
            logger.debug(
                f"[Telegram] 跳过用户头像获取 uid={user_id_str}: negative cache 命中，"
                f"上次失败原因: {cached_reason}"
            )
            return None

        try:
            tg_user_id = int(user_id_str)
        except (TypeError, ValueError):
            reason = f"用户 ID 不是有效整数: {user_id!r}"
            self._remember_avatar_negative(user_id_str, reason)
            logger.warning(f"[Telegram] 获取用户头像失败 uid={user_id}: {reason}")
            return None

        try:
            photos = await client.get_user_profile_photos(user_id=tg_user_id, limit=1)
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
                        reason = "get_file 返回相对 file_path，但 client 没有 token，无法拼接下载 URL"
                        self._remember_avatar_negative(user_id_str, reason)
                        logger.warning(
                            f"[Telegram] 获取用户头像失败 uid={user_id_str}: {reason}"
                        )
                        return None
                    reason = "get_file 未返回 file_path"
                    self._remember_avatar_negative(user_id_str, reason)
                    logger.warning(
                        f"[Telegram] 获取用户头像失败 uid={user_id_str}: {reason}"
                    )
                    return None
                reason = "get_user_profile_photos 返回的首张头像没有可用尺寸"
                self._remember_avatar_negative(user_id_str, reason)
                logger.info(f"[Telegram] 获取用户头像失败 uid={user_id_str}: {reason}")
                return None
            reason = "get_user_profile_photos 返回空列表，用户可能没有公开头像或隐私设置不可见"
            self._remember_avatar_negative(user_id_str, reason)
            logger.info(f"[Telegram] 获取用户头像失败 uid={user_id_str}: {reason}")
            return None
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            self._remember_avatar_negative(user_id_str, reason)
            logger.warning(f"[Telegram] 获取用户头像失败 uid={user_id_str}: {reason}")
            return None

    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> str | None:
        """获取头像的 Base64 数据"""
        # 暂不实现，返回 None
        logger.debug(
            f"[Telegram] 获取用户头像数据失败 uid={user_id}: get_user_avatar_data 暂未实现"
        )
        return None

    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> str | None:
        """获取群组头像 URL"""
        client = self._telegram_client
        if not client:
            logger.warning(
                f"[Telegram] 获取群头像失败 group_id={group_id}: Telegram 客户端未初始化"
            )
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

                    logger.warning(
                        f"[Telegram] 获取群头像失败 group_id={group_id}: "
                        "get_file 返回相对 file_path，但 client 没有 token，无法拼接下载 URL"
                    )
                    return None
                logger.warning(
                    f"[Telegram] 获取群头像失败 group_id={group_id}: get_file 未返回 file_path"
                )
                return None
            logger.info(
                f"[Telegram] 获取群头像失败 group_id={group_id}: 群组未设置头像或 bot 不可见"
            )
            return None
        except Exception as e:
            logger.warning(
                f"[Telegram] 获取群头像失败 group_id={group_id}: {type(e).__name__}: {e}"
            )
            return None

    def _prune_avatar_negative_cache(self) -> None:
        """清理过期项并限制 negative cache 大小，避免长期运行时无界增长。"""
        cache = self._avatar_negative_cache
        if not cache:
            return

        now = time.monotonic()
        expired_keys = [
            user_id
            for user_id, (expires_at, _reason) in cache.items()
            if expires_at <= now
        ]
        for user_id in expired_keys:
            cache.pop(user_id, None)

        overflow = len(cache) - TELEGRAM_AVATAR_NEGATIVE_CACHE_MAX_SIZE
        if overflow <= 0:
            return

        for user_id, _ in sorted(cache.items(), key=lambda item: item[1][0])[:overflow]:
            cache.pop(user_id, None)

    def _get_avatar_negative_cache_reason(self, user_id: str) -> str | None:
        self._prune_avatar_negative_cache()
        cached = self._avatar_negative_cache.get(user_id)
        if not cached:
            return None

        expires_at, reason = cached
        if time.monotonic() >= expires_at:
            self._avatar_negative_cache.pop(user_id, None)
            return None
        return reason

    def _remember_avatar_negative(self, user_id: str, reason: str) -> None:
        self._prune_avatar_negative_cache()
        self._avatar_negative_cache[user_id] = (
            time.monotonic() + TELEGRAM_AVATAR_NEGATIVE_CACHE_TTL,
            reason,
        )
        self._prune_avatar_negative_cache()

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

    @staticmethod
    def _parse_group_id(group_id: str) -> tuple[str, str | None]:
        """解析群组 ID（委托 TelegramMessageConverter）。

        Telegram 话题群的 ID 格式为: "chat_id#thread_id"。

        Returns:
            tuple[str, str | None]: (chat_id, message_thread_id)
        """
        return TelegramMessageConverter.parse_group_id(group_id)
