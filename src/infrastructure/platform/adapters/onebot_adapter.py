"""
OneBot v11 平台适配器

支持 NapCat、go-cqhttp、Lagrange 及其他 OneBot 实现。
"""

import asyncio
import base64
import os
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from ....domain.value_objects.platform_capabilities import (
    ONEBOT_V11_CAPABILITIES,
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


class OneBotAdapter(PlatformAdapter):
    """
    具体实现：OneBot v11 平台适配器

    支持 NapCat, go-cqhttp, Lagrange 等遵循 OneBot v11 协议的 QQ 机器人框架。
    实现了消息获取、发送、群组管理及头像解析等全套功能。

    Attributes:
        platform_name (str): 平台硬编码标识 'onebot'
        bot_self_ids (list[str]): 机器人自身的 QQ 号列表，用于消息过滤
    """

    platform_name = "onebot"

    # QQ 头像服务 URL 模板
    USER_AVATAR_TEMPLATE = "https://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"
    USER_AVATAR_HD_TEMPLATE = (
        "https://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec={size}&img_type=jpg"
    )
    GROUP_AVATAR_TEMPLATE = "https://p.qlogo.cn/gh/{group_id}/{group_id}/{size}/"

    # OneBot 服务支持的头像尺寸像素
    AVAILABLE_SIZES = (40, 100, 140, 160, 640)

    def __init__(self, bot_instance: Any, config: dict | None = None):
        """
        初始化 OneBot 适配器。

        Args:
            bot_instance (Any): 外部传入的机器人对象
            config (dict, optional): 插件配置，用于提取机器人自身的 QQ 号供过滤用
        """
        super().__init__(bot_instance, config)
        self.bot_self_ids = (
            [str(id) for id in config.get("bot_qq_ids", [])] if config else []
        )

    def _init_capabilities(self) -> PlatformCapabilities:
        """返回预定义的 OneBot v11 能力集。"""
        return ONEBOT_V11_CAPABILITIES

    def _get_nearest_size(self, requested_size: int) -> int:
        """从支持的尺寸列表中找到最接近请求尺寸的一个。"""
        return min(self.AVAILABLE_SIZES, key=lambda x: abs(x - requested_size))

    # ==================== IMessageRepository 实现 ====================

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: str | None = None,
    ) -> list[UnifiedMessage]:
        """
        从 OneBot 后端拉取群组历史消息。
        采用分页拉取策略（参考 portrayal 插件），减少 NapCat/go-cqhttp 单次请求的 CPU 和内存负担。

        Args:
            group_id (str): 群号
            days (int): 拉取过去几天的消息
            max_count (int): 最大拉取条数
            before_id (str, optional): 锚点消息 ID，用于分页回溯

        Returns:
            list[UnifiedMessage]: 统一格式的消息列表
        """
        if not hasattr(self.bot, "call_action"):
            return []

        try:
            chunk_size = 100  # 每次拉取 100 条，较为稳健
            all_raw_messages = []

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            start_timestamp = int(start_time.timestamp())

            # 使用 message_seq (在 NapCat 中通常可用 message_id 作为 seq 参数)
            # 进行分页回溯拉取
            current_anchor_id = before_id

            logger.info(
                f"OneBot 开始分页回溯拉取消息: 群 {group_id}, 时间限制 {days}天, 数量限制 {max_count}"
            )

            while len(all_raw_messages) < max_count:
                fetch_count = min(chunk_size, max_count - len(all_raw_messages))

                params = {
                    "group_id": int(group_id),
                    "count": fetch_count,
                    "reverseOrder": True,  # 关键：协助分页向上回退拉取历史
                }

                if current_anchor_id:
                    params["message_seq"] = current_anchor_id

                result = await self.bot.call_action("get_group_msg_history", **params)

                if not result or "messages" not in result:
                    logger.debug(
                        f"OneBot 分页拉取：API 调用返回空或无效数据，停止回溯。群: {group_id}"
                    )
                    break

                messages = result.get("messages", [])
                if not messages:
                    logger.debug(
                        f"OneBot 分页拉取：获取到 0 条消息，停止回溯。群: {group_id}"
                    )
                    break

                # 消息通常是按时间正序排列的，即 messages[0] 最旧，messages[-1] 最新
                chunk_earliest_msg = messages[0]
                chunk_earliest_time = chunk_earliest_msg.get("time", 0)

                for raw_msg in messages:
                    msg_time = raw_msg.get("time", 0)

                    # 身份过滤（排除机器人自己）
                    sender_id = str(raw_msg.get("sender", {}).get("user_id", ""))
                    if sender_id in self.bot_self_ids:
                        continue

                    # 时间范围判定
                    if start_timestamp <= msg_time <= int(end_time.timestamp()):
                        all_raw_messages.append(raw_msg)

                # 更新锚点为该批次最旧的消息 ID，用于下一次回溯请求
                new_anchor_id = chunk_earliest_msg.get("message_id")

                # 如果时间已经超过限制，或者锚点没有变化（说明已经到底），则停止
                if chunk_earliest_time < start_timestamp:
                    logger.debug(
                        f"OneBot 分页拉取：消息时间 ({chunk_earliest_time}) 早于起始时间 ({start_timestamp})，回溯完成。"
                    )
                    break

                if str(new_anchor_id) == str(current_anchor_id):
                    logger.debug(
                        "OneBot 分页拉取：消息锚点没有变化，可能已到达历史尽头。"
                    )
                    break

                current_anchor_id = new_anchor_id
                logger.debug(
                    f"OneBot 分页拉取进度: 已获取 {len(all_raw_messages)} 条符合条件的消息，下一次锚点: {current_anchor_id}"
                )

                # 如果这批消息全都是旧的（不在我们要的时间范围内），也应该可以考虑停止
                # 但由于 get_group_msg_history 的 reverseOrder 行为在不同实现下可能不一致，
                # 只要时间没越界且还有消息，我们就继续拉取直到 max_count 或时间越界。

                # 稍微延迟，减缓服务端压力（避免 NapCat 瞬间 CPU 飙升）
                await asyncio.sleep(0.05)

            # 统一转换为 UnifiedMessage 并在返回前去重排序
            unified_messages = []
            seen_ids = set()
            for raw_msg in all_raw_messages:
                mid = str(raw_msg.get("message_id", ""))
                if not mid or mid in seen_ids:
                    continue

                unified = self._convert_message(raw_msg, group_id)
                if unified:
                    unified_messages.append(unified)
                    seen_ids.add(mid)

            # 确保最终结果符合时间顺序
            unified_messages.sort(key=lambda m: m.timestamp)

            logger.info(
                f"OneBot 分页拉取完成: 共处理 {len(all_raw_messages)} 条原始消息, 最终有效 {len(unified_messages)} 条"
            )
            return unified_messages

        except Exception as e:
            logger.warning(f"OneBot 分页获取消息失败: {e}")
            return []

    def _convert_message(self, raw_msg: dict, group_id: str) -> UnifiedMessage | None:
        """内部方法：将 OneBot 原生原始消息字典转换为 UnifiedMessage 值对象。"""
        try:
            sender = raw_msg.get("sender", {})
            message_chain = raw_msg.get("message", [])

            # 兼容性处理：如果是字符串格式的 message，转换为列表格式
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

            # 提取回复 ID
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

        except Exception as e:
            logger.debug(f"OneBot _convert_message 错误: {e}")
            return None

    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        """
        将统一格式转换回 OneBot v11 原生字典格式。

        使现有业务逻辑逻辑无需重构即可使用新流水。

        Args:
            messages (list[UnifiedMessage]): 统一消息列表

        Returns:
            list[dict]: OneBot 格式的消息字典列表
        """
        raw_messages = []
        for msg in messages:
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
                "raw_message": msg.text_content,
                "user_id": msg.sender_id,
            }
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
        向群组发送文本消息。

        Args:
            group_id (str): 目标群号
            text (str): 消息内容
            reply_to (str, optional): 引用回复的消息 ID

        Returns:
            bool: 是否发送成功
        """
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
        except Exception as e:
            logger.error(f"OneBot 文本发送失败: {e}")
            return False

    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """
        向群组发送图片。

        Args:
            group_id (str): 目标群号
            image_path (str): 本地文件路径或远程 URL
            caption (str): 图片下方可选的文字说明

        Returns:
            bool: 是否成功
        """
        try:
            # 策略 1: 优先尝试物理路径 (高性能, 支持超大图)
            file_str = image_path
            if not image_path.startswith(("http://", "https://", "base64://")):
                file_str = f"file:///{os.path.abspath(image_path)}"

            try:
                message = []
                if caption:
                    message.append({"type": "text", "data": {"text": caption}})
                message.append({"type": "image", "data": {"file": file_str}})

                await self.bot.call_action(
                    "send_group_msg",
                    group_id=int(group_id),
                    message=message,
                )
                return True
            except Exception as e:
                # 如果是网络图片或 Base64 已经报错，则直接失败
                if image_path.startswith(("http://", "https://", "base64://")):
                    raise e

                # 策略 2: 路径报错 (如 1200 / ENOENT)，回退到 Base64 发送 (兼容跨容器)
                logger.warning(f"路径发送图片失败 ({e})，尝试 Base64 回退模式...")
                b64_str = await self._get_base64_from_file(image_path)
                if not b64_str:
                    raise e  # 无法读取本地文件，抛出原始错误

                message = []
                if caption:
                    message.append({"type": "text", "data": {"text": caption}})
                message.append({"type": "image", "data": {"file": b64_str}})

                await self.bot.call_action(
                    "send_group_msg",
                    group_id=int(group_id),
                    message=message,
                )
                logger.info(f"Base64 回退模式发送图片成功: 群 {group_id}")
                return True

        except Exception as e:
            logger.error(f"OneBot 图片发送最终失败: {e}")
            return False

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: str | None = None,
    ) -> bool:
        """
        通过群文件功能上传并发送文件。

        Args:
            group_id (str): 目标群号
            file_path (str): 本地文件绝对路径
            filename (str, optional): 显示的文件名，默认为路径尾部

        Returns:
            bool: 上传任务启动是否成功
        """
        try:
            # 策略 1: 优先尝试物理路径
            try:
                await self.bot.call_action(
                    "upload_group_file",
                    group_id=int(group_id),
                    file=file_path,
                    name=filename or os.path.basename(file_path),
                )
                return True
            except Exception as e:
                # 策略 2: 路径报错，回退到 Base64
                logger.warning(f"路径发送文件失败 ({e})，尝试 Base64 回退模式...")
                file_b64 = await self._get_base64_from_file(file_path)
                if not file_b64:
                    raise e

                await self.bot.call_action(
                    "upload_group_file",
                    group_id=int(group_id),
                    file=file_b64,
                    name=filename or os.path.basename(file_path),
                )
                logger.info(f"Base64 回退模式发送文件成功: {filename or file_path}")
                return True
        except Exception as e:
            logger.error(f"OneBot 文件发送最终失败: {e}")
            return False

    async def send_forward_msg(
        self,
        group_id: str,
        nodes: list[dict],
    ) -> bool:
        """
        发送群合并转发消息。

        Args:
            group_id (str): 目标群号
            nodes (list[dict]): 转发节点列表

        Returns:
            bool: 是否发送成功
        """
        if not hasattr(self.bot, "call_action"):
            return False

        try:
            # 兼容处理节点中的 uin -> user_id (有些后端偏好 uin)
            for node in nodes:
                if "data" in node:
                    if "user_id" in node["data"] and "uin" not in node["data"]:
                        node["data"]["uin"] = node["data"]["user_id"]

            await self.bot.call_action(
                "send_group_forward_msg",
                group_id=int(group_id),
                messages=nodes,
            )
            return True
        except Exception as e:
            logger.warning(f"OneBot 发送合并转发消息失败: {e}")
            return False

    # ==================== IGroupInfoRepository 实现 ====================

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        """获取指定群组的基础元数据。"""
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

    async def get_group_list(self) -> list[str]:
        """获取当前机器人已加入的所有群组 ID 列表。"""
        try:
            result = await self.bot.call_action("get_group_list")
            return [str(g.get("group_id", "")) for g in result or []]
        except Exception:
            return []

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        """拉取整个群组成员列表。"""
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
    ) -> UnifiedMember | None:
        """拉取特定群成员的详细名片及角色信息。"""
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

    async def _get_base64_from_file(self, file_path: str) -> str | None:
        """
        读取本地文件并返回 Base64 编码字符串。

        Args:
            file_path: 本地文件绝对路径

        Returns:
            str | None: base64://... 格式的字符串，读取失败返回 None
        """
        try:
            import os

            if not os.path.exists(file_path):
                logger.error(f"文件不存在，无法读取 Base64: {file_path}")
                return None

            with open(file_path, "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode("utf-8")
                return f"base64://{b64}"
        except Exception as e:
            logger.error(f"读取文件并转换 Base64 失败: {e}")
            return None

    # ==================== IAvatarRepository 实现 ====================

    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> str | None:
        """
        拼凑 QQ 官方服务地址获取用户头像。

        Args:
            user_id (str): QQ 号
            size (int): 期望像素大小

        Returns:
            str: 格式化后的 URL
        """
        actual_size = self._get_nearest_size(size)
        # 640 使用 HD 接口更清晰
        if actual_size >= 640:
            return self.USER_AVATAR_HD_TEMPLATE.format(user_id=user_id, size=640)
        return self.USER_AVATAR_TEMPLATE.format(user_id=user_id, size=actual_size)

    async def get_user_avatar_data(
        self,
        user_id: str,
        size: int = 100,
    ) -> str | None:
        """
        通过网络下载头像并转换为 Base64 格式，适用于前端模板直接渲染。
        """
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
        except Exception as e:
            logger.debug(f"OneBot 头像下载失败: {e}")
        return None

    async def get_group_avatar_url(
        self,
        group_id: str,
        size: int = 100,
    ) -> str | None:
        """获取 QQ 群头像地址。"""
        actual_size = self._get_nearest_size(size)
        return self.GROUP_AVATAR_TEMPLATE.format(group_id=group_id, size=actual_size)

    async def batch_get_avatar_urls(
        self,
        user_ids: list[str],
        size: int = 100,
    ) -> dict[str, str | None]:
        """批量映射 QQ 号到其头像 URL 地址。"""
        return {
            user_id: await self.get_user_avatar_url(user_id, size)
            for user_id in user_ids
        }

    # ================================================================
    # 群文件 / 群相册上传
    # ================================================================

    async def upload_group_file_to_folder(
        self,
        group_id: str,
        file_path: str,
        filename: str | None = None,
        folder_id: str | None = None,
    ) -> bool:
        """
        上传文件到群文件目录的指定子文件夹。

        Args:
            group_id: 目标群号
            file_path: 本地文件绝对路径
            filename: 显示的文件名，默认为路径尾部
            folder_id: 目标文件夹 ID（由 get_group_file_root_folders 获取）。
                       为 None 或空字符串时上传到根目录。

        Returns:
            bool: 上传任务是否成功启动
        """
        try:
            # 策略 1: 优先使用物理路径
            params = {
                "group_id": int(group_id),
                "file": file_path,
                "name": filename or os.path.basename(file_path),
            }
            if folder_id:
                params["folder"] = folder_id

            try:
                await self.bot.call_action("upload_group_file", **params)
                logger.info(
                    f"OneBot 群文件上传成功: {params['name']} -> 群 {group_id}"
                    + (f" (目录: {folder_id})" if folder_id else " (根目录)")
                )
                return True
            except Exception as e:
                # 策略 2: 路径报错，回退到 Base64
                logger.warning(f"路径上传群文件失败 ({e})，尝试 Base64 回退模式...")
                b64_str = await self._get_base64_from_file(file_path)
                if not b64_str:
                    raise e

                params["file"] = b64_str
                await self.bot.call_action("upload_group_file", **params)
                logger.info(f"Base64 回退模式上传群文件成功: {params['name']}")
                return True

        except Exception as e:
            logger.error(f"OneBot 群文件上传最终失败: {e}")
            return False

    async def create_group_file_folder(
        self,
        group_id: str,
        folder_name: str,
    ) -> str | None:
        """
        在群文件根目录下创建子文件夹。

        Args:
            group_id: 目标群号
            folder_name: 文件夹名称

        Returns:
            str | None: 创建成功时返回 folder_id，失败返回 None
        """
        try:
            result = await self.bot.call_action(
                "create_group_file_folder",
                group_id=int(group_id),
                name=folder_name,
                parent_id="/",
            )
            # go-cqhttp 等实现可能不返回 folder_id
            folder_id = None
            if isinstance(result, dict):
                folder_id = result.get("folder_id") or result.get("id")
            logger.info(
                f"OneBot 群文件夹创建成功: {folder_name} (群 {group_id})"
                + (f" [ID: {folder_id}]" if folder_id else "")
            )
            return folder_id
        except Exception as e:
            error_msg = str(e).lower()
            # 文件夹已存在的情况不视为错误
            if "exist" in error_msg or "已存在" in error_msg:
                logger.info(f"OneBot 群文件夹已存在: {folder_name} (群 {group_id})")
                return None  # 需要通过 get_group_file_root_folders 获取 ID
            logger.error(f"OneBot 群文件夹创建失败: {e}")
            return None

    async def get_group_file_root_folders(
        self,
        group_id: str,
    ) -> list[dict]:
        """
        获取群文件根目录下的文件夹列表。

        Args:
            group_id: 目标群号

        Returns:
            list[dict]: 文件夹列表，每项包含 folder_id/name 等字段。
                        API 不可用时返回空列表。
        """
        try:
            result = await self.bot.call_action(
                "get_group_root_files",
                group_id=int(group_id),
            )
            if isinstance(result, dict):
                return result.get("folders", []) or []
            return []
        except Exception as e:
            logger.debug(f"OneBot 获取群文件夹列表失败: {e}")
            return []

    async def find_or_create_folder(
        self,
        group_id: str,
        folder_name: str,
    ) -> str | None:
        """
        查找或创建指定名称的群文件子文件夹，返回 folder_id。

        先尝试在现有根目录文件夹中查找匹配名称的文件夹，
        找不到则创建新文件夹。

        Args:
            group_id: 目标群号
            folder_name: 文件夹名称

        Returns:
            str | None: folder_id（成功时）或 None（失败时）
        """
        if not folder_name:
            return None

        # 1. 先尝试查找已有文件夹
        folders = await self.get_group_file_root_folders(group_id)
        for folder in folders:
            name = folder.get("folder_name") or folder.get("name", "")
            fid = folder.get("folder_id") or folder.get("id", "")
            if name == folder_name and fid:
                logger.debug(f"找到已有群文件夹: {folder_name} [ID: {fid}]")
                return fid

        # 2. 未找到，尝试创建
        created_id = await self.create_group_file_folder(group_id, folder_name)
        if created_id:
            return created_id

        # 3. 创建后再次查找（某些实现创建时不返回 ID）
        folders = await self.get_group_file_root_folders(group_id)
        for folder in folders:
            name = folder.get("folder_name") or folder.get("name", "")
            fid = folder.get("folder_id") or folder.get("id", "")
            if name == folder_name and fid:
                logger.debug(f"创建后找到群文件夹: {folder_name} [ID: {fid}]")
                return fid

        logger.warning(
            f"无法获取群文件夹 ID: {folder_name} (群 {group_id})，将上传到根目录"
        )
        return None

    async def upload_group_album(
        self,
        group_id: str,
        image_path: str,
        album_id: str | None = None,
        album_name: str | None = None,
    ) -> bool:
        """
        上传图片到群相册（NapCat 扩展 API）。

        注意：此功能主要由 NapCat 等 OneBot 增强版实现提供。
        调用失败时会静默降级，不影响正常发送。

        Args:
            group_id: 目标群号
            image_path: 本地图片文件的绝对路径
            album_id: 目标相册 ID
            album_name: 目标相册名称（部分 API 需要）

        Returns:
            bool: 上传是否成功
        """
        try:
            # 如果没有 album_id，尝试获取该群的第一个相册作为默认目标
            # 注意：某些 API (如 upload_image_to_qun_album) 强制要求 album_id 且不能为空
            if not album_id:
                albums = await self.get_group_album_list(group_id)
                if albums:
                    album_id = str(
                        albums[0].get("album_id") or albums[0].get("id") or ""
                    )
                    if album_id:
                        logger.debug(
                            f"未指定有效的相册，自动选择默认相册 ID: {album_id}"
                        )

            if not album_id:
                logger.info(
                    f"群 {group_id} 未找到任何有效相册，且未指定相册名，跳过相册上传以防止后端错误。"
                )
                return False

            # 策略 1: 优先尝试物理路径
            try:
                # 尝试 upload_image_to_qun_album
                params = {
                    "group_id": int(group_id),
                    "file": image_path,
                    "album_id": str(album_id or ""),
                }
                if album_name:
                    params["album_name"] = album_name

                logger.debug(
                    f"尝试调用 upload_image_to_qun_album (路径模式), 参数: {params}"
                )
                await self.bot.call_action("upload_image_to_qun_album", **params)
                logger.info(f"OneBot (路径模式) 群相册上传成功: 群 {group_id}")
                return True
            except Exception as e1:
                # 策略 2: 路径失败，尝试 Base64 模式
                logger.warning(f"路径上传相册失败 ({e1})，尝试 Base64 回退模式...")
                b64_file = await self._get_base64_from_file(image_path)
                if not b64_file:
                    raise e1

                # 重新尝试两个可能的 API 名
                try:
                    params = {
                        "group_id": int(group_id),
                        "file": b64_file,
                        "album_id": str(album_id or ""),
                    }
                    if album_name:
                        params["album_name"] = album_name

                    await self.bot.call_action("upload_image_to_qun_album", **params)
                    logger.info(
                        "Base64 回退模式 (upload_image_to_qun_album) 群相册上传成功"
                    )
                    return True
                except Exception as e2:
                    logger.debug(f"Base64 模式 1 失败，尝试模式 2: {e2}")
                    await self.bot.call_action("upload_group_album", **params)
                    logger.info("Base64 回退模式 (upload_group_album) 群相册上传成功")
                    return True

        except Exception as e:
            error_msg = str(e).lower()
            if (
                "not found" in error_msg
                or "not support" in error_msg
                or "不支持" in error_msg
            ):
                logger.debug(f"当前 OneBot 实现不支持群相册上传 API: {e}")
            else:
                logger.warning(f"OneBot 群相册上传失败: {e}")
            return False

    async def get_group_album_list(
        self,
        group_id: str,
    ) -> list[dict]:
        """
        获取群相册列表（NapCat 扩展 API）。

        Args:
            group_id: 目标群号

        Returns:
            list[dict]: 相册列表，每项可能包含 album_id / name 等字段。
                        API 不可用时返回空列表。
        """
        try:
            # 策略 1: 尝试 get_qun_album_list (参考 qun_album 插件)
            try:
                result = await self.bot.call_action(
                    "get_qun_album_list",
                    group_id=int(group_id),
                )
                if result:
                    logger.debug(f"get_qun_album_list 成功: {result}")
                    if isinstance(result, list):
                        return result
                    if isinstance(result, dict):
                        return result.get("albums", []) or result.get("data", []) or []
            except Exception as e:
                logger.debug(f"策略 1 get_qun_album_list 尝试失败: {e}")

            # 策略 2: 尝试 get_group_album_list
            try:
                result = await self.bot.call_action(
                    "get_group_album_list",
                    group_id=int(group_id),
                )
                if result:
                    logger.debug(f"get_group_album_list 成功: {result}")
                    if isinstance(result, list):
                        return result
                    if isinstance(result, dict):
                        return result.get("albums", []) or result.get("data", []) or []
            except Exception as e:
                logger.debug(f"策略 2 get_group_album_list 尝试失败: {e}")

            # 策略 3: 尝试 get_group_albums
            try:
                result = await self.bot.call_action(
                    "get_group_albums",
                    group_id=int(group_id),
                )
                if result:
                    logger.debug(f"get_group_albums 成功: {result}")
                    if isinstance(result, list):
                        return result
                    if isinstance(result, dict):
                        return result.get("albums", []) or result.get("data", []) or []
            except Exception as e:
                logger.debug(f"策略 3 get_group_albums 尝试失败: {e}")

            return []
        except Exception as e:
            logger.debug(f"获取群相册列表最终失败: {e}")
            return []

    async def find_album_id(
        self,
        group_id: str,
        album_name: str,
    ) -> str | None:
        """
        根据相册名称查找 album_id。找不到返回 None（将回退到默认相册）。

        Args:
            group_id: 目标群号
            album_name: 目标相册名称

        Returns:
            str | None: 匹配的 album_id，未找到返回 None
        """
        if not album_name:
            return None

        albums = await self.get_group_album_list(group_id)
        for album in albums:
            name = album.get("name") or album.get("album_name", "")
            aid = album.get("album_id") or album.get("id", "")
            if name == album_name and aid:
                logger.debug(f"找到群相册: {album_name} [ID: {aid}]")
                return str(aid)

        logger.info(f"未找到群相册 '{album_name}' (群 {group_id})，将使用默认相册")
        return None
