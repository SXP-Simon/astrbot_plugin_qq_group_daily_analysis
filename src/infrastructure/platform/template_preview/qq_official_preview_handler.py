"""QQ 官方机器人的单图预览与原生指令按钮。"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from ....utils.logger import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent, MessageEventResult
    from astrbot.api.star import Context
    from botpy import Client
    from botpy.types.inline import Button

    from ....application.services.template_command_service import TemplateCommandService
    from ...config.config_manager import ConfigManager
    from .image_cache import PreviewImageCache


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
            已处理标记，以及交给宿主发送的普通回复。
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
        message_id = str(event.message_obj.message_id or "")
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
                        reply: object = await bot.api._http.request(route, json=payload)
                        if reply is not None:
                            markdown_sent = True
                            break
                    except Exception as exc:
                        logger.debug("QQ 官方模板预览原生消息不可用: %s", exc)
                    sequence += 1
            except (ImportError, AttributeError) as exc:
                logger.debug("QQ 官方模板预览使用普通消息: %s", exc)
        if not markdown_sent:
            results.append(event.plain_result(text))
        source = self.template_service.resolve_template_preview_source(selected)
        if source:
            try:
                path = await self.image_cache.get_jpeg(source)
                results.append(event.image_result(path))
            except Exception as exc:
                logger.warning("QQ 官方模板预览图片准备失败: %s", exc)
                results.append(
                    event.plain_result("这张预览图暂时无法获取，模板仍可正常选择。")
                )
        else:
            results.append(event.plain_result("这个自定义模板没有附带预览图。"))
        for result in results:
            # 明确禁止宿主再次把回退文字当成 Markdown 或自动转图。
            result.use_markdown(False).use_t2i(False)
        return True, results
