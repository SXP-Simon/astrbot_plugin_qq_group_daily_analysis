"""
OneBot v11 平台适配器

支持 NapCat、go-cqhttp、Lagrange 及其他 OneBot 实现。
"""

from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict
import aiohttp
import base64

from ....domain.value_objects.unified_message import (
    UnifiedMessage,
    MessageContent,
    MessageContentType,
)
from ....domain.value_objects.platform_capabilities import (
    PlatformCapabilities,
    ONEBOT_V11_CAPABILITIES,
)
from ....domain.value_objects.unified_group import UnifiedGroup, UnifiedMember
from ..base import PlatformAdapter


class OneBotAdapter(PlatformAdapter):
    platform_name = "onebot"

    """OneBot v11 协议适配器"""

    # QQ 头像 URL 模板
    USER_AVATAR_TEMPLATE = "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"
    USER_AVATAR_HD_TEMPLATE = (
        "https://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec={size}&img_type=jpg"
    )
    GROUP_AVATAR_TEMPLATE = "https://p.qlogo.cn/gh/{group_id}/{group_id}/{size}/"

    AVAILABLE_SIZES = [40, 100, 140, 160, 640]

    def __init__(self, bot_instance: Any, config: dict = None):
        super().__init__(bot_instance, config)
        self.bot_self_ids = (
            [str(id) for id in config.get("bot_qq_ids", [])] if config else []
        )

    def _init_capabilities(self) -> PlatformCapabilities:
        return ONEBOT_V11_CAPABILITIES

    def _get_nearest_size(self, requested_size: int) -> int:
        """获取最接近的可用尺寸"""
        return min(self.AVAILABLE_SIZES, key=lambda x: abs(x - requested_size))

    # ==================== IMessageRepository ====================

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: Optional[str] = None,
    ) -> List[UnifiedMessage]:
        """获取群组消息历史"""

        if not hasattr(self.bot, "call_action"):
            return []

        try:
            result = await self.bot.call_action(
                "get_group_msg_history",
                group_id=int(group_id),
                count=max_count,
            )

            if not result or "messages" not in result:
                return []

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            messages = []
            for raw_msg in result.get("messages", []):
                msg_time = datetime.fromtimestamp(raw_msg.get("time", 0))
                if not (start_time <= msg_time <= end_time):
                    continue

                sender_id = str(raw_msg.get("sender", {}).get("user_id", ""))
                if sender_id in self.bot_self_ids:
                    continue

                unified = self._convert_message(raw_msg, group_id)
                if unified:
                    messages.append(unified)

            messages.sort(key=lambda m: m.timestamp)
            return messages

        except Exception:
            return []

    def _convert_message(
        self, raw_msg: dict, group_id: str
    ) -> Optional[UnifiedMessage]:
        """将 OneBot 消息转换为统一格式"""
        try:
            sender = raw_msg.get("sender", {})
            message_chain = raw_msg.get("message", [])

            if isinstance(message_chain, str):
                message_chain = [{"type": "text", "data": {"text": message_chain}}]

            contents = []
            text_parts = []

            for seg in message_chain:
                seg_type = seg.get("type", "")
                seg_data = seg.get("data", {})

                if seg_type == "text":
                    text = seg_data.get("text", "")
                    text_parts.append(text)
                    contents.append(
                        MessageContent(type=MessageContentType.TEXT, text=text)
                    )

                elif seg_type == "image":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE,
                            url=seg_data.get("url", seg_data.get("file", "")),
                        )
                    )

                elif seg_type == "at":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.AT,
                            at_user_id=str(seg_data.get("qq", "")),
                        )
                    )

                elif seg_type in ("face", "mface", "bface", "sface"):
                    contents.append(
                        MessageContent(
                            type=MessageContentType.EMOJI,
                            emoji_id=str(seg_data.get("id", "")),
                            raw_data={"face_type": seg_type},
                        )
                    )

                elif seg_type == "reply":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.REPLY,
                            raw_data={"reply_id": seg_data.get("id", "")},
                        )
                    )

                elif seg_type == "forward":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.FORWARD, raw_data=seg_data
                        )
                    )

                elif seg_type == "record":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VOICE,
                            url=seg_data.get("url", seg_data.get("file", "")),
                        )
                    )

                elif seg_type == "video":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.VIDEO,
                            url=seg_data.get("url", seg_data.get("file", "")),
                        )
                    )

                else:
                    contents.append(
                        MessageContent(type=MessageContentType.UNKNOWN, raw_data=seg)
                    )

            reply_to = None
            for c in contents:
                if c.type == MessageContentType.REPLY and c.raw_data:
                    reply_to = str(c.raw_data.get("reply_id", ""))
                    break

            return UnifiedMessage(
                message_id=str(raw_msg.get("message_id", "")),
                sender_id=str(sender.get("user_id", "")),
                sender_name=sender.get("nickname", ""),
                sender_card=sender.get("card", "") or None,
                group_id=group_id,
                text_content="".join(text_parts),
                contents=tuple(contents),
                timestamp=raw_msg.get("time", 0),
                platform="onebot",
                reply_to_id=reply_to,
            )

        except Exception:
            return None

    def convert_to_raw_format(self, messages: List[UnifiedMessage]) -> List[dict]:
        """
        将统一消息格式转换为 OneBot 原生格式。

        用于与现有分析器的向后兼容。
        """
        raw_messages = []
        for msg in messages:
            # 重建 OneBot 消息格式
            message_chain = []
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    message_chain.append(
                        {"type": "text", "data": {"text": content.text or ""}}
                    )
                elif content.type == MessageContentType.IMAGE:
                    message_chain.append(
                        {"type": "image", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.AT:
                    message_chain.append(
                        {"type": "at", "data": {"qq": content.at_user_id or ""}}
                    )
                elif content.type == MessageContentType.EMOJI:
                    face_type = (
                        content.raw_data.get("face_type", "face")
                        if content.raw_data
                        else "face"
                    )
                    message_chain.append(
                        {"type": face_type, "data": {"id": content.emoji_id or ""}}
                    )
                elif content.type == MessageContentType.REPLY:
                    reply_id = (
                        content.raw_data.get("reply_id", "") if content.raw_data else ""
                    )
                    message_chain.append({"type": "reply", "data": {"id": reply_id}})
                elif content.type == MessageContentType.FORWARD:
                    message_chain.append(
                        {"type": "forward", "data": content.raw_data or {}}
                    )
                elif content.type == MessageContentType.VOICE:
                    message_chain.append(
                        {"type": "record", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.VIDEO:
                    message_chain.append(
                        {"type": "video", "data": {"url": content.url or ""}}
                    )
                elif content.type == MessageContentType.UNKNOWN and content.raw_data:
                    message_chain.append(content.raw_data)

            raw_msg = {
                "message_id": msg.message_id,
                "time": msg.timestamp,
                "sender": {
                    "user_id": msg.sender_id,
                    "nickname": msg.sender_name,
                    "card": msg.sender_card or "",
                },
                "message": message_chain,
                "group_id": msg.group_id,
                "raw_message": msg.text_content,  # 添加 raw_message 兼容字段
                "user_id": msg.sender_id,  # 添加 user_id 兼容字段
            }
            raw_messages.append(raw_msg)

        return raw_messages

    # ==================== IMessageSender ====================

    async def send_text(
        self,
        group_id: str,
        text: str,
        reply_to: Optional[str] = None,
    ) -> bool:
        """发送文本消息"""
        try:
            message = [{"type": "text", "data": {"text": text}}]

            if reply_to:
                message.insert(0, {"type": "reply", "data": {"id": reply_to}})

            await self.bot.call_action(
                "send_group_msg",
                group_id=int(group_id),
                message=message,
            )
            return True
        except Exception:
            return False

    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """发送图片消息"""
        try:
            message = []

            if caption:
                message.append({"type": "text", "data": {"text": caption}})

            if image_path.startswith(("http://", "https://")):
                file_str = image_path
            else:
                file_str = f"file:///{image_path}"

            message.append({"type": "image", "data": {"file": file_str}})

            await self.bot.call_action(
                "send_group_msg",
                group_id=int(group_id),
                message=message,
            )
            return True
        except Exception:
            return False

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: Optional[str] = None,
    ) -> bool:
        """发送文件"""
        try:
            await self.bot.call_action(
                "upload_group_file",
                group_id=int(group_id),
                file=file_path,
                name=filename or file_path.split("/")[-1],
            )
            return True
        except Exception:
            return False

    # ==================== IGroupInfoRepository ====================

    async def get_group_info(self, group_id: str) -> Optional[UnifiedGroup]:
        """获取群组信息"""
        try:
            result = await self.bot.call_action(
                "get_group_info",
                group_id=int(group_id),
            )

            if not result:
                return None

            return UnifiedGroup(
                group_id=str(result.get("group_id", group_id)),
                group_name=result.get("group_name", ""),
                member_count=result.get("member_count", 0),
                owner_id=str(result.get("owner_id", "")) or None,
                create_time=result.get("group_create_time"),
                platform="onebot",
            )
        except Exception:
            return None

    async def get_group_list(self) -> List[str]:
        """获取机器人所在的所有群组 ID"""
        try:
            result = await self.bot.call_action("get_group_list")
            return [str(g.get("group_id", "")) for g in result or []]
        except Exception:
            return []

    async def get_member_list(self, group_id: str) -> List[UnifiedMember]:
        """获取群组成员列表"""
        try:
            result = await self.bot.call_action(
                "get_group_member_list",
                group_id=int(group_id),
            )

            members = []
            for m in result or []:
                members.append(
                    UnifiedMember(
                        user_id=str(m.get("user_id", "")),
                        nickname=m.get("nickname", ""),
                        card=m.get("card", "") or None,
                        role=m.get("role", "member"),
                        join_time=m.get("join_time"),
                    )
                )
            return members
        except Exception:
            return []

    async def get_member_info(
        self,
        group_id: str,
        user_id: str,
    ) -> Optional[UnifiedMember]:
        """获取特定成员信息"""
        try:
            result = await self.bot.call_action(
                "get_group_member_info",
                group_id=int(group_id),
                user_id=int(user_id),
            )

            if not result:
                return None

            return UnifiedMember(
                user_id=str(result.get("user_id", user_id)),
                nickname=result.get("nickname", ""),
                card=result.get("card", "") or None,
                role=result.get("role", "member"),
                join_time=result.get("join_time"),
            )
        except Exception:
            return None

    # ==================== IAvatarRepository ====================

    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 QQ 用户头像 URL"""
        actual_size = self._get_nearest_size(size)
        if actual_size >= 640:
            return self.USER_AVATAR_HD_TEMPLATE.format(user_id=user_id, size=640)
        return self.USER_AVATAR_TEMPLATE.format(user_id=user_id, size=actual_size)

    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 QQ 用户头像 Base64 数据"""
        url = await self.get_user_avatar_url(user_id, size)
        if not url:
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        b64 = base64.b64encode(data).decode("utf-8")
                        content_type = resp.headers.get("Content-Type", "image/png")
                        return f"data:{content_type};base64,{b64}"
        except Exception:
            pass
        return None

    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> Optional[str]:
        """获取 QQ 群头像 URL"""
        actual_size = self._get_nearest_size(size)
        return self.GROUP_AVATAR_TEMPLATE.format(group_id=group_id, size=actual_size)

    async def batch_get_avatar_urls(
        self,
        user_ids: List[str],
        size: int = 100,
    ) -> Dict[str, Optional[str]]:
        """批量获取 QQ 用户头像 URL（无需 API 调用）"""
        return {
            user_id: await self.get_user_avatar_url(user_id, size)
            for user_id in user_ids
        }
