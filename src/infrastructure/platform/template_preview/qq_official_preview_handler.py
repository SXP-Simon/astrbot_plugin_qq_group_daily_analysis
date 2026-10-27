"""QQ 官方机器人的单图预览与原生指令按钮。"""

from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict
from urllib.parse import urlsplit

import aiohttp
from PIL import Image

from ....utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context
    from botpy import Client
    from botpy.types.inline import Button

    from ....application.services.template_command_service import TemplateCommandService
    from ...config.config_manager import ConfigManager
    from .image_cache import PreviewImageCache


class _PreviewMarkdown(TypedDict, total=False):
    """包含新版图片转存校验字段的官方 Markdown 请求。"""

    content: str
    force_verify_image_resource: bool


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
        """准备图片后展示预览，优先图文同卡，回退时先图后说明。

        Args:
            event: 当前 QQ 官方消息事件。
            platform_id: 平台实例标识。
            available_templates: 按显示序号排序的模板列表。
            template_name: 指定模板；留空时查看当前模板。

        Returns:
            已处理标记和待发送回复，正常预览在处理器内发送完毕。
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
        text = (
            f"{selected} · {index + 1}/{len(available_templates)}\n"
            + ("当前正在使用" if selected == current else f"当前使用：{current}")
            + "\n\n按钮填入命令后，请确认发送。"
        )
        source = self.template_service.resolve_template_preview_source(selected)
        path: str | None = None
        notice = "这个自定义模板没有附带预览图。"
        if source:
            try:
                path = await self.image_cache.get_jpeg(source)
            except Exception as exc:
                logger.warning(
                    "[模板预览] QQ 图片准备失败: message_id=%s template=%s reason=%s",
                    message_id,
                    selected,
                    _describe_preview_error(exc),
                )
                notice = "这张预览图暂时无法获取，模板仍可正常选择。"

        image_markdown = ""
        if source and path:
            # 本地内置素材可使用对应的 CDN 原图；自定义预览必须保留原图来源。
            public_url = source if source.startswith(("http://", "https://")) else ""
            if not public_url and Path(source).name in {
                f"{selected}-demo.webp",
                f"{selected}-demo.jpg",
            }:
                assets = Path(self.template_service.plugin_root) / "assets"
                if Path(source).resolve() in {
                    assets.joinpath(f"{selected}-demo.webp").resolve(),
                    assets.joinpath(f"{selected}-demo.jpg").resolve(),
                }:
                    public_url = f"{self.config_manager.get_template_assets_base_url()}/{selected}-demo.webp"
            if public_url:
                try:
                    address = urlsplit(public_url)
                    # 不将用户凭据或带签名参数的资源地址转交 QQ 拉取。
                    if (
                        address.scheme in {"http", "https"}
                        and address.hostname
                        and not (
                            address.username
                            or address.password
                            or address.query
                            or address.fragment
                        )
                    ):
                        with Image.open(path) as image:
                            width, height = image.size
                        public_url = public_url.replace("(", "%28").replace(")", "%29")
                        image_markdown = f"![img#{width}px #{height}px]({public_url})"
                except (OSError, ValueError) as exc:
                    logger.debug(
                        "[模板预览] QQ 使用独立 JPEG 预览: reason=%s",
                        _describe_preview_error(exc),
                    )

        sequence = secrets.randbelow(9998) + 10001
        if (
            image_markdown
            and getattr(event, "bot", None) is not None
            and message_id
            and await self._send_native_preview(
                event, text, index, len(available_templates), sequence, image_markdown
            )
        ):
            logger.debug(
                "[模板预览] QQ 预览结束: message_id=%s layout=inline host_calls=0 failures=0",
                message_id,
            )
            return True, []

        # 图片上传和发送在说明卡片前完成，不让用户看着按钮等待图片。
        failures = 0
        host_calls = 0
        image_failed = False
        if path:
            host_calls += 1
            if not await self._send_host_preview(
                event, event.image_result(path), "image", selected
            ):
                failures += 1
                image_failed = True
                notice = "预览图发送失败，仍可使用按钮选择模板。"
        native_sent = await self._send_native_preview(
            event, text, index, len(available_templates), sequence + 1
        )
        if not native_sent:
            host_calls += 1
            plain = (
                text
                + f"\n查看：/查看模板 序号或名称\n使用此模板：/设置模板 {index + 1}"
            )
            if not await self._send_host_preview(
                event, event.plain_result(plain), "plain", selected
            ):
                failures += 1
        if not path or image_failed:
            host_calls += 1
            if not await self._send_host_preview(
                event, event.plain_result(notice), "plain", selected
            ):
                failures += 1
        logger.debug(
            "[模板预览] QQ 预览结束: message_id=%s layout=separate native_sent=%s host_calls=%s failures=%s",
            message_id,
            native_sent,
            host_calls,
            failures,
        )
        return True, []

    async def _send_host_preview(
        self,
        event: AstrMessageEvent,
        result: MessageEventResult,
        kind: str,
        template_name: str,
    ) -> bool:
        """等待宿主发送，图片和文字均记录可诊断且不含敏感内容的结果。

        Args:
            event: 当前 QQ 官方事件。
            result: 图片或普通文字回复。
            kind: 用于区分失败阶段的消息类型。
            template_name: 当前预览模板。

        Returns:
            发送调用是否完成；不代表客户端送达回执。
        """
        message_id = str(event.message_obj.message_id or "")
        result.use_markdown(False).use_t2i(False)
        logger.debug(
            "[模板预览] QQ 宿主发送开始: kind=%s message_id=%s", kind, message_id
        )
        try:
            await event.send(result)
            logger.debug(
                "[模板预览] QQ 宿主发送调用完成（非送达回执）: kind=%s message_id=%s",
                kind,
                message_id,
            )
            return True
        except Exception as exc:
            logger.warning(
                "[模板预览] QQ 发送失败: kind=%s message_id=%s template=%s reason=%s",
                kind,
                message_id,
                template_name,
                _describe_preview_error(exc),
            )
            return False

    async def _send_native_preview(
        self,
        event: AstrMessageEvent,
        text: str,
        index: int,
        total: int,
        sequence: int,
        image_markdown: str = "",
    ) -> bool:
        """发送原生卡片；图文同卡强制校验转存，失败后交给调用方回退。

        Args:
            event: 当前 QQ 官方事件。
            text: 精简预览说明。
            index: 当前模板的零基序号。
            total: 模板数量。
            sequence: 本次预览统一分配的回复序号，回退时递增以避免重复。
            image_markdown: 可公开访问的原图标记；留空时仅发送说明。

        Returns:
            原生消息是否获得有效的消息 ID。
        """
        bot: Client | None = getattr(event, "bot", None)
        message_id = str(event.message_obj.message_id or "")
        native_error = "缺少机器人客户端" if bot is None else "缺少被动回复消息 ID"
        if bot is not None and message_id:
            try:
                from botpy.http import Route
                from botpy.types.message import KeyboardPayload

                buttons: list[Button] = []
                for button_id, (label, command) in enumerate(
                    [
                        ("上一张", f"/查看模板 {(index - 1) % total + 1}"),
                        ("下一张", f"/查看模板 {(index + 1) % total + 1}"),
                        ("使用此模板", f"/设置模板 {index + 1}"),
                    ]
                ):
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
                markdown = _PreviewMarkdown(content="## " + text)
                raw = event.message_obj.raw_message
                group_id = str(getattr(raw, "group_openid", "") or "")
                channel_id = str(getattr(raw, "channel_id", "") or "")
                dm_guild_id = (
                    str(getattr(raw, "guild_id", "") or "")
                    if getattr(raw, "direct_message", False)
                    else ""
                )
                # 强制转存校验仅由群聊和单聊接口承诺，频道沿用独立 JPEG。
                if image_markdown and (channel_id or dm_guild_id):
                    logger.debug("[模板预览] QQ 频道预览使用独立 JPEG")
                    return False
                if image_markdown:
                    markdown["content"] = "## " + text + "\n\n" + image_markdown
                    markdown["force_verify_image_resource"] = True
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
                for with_buttons in (True,) if image_markdown else (True, False):
                    mode = (
                        "图文+按钮"
                        if image_markdown
                        else ("Markdown+按钮" if with_buttons else "Markdown")
                    )
                    payload: dict[str, object] = {
                        "markdown": markdown,
                        "msg_id": message_id,
                    }
                    if not channel_id and not dm_guild_id:
                        payload.update(msg_type=2, msg_seq=sequence)
                    if with_buttons:
                        payload["keyboard"] = keyboard
                    try:
                        started = time.monotonic()
                        logger.debug(
                            "[模板预览] QQ 原生发送开始: mode=%s message_id=%s",
                            mode,
                            message_id,
                        )
                        reply: object = await bot.api._http.request(route, json=payload)
                        if (
                            isinstance(reply, dict)
                            and isinstance(reply.get("id"), str)
                            and reply["id"]
                        ):
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
                            return True
                        native_error = (
                            "QQ 接口未返回结果"
                            if reply is None
                            else "QQ 接口未返回有效消息 ID"
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
        logger.warning(
            "[模板预览] QQ 原生预览不可用，将使用%s: message_id=%s reason=%s",
            "独立 JPEG 和简短卡片" if image_markdown else "普通文字和图片",
            message_id,
            native_error,
        )
        return False
