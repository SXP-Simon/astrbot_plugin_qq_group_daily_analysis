"""QQ 官方机器人的单图预览与原生指令按钮。"""

from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING

import aiohttp

from ....utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context
    from botpy import Client
    from botpy.types.inline import Button

    from ....application.services.template_command_service import TemplateCommandService
    from ...config.config_manager import ConfigManager
    from .image_cache import PreviewImageCache


def _describe_preview_error(exc: Exception) -> str:
    """仅描述错误类别和可公开的状态，不回显 SDK 正文中的敏感地址。

    Args:
        exc: 原生消息、图片准备或宿主发送阶段的异常。

    Returns:
        不含请求正文、Token 或完整资源地址的排障说明。
    """
    name = type(exc).__name__
    if isinstance(exc, aiohttp.ClientResponseError):
        return f"{name}: HTTP {exc.status}"
    if isinstance(exc, aiohttp.ClientConnectionError):
        return f"{name}: 无法连接，请检查网络或代理"
    if isinstance(exc, TimeoutError):
        return f"{name}: 请求超时"
    reasons = {
        "AuthenticationFailedError": "QQ 接口鉴权失败，请检查机器人连接状态",
        "ForbiddenError": "QQ 接口拒绝访问，请检查消息及按钮权限",
        "SequenceNumberError": "QQ 接口限流或消息序号冲突",
        "ServerError": "QQ 接口返回错误，请结合宿主日志检查服务状态",
        "NotFoundError": "QQ 接口或目标会话不存在",
        "MethodNotAllowedError": "QQ 接口不支持此发送方式",
        "ImportError": "当前 SDK 缺少原生消息能力",
        "AttributeError": "当前客户端缺少所需 SDK 接口",
        "FileNotFoundError": "本地预览图或缓存文件不存在",
        "PermissionError": "没有本地文件读写权限",
        "UnidentifiedImageError": "预览内容不是可识别的图片",
        "ValueError": "图片格式、大小或像素未通过校验",
    }
    return f"{name}: {reasons.get(name, '调用异常，请结合当前阶段排查')}"


class QQOfficialTemplatePreviewHandler:
    """优先使用 Markdown 和指令按钮；权限不足时保留普通文字及 JPEG。"""

    def __init__(
        self,
        config_manager: ConfigManager,
        template_service: TemplateCommandService,
        image_cache: PreviewImageCache,
    ) -> None:
        self.config_manager = config_manager
        self.template_service = template_service
        self.image_cache = image_cache

    @staticmethod
    def supports(event: AstrMessageEvent) -> bool:
        """识别 WebSocket 和 Webhook 两种官方接入。"""
        return event.get_platform_name() in {"qq_official", "qq_official_webhook"}

    def ensure_callback_handlers_registered(self, context: Context) -> None:
        """指令按钮复用已有命令权限检查，无需注册回调。"""

    def unregister_callback_handlers(self) -> None:
        """无独立回调资源需要注销。"""

    async def handle_view_templates(
        self,
        event: AstrMessageEvent,
        platform_id: str,
        available_templates: list[str],
        template_name: str = "",
    ) -> tuple[bool, list[MessageEventResult]]:
        """发送模板说明和当前预览，不使用官方接口不支持的转发节点。

        Args:
            event: 当前 QQ 官方消息事件。
            platform_id: 平台实例标识。
            available_templates: 按显示序号排序的模板列表。
            template_name: 指定要查看的模板；留空时查看当前模板。

        Returns:
            已处理标记，以及尚未发送的回复；正常预览在此等待发送完成。
        """
        if not self.supports(event):
            return False, []
        if not available_templates:
            return True, [
                event.plain_result("没有可用模板。").use_markdown(False).use_t2i(False)
            ]
        current = self.config_manager.get_report_template()
        selected = template_name or current
        if selected not in available_templates:
            selected = available_templates[0]
        index = available_templates.index(selected)
        message_id = str(event.message_obj.message_id or "")
        logger.debug(
            "[模板预览] QQ 官方处理器: platform=%s platform_id=%s message_id=%s template=%s",
            event.get_platform_name(),
            platform_id,
            message_id,
            selected,
        )
        lines = [
            f"{i}. {name}{' ✓' if name == current else ''}"
            for i, name in enumerate(available_templates, 1)
        ]
        text = (
            f"模板预览 · {index + 1}/{len(available_templates)}\n"
            f"当前使用：{current}\n正在查看：{selected}\n\n"
            + "\n".join(lines)
            + "\n\n查看其他图片：/查看模板 序号\n切换模板：/设置模板 序号"
            + "\n按钮会填入命令，请确认后发送。"
        )
        results: list[MessageEventResult] = []
        markdown_sent = False
        # 宿主 SDK 边界兼容：旧版或没有 Markdown/按钮权限时回退普通消息。
        bot: Client | None = getattr(event, "bot", None)
        native_error = "缺少机器人客户端" if bot is None else "缺少被动回复消息 ID"
        if bot is not None and message_id:
            try:
                from botpy.http import Route
                from botpy.types.message import KeyboardPayload, MarkdownPayload

                buttons: list[Button] = []
                actions = [
                    (
                        "上一张",
                        f"/查看模板 {(index - 1) % len(available_templates) + 1}",
                    ),
                    (
                        "下一张",
                        f"/查看模板 {(index + 1) % len(available_templates) + 1}",
                    ),
                    ("使用此模板", f"/设置模板 {index + 1}"),
                ]
                for button_id, (label, command) in enumerate(actions):
                    buttons.append(
                        {
                            "id": f"template_{button_id}",
                            "render_data": {
                                "label": label,
                                "visited_label": label,
                                "style": 1,
                            },
                            "action": {
                                "type": 2,
                                "data": command,
                                "permission": {
                                    "type": 0,
                                    "specify_user_ids": [event.get_sender_id()],
                                    "specify_role_ids": [],
                                },
                                "click_limit": 0,
                                "at_bot_show_channel_list": False,
                            },
                        }
                    )
                keyboard = KeyboardPayload(content={"rows": [{"buttons": buttons}]})
                markdown = MarkdownPayload(content="## " + text)
                raw = event.message_obj.raw_message
                group_id = str(getattr(raw, "group_openid", "") or "")
                channel_id = str(getattr(raw, "channel_id", "") or "")
                dm_guild_id = (
                    str(getattr(raw, "guild_id", "") or "")
                    if getattr(raw, "direct_message", False)
                    else ""
                )
                sequence = secrets.randbelow(10000) + 10001
                if group_id:
                    route = Route(
                        "POST",
                        "/v2/groups/{group_openid}/messages",
                        group_openid=group_id,
                    )
                elif dm_guild_id:
                    route = Route(
                        "POST", "/dms/{guild_id}/messages", guild_id=dm_guild_id
                    )
                elif channel_id:
                    route = Route(
                        "POST", "/channels/{channel_id}/messages", channel_id=channel_id
                    )
                else:
                    route = Route(
                        "POST",
                        "/v2/users/{openid}/messages",
                        openid=event.get_sender_id(),
                    )
                for with_buttons in (True, False):
                    mode = "Markdown+按钮" if with_buttons else "Markdown"
                    payload: dict[str, object] = {
                        "markdown": markdown,
                        "msg_id": message_id,
                    }
                    if not channel_id and not dm_guild_id:
                        payload.update(msg_type=2, msg_seq=sequence)
                    if with_buttons:
                        payload["keyboard"] = keyboard
                    try:
                        # 旧版 botpy 对 keyboard 的类型声明不完整；复用其鉴权传输，
                        # 按官方协议传递 content.rows，而不依赖过时的 SDK 参数签名。
                        started = time.monotonic()
                        logger.debug(
                            "[模板预览] QQ 原生发送开始: mode=%s message_id=%s",
                            mode,
                            message_id,
                        )
                        reply: object = await bot.api._http.request(route, json=payload)
                        if reply is not None:
                            markdown_sent = True
                            logger.debug(
                                "[模板预览] QQ 原生接口返回成功: mode=%s message_id=%s elapsed_ms=%s",
                                mode,
                                message_id,
                                round((time.monotonic() - started) * 1000),
                            )
                            if not with_buttons:
                                logger.warning(
                                    "[模板预览] QQ 按钮消息不可用，已使用仅 Markdown: message_id=%s reason=%s",
                                    message_id,
                                    native_error,
                                )
                            break
                        native_error = "QQ 接口未返回结果"
                        logger.debug(
                            "[模板预览] QQ 原生发送未返回结果: mode=%s message_id=%s",
                            mode,
                            message_id,
                        )
                    except Exception as exc:
                        native_error = _describe_preview_error(exc)
                        logger.debug(
                            "[模板预览] QQ 原生发送失败: mode=%s message_id=%s reason=%s",
                            mode,
                            message_id,
                            native_error,
                        )
                    sequence += 1
            except (ImportError, AttributeError) as exc:
                native_error = _describe_preview_error(exc)
        if not markdown_sent:
            logger.warning(
                "[模板预览] QQ 原生预览不可用，将使用普通文字和图片: message_id=%s reason=%s",
                message_id,
                native_error,
            )
            results.append(event.plain_result(text))
        source = self.template_service.resolve_template_preview_source(selected)
        image_reply: MessageEventResult | None = None
        if source:
            try:
                path = await self.image_cache.get_jpeg(source)
                image_reply = event.image_result(path)
                results.append(image_reply)
            except Exception as exc:
                logger.warning(
                    "[模板预览] QQ 图片准备失败: message_id=%s template=%s reason=%s",
                    message_id,
                    selected,
                    _describe_preview_error(exc),
                )
                results.append(
                    event.plain_result("这张预览图暂时无法获取，模板仍可正常选择。")
                )
        else:
            logger.debug("[模板预览] QQ 当前模板没有预览图: template=%s", selected)
            results.append(event.plain_result("这个自定义模板没有附带预览图。"))
        failures = 0
        for result in results:
            # 明确禁止宿主再次把回退文字当成 Markdown 或自动转图。
            result.use_markdown(False).use_t2i(False)
            kind = "image" if result is image_reply else "plain"
            logger.debug(
                "[模板预览] QQ 宿主发送开始: kind=%s message_id=%s",
                kind,
                message_id,
            )
            try:
                # 此处等待宿主调用，以捕获图片上传和发送异常；返回回复不代表已发送。
                await event.send(result)
                logger.debug(
                    "[模板预览] QQ 宿主发送调用完成（非送达回执）: kind=%s message_id=%s",
                    kind,
                    message_id,
                )
            except Exception as exc:
                failures += 1
                logger.warning(
                    "[模板预览] QQ 发送失败: kind=%s message_id=%s template=%s reason=%s",
                    kind,
                    message_id,
                    selected,
                    _describe_preview_error(exc),
                )
        logger.debug(
            "[模板预览] QQ 预览结束: message_id=%s native_sent=%s host_calls=%s failures=%s",
            message_id,
            markdown_sent,
            len(results),
            failures,
        )
        return True, []
