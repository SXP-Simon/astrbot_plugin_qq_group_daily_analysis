# pyright: reportMissingImports=false, reportConstantRedefinition=false
# mypy: ignore-errors
"""Telegram 模板预览交互处理。"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from ....utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from telegram import CallbackQuery as TelegramCallbackQuery
    from telegram import InlineKeyboardMarkup as TelegramInlineKeyboardMarkup
    from telegram import Update as TelegramUpdate

    from ....application.commands.template_command_service import TemplateCommandService
    from ...config.config_manager import ConfigManager
else:
    TelegramCallbackQuery = object
    TelegramInlineKeyboardMarkup = object
    TelegramUpdate = object

try:
    from telegram import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        InputMediaDocument,
        InputMediaPhoto,
    )
    from telegram.error import BadRequest
    from telegram.ext import CallbackQueryHandler

    TELEGRAM_RUNTIME_AVAILABLE = True
except Exception:
    TELEGRAM_RUNTIME_AVAILABLE = False
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    InputMediaPhoto = None
    InputMediaDocument = None
    BadRequest = Exception
    CallbackQueryHandler = None


@dataclass
class _PreviewSession:
    token: str
    platform_id: str
    chat_id: int | str
    message_thread_id: int | None
    message_id: int
    requester_id: int
    templates: list[str]
    index: int
    created_at: float

    @property
    def current_template(self) -> str:
        return self.templates[self.index]


class _TelegramClientLike(Protocol):
    async def send_photo(self, *args: object, **kwargs: object) -> object: ...
    async def send_document(self, *args: object, **kwargs: object) -> object: ...


class _TelegramApplicationLike(Protocol):
    bot: object | None

    def add_handler(self, handler: object) -> None: ...
    def remove_handler(self, handler: object) -> None: ...


class _TelegramPlatformLike(Protocol):
    application: _TelegramApplicationLike | None
    metadata: object | None
    client: object | None

    def meta(self) -> object: ...
    def get_client(self) -> object: ...


class _TelegramPlatformManagerLike(Protocol):
    def get_insts(self) -> list[object]: ...


class _TelegramContextLike(Protocol):
    platform_manager: _TelegramPlatformManagerLike


class TelegramTemplatePreviewHandler:
    """Telegram 按钮预览处理器（←/确定/→）。"""

    _SESSION_TTL_SECONDS = 2 * 60 * 60
    _MAX_SESSIONS = 200
    _CONNECT_TIMEOUT = 20
    _READ_TIMEOUT = 120
    _WRITE_TIMEOUT = 120
    _POOL_TIMEOUT = 20

    def __init__(
        self,
        config_manager: ConfigManager,
        template_service: TemplateCommandService,
    ):
        self.config_manager = config_manager
        self.template_service = template_service
        self._sessions: dict[str, _PreviewSession] = {}
        self._registered_platform_ids: set[str] = set()
        self._handlers: dict[str, tuple[_TelegramApplicationLike, object]] = {}
        self._platform_clients: dict[str, _TelegramClientLike] = {}
        self._callback_prefix = f"qda_tpl_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def supports(event: AstrMessageEvent) -> bool:
        """判断是否 Telegram 事件。"""
        try:
            return (event.get_platform_name() or "").lower() == "telegram"
        except Exception:
            return False

    # 向后兼容旧调用名
    is_telegram_event = supports

    async def ensure_callback_handlers_registered(self, context: object) -> None:
        """为所有 Telegram 平台注册按钮回调处理器。"""
        if not TELEGRAM_RUNTIME_AVAILABLE:
            return
        if not context or not hasattr(context, "platform_manager"):
            return
        typed_context = cast(_TelegramContextLike, context)

        platforms = typed_context.platform_manager.get_insts()
        seen_platform_ids: set[str] = set()
        for platform in platforms:
            platform_id, platform_name = self._extract_platform_meta(platform)
            if platform_name != "telegram":
                continue
            if not platform_id:
                continue

            seen_platform_ids.add(platform_id)
            client = self._extract_platform_client(platform)
            if client is not None:
                self._platform_clients[platform_id] = client

            typed_platform = cast(_TelegramPlatformLike, platform)
            application = typed_platform.application
            if not application:
                continue

            existing = self._handlers.get(platform_id)
            if existing:
                old_application, old_handler = existing
                if old_application is application:
                    self._registered_platform_ids.add(platform_id)
                    continue

                # 平台对象热替换：解绑旧 application 上的 handler 后重绑
                try:
                    old_application.remove_handler(old_handler)
                    logger.info(
                        f"[TemplatePreview][Telegram] 检测到 application 变更，已解绑旧回调: platform_id={platform_id}"
                    )
                except Exception as e:
                    logger.debug(
                        f"[TemplatePreview][Telegram] 解绑旧回调失败: platform_id={platform_id}, err={e}"
                    )
                self._handlers.pop(platform_id, None)
                self._registered_platform_ids.discard(platform_id)

            try:
                if CallbackQueryHandler is None:
                    continue
                handler = CallbackQueryHandler(
                    self._on_callback_query,
                    pattern=rf"^{re.escape(self._callback_prefix)}:",
                )
                application.add_handler(handler)
                self._registered_platform_ids.add(platform_id)
                self._handlers[platform_id] = (application, handler)
                logger.info(
                    f"[TemplatePreview][Telegram] 已注册回调处理器: platform_id={platform_id}"
                )
            except Exception as e:
                logger.warning(
                    f"[TemplatePreview][Telegram] 注册回调处理器失败: platform_id={platform_id}, err={e}"
                )

        # 兜底清理：平台下线后移除残留 handler，避免资源泄漏
        stale_ids = [
            platform_id
            for platform_id in list(self._handlers.keys())
            if platform_id not in seen_platform_ids
        ]
        for stale_platform_id in stale_ids:
            old_application, old_handler = self._handlers.pop(stale_platform_id)
            try:
                old_application.remove_handler(old_handler)
                logger.info(
                    f"[TemplatePreview][Telegram] 已清理离线平台回调: platform_id={stale_platform_id}"
                )
            except Exception as e:
                logger.debug(
                    f"[TemplatePreview][Telegram] 清理离线平台回调失败: platform_id={stale_platform_id}, err={e}"
                )
            self._registered_platform_ids.discard(stale_platform_id)
            self._platform_clients.pop(stale_platform_id, None)

    async def unregister_callback_handlers(self) -> None:
        """卸载已注册的回调处理器（插件终止时调用）。"""
        if not TELEGRAM_RUNTIME_AVAILABLE:
            return

        for platform_id, (application, handler) in list(self._handlers.items()):
            try:
                application.remove_handler(handler)
                logger.info(
                    f"[TemplatePreview][Telegram] 已移除回调处理器: platform_id={platform_id}"
                )
            except Exception as e:
                logger.debug(
                    f"[TemplatePreview][Telegram] 移除回调处理器失败: platform_id={platform_id}, err={e}"
                )
        self._handlers.clear()
        self._registered_platform_ids.clear()
        self._platform_clients.clear()

    async def send_preview_message(
        self,
        event: AstrMessageEvent,
        platform_id: str,
        available_templates: list[str],
    ) -> bool:
        """
        在 Telegram 中发送可交互模板预览消息。

        返回：
        - True: 已由本处理器发送消息（调用方不应再走默认回复）
        - False: 无法处理，调用方应走原有降级路径
        """
        if not TELEGRAM_RUNTIME_AVAILABLE:
            return False
        if not available_templates:
            return False

        client = self._get_event_client(event, platform_id)
        if client is None:
            logger.warning("[TemplatePreview][Telegram] 无法获取 Telegram client")
            return False

        target = self._resolve_chat_target(event)
        if target is None:
            return False
        chat_id, message_thread_id = target

        try:
            requester_id = int(str(event.get_sender_id()))
        except Exception:
            logger.warning(
                "[TemplatePreview][Telegram] sender_id 非法，无法创建交互会话"
            )
            return False

        current_template = self.config_manager.get_report_template()
        if current_template in available_templates:
            index = available_templates.index(current_template)
        else:
            index = 0

        token = uuid.uuid4().hex[:8]
        keyboard = self._build_keyboard(token)
        caption = self._build_caption(
            template_name=available_templates[index],
            index=index,
            total=len(available_templates),
        )

        image_path = self.template_service.resolve_template_preview_path(
            available_templates[index]
        )
        if not image_path:
            return False

        payload: dict[str, object] = {"chat_id": chat_id, "reply_markup": keyboard}
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id

        try:
            with open(image_path, "rb") as image_file:
                sent_msg = await client.send_photo(
                    photo=image_file,
                    caption=caption,
                    connect_timeout=self._CONNECT_TIMEOUT,
                    read_timeout=self._READ_TIMEOUT,
                    write_timeout=self._WRITE_TIMEOUT,
                    pool_timeout=self._POOL_TIMEOUT,
                    **payload,
                )
        except BadRequest as e:
            if not self._is_photo_dimension_error(e):
                raise
            with open(image_path, "rb") as image_file:
                sent_msg = await client.send_document(
                    document=image_file,
                    caption=caption,
                    connect_timeout=self._CONNECT_TIMEOUT,
                    read_timeout=self._READ_TIMEOUT,
                    write_timeout=self._WRITE_TIMEOUT,
                    pool_timeout=self._POOL_TIMEOUT,
                    **payload,
                )

        self._sessions[token] = _PreviewSession(
            token=token,
            platform_id=platform_id,
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            message_id=int(cast(int, getattr(sent_msg, "message_id", 0))),
            requester_id=requester_id,
            templates=available_templates.copy(),
            index=index,
            created_at=time.time(),
        )
        self._cleanup_expired_sessions()
        logger.info(
            "[TemplatePreview][Telegram] 已发送交互预览: "
            f"platform_id={platform_id} chat_id={chat_id} token={token} templates={len(available_templates)}"
        )
        return True

    async def send_preview_image_fallback(
        self,
        event: AstrMessageEvent,
        platform_id: str,
        template_name: str,
    ) -> bool:
        """TG 回退路径：直接发送单张预览图（不经过 event.image_result）。"""
        if not TELEGRAM_RUNTIME_AVAILABLE:
            return False

        image_path = self.template_service.resolve_template_preview_path(template_name)
        if not image_path:
            return False

        client = self._get_event_client(event, platform_id)
        if client is None:
            logger.warning("[TemplatePreview][Telegram] 回退发图失败：无法获取 client")
            return False

        target = self._resolve_chat_target(event)
        if target is None:
            return False
        chat_id, message_thread_id = target

        payload: dict[str, object] = {
            "chat_id": chat_id,
            "caption": f"🖼 当前模板预览: {template_name}",
            "connect_timeout": self._CONNECT_TIMEOUT,
            "read_timeout": self._READ_TIMEOUT,
            "write_timeout": self._WRITE_TIMEOUT,
            "pool_timeout": self._POOL_TIMEOUT,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id

        try:
            with open(image_path, "rb") as image_file:
                await client.send_photo(photo=image_file, **payload)
        except BadRequest as e:
            if not self._is_photo_dimension_error(e):
                raise
            with open(image_path, "rb") as image_file:
                await client.send_document(document=image_file, **payload)
        return True

    async def handle_view_templates(
        self,
        event: AstrMessageEvent,
        platform_id: str,
        available_templates: list[str],
    ) -> tuple[bool, list[object]]:
        """统一处理 Telegram 的 /查看模板 流程。"""
        if not self.supports(event):
            return False, []

        results: list[object] = []

        async def _append_fallback_results() -> None:
            current_template = self.config_manager.get_report_template()
            template_list_str = "\n".join(
                [f"【{i}】{t}" for i, t in enumerate(available_templates, start=1)]
            )
            results.append(
                event.plain_result(
                    f"""🎨 可用报告模板列表
📌 当前使用: {current_template}

{template_list_str}

💡 使用 /设置模板 [序号] 切换"""
                )
            )

            try:
                sent_preview = await self.send_preview_image_fallback(
                    event=event,
                    platform_id=platform_id,
                    template_name=current_template,
                )
                if not sent_preview:
                    results.append(event.plain_result("⚠️ 当前模板预览图发送失败"))
            except Exception as image_err:
                logger.warning(f"[TemplatePreview][Telegram] 回退发图失败: {image_err}")
                results.append(event.plain_result("⚠️ 当前模板预览图发送失败"))

        try:
            sent = await self.send_preview_message(
                event=event,
                platform_id=platform_id,
                available_templates=available_templates,
            )
            if sent:
                return True, results
            await _append_fallback_results()
            return True, results
        except Exception as e:
            logger.warning(
                f"[TemplatePreview][Telegram] 交互预览发送失败，回退普通模式: {e}"
            )
            await _append_fallback_results()
            return True, results

    async def _on_callback_query(self, update: TelegramUpdate, context: object) -> None:
        if not TELEGRAM_RUNTIME_AVAILABLE:
            return
        if not update.callback_query or not update.callback_query.data:
            return

        self._cleanup_expired_sessions()

        query = update.callback_query
        data = query.data
        if not isinstance(data, str):
            await query.answer("无效操作", show_alert=False)
            return
        parts = data.split(":")
        if len(parts) != 3:
            await query.answer("无效操作", show_alert=False)
            return

        _, token, action = parts
        session = self._sessions.get(token)
        if not session:
            await query.answer("预览会话已过期，请重新发送 /查看模板", show_alert=True)
            return
        if time.time() - session.created_at > self._SESSION_TTL_SECONDS:
            self._sessions.pop(token, None)
            await query.answer("预览会话已过期，请重新发送 /查看模板", show_alert=True)
            return

        if not query.from_user:
            await query.answer("无法识别操作者", show_alert=False)
            return
        if int(query.from_user.id) != session.requester_id:
            await query.answer("仅命令发起人可操作该预览", show_alert=True)
            return

        if not query.message:
            await query.answer("消息已失效", show_alert=False)
            return

        message_chat_id = getattr(query.message, "chat_id", None)
        if message_chat_id is None:
            message_chat = getattr(query.message, "chat", None)
            message_chat_id = getattr(message_chat, "id", None)

        if query.message.message_id != session.message_id or str(
            message_chat_id
        ) != str(session.chat_id):
            await query.answer("预览状态不一致，请重新发送 /查看模板", show_alert=True)
            return

        if action == "prev":
            session.index = (session.index - 1) % len(session.templates)
            await self._edit_preview_message(query, session)
            await query.answer()
            return

        if action == "next":
            session.index = (session.index + 1) % len(session.templates)
            await self._edit_preview_message(query, session)
            await query.answer()
            return

        if action == "apply":
            template_name = session.current_template
            self.config_manager.set_report_template(template_name)
            await self._edit_preview_message(query, session, applied=True)
            await query.answer(f"已设置模板: {template_name}", show_alert=False)
            logger.info(
                "[TemplatePreview][Telegram] 已应用模板: "
                f"platform_id={session.platform_id} template={template_name} requester={session.requester_id}"
            )
            return

        await query.answer("未知操作", show_alert=False)

    async def _edit_preview_message(
        self,
        query: TelegramCallbackQuery,
        session: _PreviewSession,
        applied: bool = False,
    ) -> None:
        template_name = session.current_template
        caption = self._build_caption(
            template_name=template_name,
            index=session.index,
            total=len(session.templates),
            applied=applied,
        )
        keyboard = self._build_keyboard(session.token)
        image_path = self.template_service.resolve_template_preview_path(template_name)
        if not image_path:
            await query.edit_message_caption(
                caption=caption,
                reply_markup=keyboard,
            )
            return

        try:
            with open(image_path, "rb") as image_file:
                if InputMediaPhoto is None:
                    return
                media = InputMediaPhoto(media=image_file, caption=caption)
                await query.edit_message_media(
                    media=media,
                    reply_markup=keyboard,
                    connect_timeout=self._CONNECT_TIMEOUT,
                    read_timeout=self._READ_TIMEOUT,
                    write_timeout=self._WRITE_TIMEOUT,
                    pool_timeout=self._POOL_TIMEOUT,
                )
        except BadRequest as e:
            if "message is not modified" in str(e).lower():
                return
            if self._is_photo_dimension_error(e):
                try:
                    with open(image_path, "rb") as image_file:
                        if InputMediaDocument is None:
                            return
                        media = InputMediaDocument(media=image_file, caption=caption)
                        await query.edit_message_media(
                            media=media,
                            reply_markup=keyboard,
                            connect_timeout=self._CONNECT_TIMEOUT,
                            read_timeout=self._READ_TIMEOUT,
                            write_timeout=self._WRITE_TIMEOUT,
                            pool_timeout=self._POOL_TIMEOUT,
                        )
                except BadRequest as document_error:
                    if "message is not modified" in str(document_error).lower():
                        return
                    raise
                return
            raise

    def _build_keyboard(self, token: str) -> TelegramInlineKeyboardMarkup | None:
        if InlineKeyboardMarkup is None or InlineKeyboardButton is None:
            return None
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="←",
                        callback_data=f"{self._callback_prefix}:{token}:prev",
                    ),
                    InlineKeyboardButton(
                        text="确定",
                        callback_data=f"{self._callback_prefix}:{token}:apply",
                    ),
                    InlineKeyboardButton(
                        text="→",
                        callback_data=f"{self._callback_prefix}:{token}:next",
                    ),
                ]
            ]
        )

    def _build_caption(
        self,
        template_name: str,
        index: int,
        total: int,
        applied: bool = False,
    ) -> str:
        current_active = self.config_manager.get_report_template()
        active_mark = "✅ 当前生效" if template_name == current_active else "未生效"
        apply_mark = "\n\n✅ 已应用该模板" if applied else ""
        return (
            f"🎨 模板预览 ({index + 1}/{total})\n"
            f"当前项: {template_name}\n"
            f"状态: {active_mark}\n\n"
            "操作: ← 上一个 / 确定应用 / → 下一个"
            f"{apply_mark}"
        )

    @staticmethod
    def _extract_platform_meta(platform: object) -> tuple[str | None, str | None]:
        typed_platform = cast(_TelegramPlatformLike, platform)
        metadata = typed_platform.metadata
        if not metadata and hasattr(typed_platform, "meta"):
            try:
                metadata = typed_platform.meta()
            except Exception:
                metadata = None

        platform_id = None
        platform_name = None
        if metadata:
            if isinstance(metadata, dict):
                platform_id = metadata.get("id")
                platform_name = metadata.get("type") or metadata.get("name")
            else:
                platform_id = getattr(metadata, "id", None)
                platform_name = getattr(metadata, "type", None) or getattr(
                    metadata, "name", None
                )
        if platform_name:
            platform_name = str(platform_name).lower()
        if platform_id:
            platform_id = str(platform_id)
        return platform_id, platform_name

    @staticmethod
    def _extract_platform_client(platform: object) -> _TelegramClientLike | None:
        typed_platform = cast(_TelegramPlatformLike, platform)
        client: object | None = None
        if hasattr(platform, "get_client"):
            try:
                client = typed_platform.get_client()
            except Exception:
                client = None
        if client is None:
            client = typed_platform.client
        if client is None:
            application = typed_platform.application
            if application is not None:
                client = getattr(application, "bot", None)
        if client is None:
            return None
        if not hasattr(client, "send_photo") or not hasattr(client, "send_document"):
            return None
        return cast(_TelegramClientLike, client)

    @staticmethod
    def _get_raw_event_client(event: AstrMessageEvent) -> _TelegramClientLike | None:
        client = getattr(event, "client", None)
        if (
            client
            and hasattr(client, "send_photo")
            and hasattr(client, "send_document")
        ):
            return cast(_TelegramClientLike, client)
        bot = getattr(event, "bot", None)
        if bot and hasattr(bot, "send_photo") and hasattr(bot, "send_document"):
            return cast(_TelegramClientLike, bot)
        return None

    def _get_event_client(
        self, event: AstrMessageEvent, platform_id: str | None = None
    ) -> _TelegramClientLike | None:
        client = self._get_raw_event_client(event)
        if client is not None:
            return client
        if platform_id:
            cached = self._platform_clients.get(platform_id)
            if cached is not None:
                return cached
        return None

    @staticmethod
    def _resolve_chat_target(
        event: AstrMessageEvent,
    ) -> tuple[int | str, int | None] | None:
        try:
            group_id = event.get_group_id()
        except Exception:
            group_id = ""

        if group_id:
            raw_target = str(group_id)
        else:
            try:
                raw_target = str(event.get_sender_id())
            except Exception:
                return None

        chat_part = raw_target
        thread_id: int | None = None
        if "#" in raw_target:
            chat_part, thread_part = raw_target.split("#", 1)
            try:
                thread_id = int(thread_part)
            except (TypeError, ValueError):
                thread_id = None

        try:
            chat_id: int | str = int(chat_part)
        except (TypeError, ValueError):
            chat_id = chat_part
        return chat_id, thread_id

    def _cleanup_expired_sessions(self) -> None:
        now = time.time()
        expired_tokens = [
            token
            for token, session in self._sessions.items()
            if now - session.created_at > self._SESSION_TTL_SECONDS
        ]
        for token in expired_tokens:
            self._sessions.pop(token, None)

        if len(self._sessions) <= self._MAX_SESSIONS:
            return

        ordered = sorted(self._sessions.items(), key=lambda item: item[1].created_at)
        overflow_count = len(self._sessions) - self._MAX_SESSIONS
        for token, _ in ordered[:overflow_count]:
            self._sessions.pop(token, None)

    @staticmethod
    def _is_photo_dimension_error(err: Exception) -> bool:
        message = str(err).lower()
        return "photo_invalid_dimensions" in message or "invalid dimensions" in message
