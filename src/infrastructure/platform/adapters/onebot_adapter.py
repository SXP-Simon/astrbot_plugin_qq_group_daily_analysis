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
        """
        super().__init__(bot_instance, config)
        # 支持从多个潜在的配置键中提取机器人 ID
        self.bot_self_ids = (
            [str(id) for id in config.get("bot_self_ids", [])] if config else []
        )
        if not self.bot_self_ids and config:
            self.bot_self_ids = [str(id) for id in config.get("bot_qq_ids", [])]

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
        since_ts: int | None = None,
    ) -> list[UnifiedMessage]:
        """
        从 OneBot 后端拉取群组历史消息。
        采用分页拉取策略（参考 portrayal 插件），减少 NapCat/go-cqhttp 单次请求的 CPU 和内存负担。

        Args:
            group_id (str): 群号
            days (int): 拉取过去几天的消息
            max_count (int): 最大拉取条数
            before_id (str, optional): 锚点消息 ID，用于分页回溯
            since_ts (int, optional): 从指定时间戳开始拉取消息（Unix timestamp），优先级高于 days。

        Returns:
            list[UnifiedMessage]: 统一格式的消息列表
        """
        if not hasattr(self.bot, "call_action"):
            return []

        try:
            chunk_size = 100  # 每次拉取 100 条，较为稳健
            all_raw_messages = []

            # 确定回溯的起始时间点
            if since_ts and since_ts > 0:
                start_timestamp = since_ts
            else:
                end_time_dt = datetime.now()
                start_time_dt = end_time_dt - timedelta(days=days)
                start_timestamp = int(start_time_dt.timestamp())

            # 使用 message_seq 或 message_id 进行分页回溯拉取
            current_anchor_id = before_id

            logger.info(
                f"OneBot 开始分页回溯消息: 群 {group_id}, "
                f"起始时间 {datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S')}, "
                f"上限 {max_count} 条"
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

                # 确定该批次中最旧的消息作为下一次回溯的起点
                # 不同 OneBot 实现对 reverseOrder 的处理可能导致结果顺序不同（反映在消息时间戳上）
                # 我们通过比较首尾消息的时间戳，动态识别出本批次中最旧的消息
                first_msg = messages[0]
                last_msg = messages[-1]
                if first_msg.get("time", 0) <= last_msg.get("time", 0):
                    # 正序：首条消息最旧
                    chunk_earliest_msg = first_msg
                else:
                    # 逆序：末条消息最旧
                    chunk_earliest_msg = last_msg

                chunk_earliest_time = chunk_earliest_msg.get("time", 0)

                for raw_msg in messages:
                    msg_time = raw_msg.get("time", 0)
                    msg_id = str(raw_msg.get("message_id", ""))

                    # 基础过滤：去重
                    if any(
                        str(m.get("message_id", "")) == msg_id for m in all_raw_messages
                    ):
                        continue

                    # 身份过滤（排除机器人自己）
                    sender_id = str(raw_msg.get("sender", {}).get("user_id", ""))
                    if sender_id in self.bot_self_ids:
                        continue

                    # 时间范围判定
                    if start_timestamp <= msg_time <= int(datetime.now().timestamp()):
                        all_raw_messages.append(raw_msg)

                # 提取锚点。
                # 优先级: message_seq > real_id > seq > message_id
                # 注意：为了兼容 NapCat (NTQQ) 这种 Message ID 非连续的情况，
                # 以及 LLBot 这种 Sequence 模式，我们统一不进行 -1 偏移。
                # 分页产生的重叠消息将由上方的去重逻辑 (all_raw_messages 循环对比) 自动处理。
                seq_val = (
                    chunk_earliest_msg.get("message_seq")
                    or chunk_earliest_msg.get("real_id")
                    or chunk_earliest_msg.get("seq")
                )
                mid_val = chunk_earliest_msg.get("message_id")

                # 重要修复：取消对 ID 的 -1 位移手动操作。
                # 在 NapCat/NTQQ 中，ID 虽为数字但并不连续。-1 位移会导致“消息不存在”错误。
                # 即使 API 返回的消息包含锚点本身，上方的 deduplication 逻辑也会将其排除，
                # 保证翻页能正常向前推进。
                new_anchor_id = seq_val if seq_val is not None else mid_val

                # 如果消息时间已到达起始点，或者锚点无法继续往前位移，则停止
                if chunk_earliest_time <= start_timestamp:
                    logger.debug(
                        f"OneBot 分页拉取：已到达起始时间 ({start_timestamp})，回溯同步完成。"
                    )
                    break

                if current_anchor_id and str(new_anchor_id) == str(current_anchor_id):
                    logger.debug(
                        "OneBot 分页拉取：消息锚点未发生有效位移，可能已到达历史尽头。"
                    )
                    break

                current_anchor_id = new_anchor_id
                logger.debug(
                    f"OneBot 分页拉取进度: 已获取 {len(all_raw_messages)} 条基础/有效消息，下一次锚点: {current_anchor_id}"
                )

                # 稍微延迟，减缓服务端压力
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
                    # QQ 平台: subType=1 表示表情包，通过 raw_data 传递给下游统计
                    sub_type = seg_data.get("subType", seg_data.get("sub_type"))
                    # 安全地转换为整数，防止非数字值导致异常
                    try:
                        is_sticker = int(sub_type) == 1
                    except (TypeError, ValueError):
                        is_sticker = False
                    # 只在 sub_type 有效时包含在 raw_data 中
                    raw_data: dict[str, Any] = {"summary": seg_data.get("summary", "")}
                    if sub_type is not None:
                        raw_data["sub_type"] = int(sub_type)
                    contents.append(
                        MessageContent(
                            type=MessageContentType.EMOJI
                            if is_sticker
                            else MessageContentType.IMAGE,
                            url=seg_data.get("url", seg_data.get("file", "")),
                            raw_data=raw_data,
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

    async def _execute_transmission_strategy(
        self,
        path: str,
        worker: Any,
        label: str,
        format_path_as_url: bool = False,
    ) -> bool:
        """
        通用传输策略执行器。
        处理 Base64 优先（开启时）、物理路径尝试、以及 Base64 兜底。

        Args:
            path: 文件路径或 URL
            worker: 执行具体 API 调用的异步函数，接收 (file_val, mode_label) -> Awaitable[None]
            label: 业务标签，用于日志
            format_path_as_url: 是否将本地路径格式化为 file:/// 形式
        """
        try:
            use_base64 = self._get_use_base64()
            abs_path, is_remote, exists = self._prepare_path(path)

            # 1. 优先尝试 Base64 (如果开启)
            if use_base64 and not is_remote:
                b64 = await self._get_base64_from_file(abs_path)
                if b64:
                    try:
                        await worker(b64, "Base64 优先")
                        return True
                    except Exception:
                        pass

            # 2. 尝试物理路径/远程 URL
            if exists:
                try:
                    file_val = abs_path
                    if not is_remote and format_path_as_url:
                        file_val = (
                            f"file://{abs_path}"
                            if abs_path.startswith("/")
                            else f"file:///{abs_path}"
                        )
                    await worker(file_val, "路径模式")
                    return True
                except Exception as e:
                    if not use_base64:
                        logger.error(f"[{label}] 发送失败: {e}")
                        return False
                    logger.warning(f"[{label}] 路径发送失败 ({e})，准备 Base64 补救...")
            else:
                if not use_base64:
                    logger.error(f"[{label}] 文件不存在且未开启 Base64: {abs_path}")
                    return False

            # 3. 兜底回退
            if not is_remote:
                b64 = await self._get_base64_from_file(abs_path)
                if b64:
                    await worker(b64, "Base64 补发")
                    return True

            return False
        except Exception as e:
            logger.error(f"[{label}] 发送异常: {e}")
            return False

    async def send_image(
        self,
        group_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """向群组发送图片消息。"""

        async def do_send(file_val: str, label: str):
            msg = []
            if caption:
                msg.append({"type": "text", "data": {"text": caption}})
            msg.append({"type": "image", "data": {"file": file_val}})
            await self.bot.call_action(
                "send_group_msg", group_id=int(group_id), message=msg
            )
            logger.debug(f"[OneBot] 图片发送成功 ({label}): 群 {group_id}")

        return await self._execute_transmission_strategy(
            image_path, do_send, "OneBot 图片", format_path_as_url=True
        )

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: str | None = None,
    ) -> bool:
        """通过群文件功能上传并发送文件。"""

        async def do_upload(content: str, label: str):
            await self.bot.call_action(
                "upload_group_file",
                group_id=int(group_id),
                file=content,
                name=filename or os.path.basename(file_path),
            )
            logger.debug(f"[OneBot] 文件发送成功 ({label}): {filename or file_path}")

        return await self._execute_transmission_strategy(
            file_path, do_upload, "OneBot 文件"
        )

    async def send_forward_msg(
        self,
        group_id: str,
        nodes: list[dict],
    ) -> bool:
        """
        发送群合并转发消息。
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
            logger.warning(f"[OneBot] 发送合并转发消息失败: {e}")
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
        """上传文件到群文件目录的指定子文件夹。"""

        async def do_upload(content: str, label: str):
            params = {
                "group_id": int(group_id),
                "file": content,
                "name": filename or os.path.basename(file_path),
            }
            if folder_id:
                params["folder"] = folder_id
            await self.bot.call_action("upload_group_file", **params)
            logger.debug(f"[OneBot] 群文件发送成功 ({label}): {params['name']}")

        return await self._execute_transmission_strategy(
            file_path, do_upload, "OneBot 群文件"
        )

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
        strict_mode: bool = False,
    ) -> bool:
        """上传图片到群相册（NapCat 扩展 API）。"""
        # 严格模式：指定了相册名但未解析到 album_id 时，禁止上传
        if strict_mode and album_name and not album_id:
            logger.info(
                f"[群分析相册] 严格模式开启：未找到相册 '{album_name}' (群 {group_id})，停止上传。"
            )
            return False

        # 兜底查询
        if not album_id:
            albums = await self.get_group_album_list(group_id)
            album_id = self._find_item_in_list(
                albums, album_name, ["album_id", "id"], ["name", "album_name"]
            )
            # 如果仍没指定且没搜到特定相册，取第一个
            if not album_id and not album_name and albums:
                album_id = albums[0].get("album_id") or albums[0].get("id")

        if not album_id:
            logger.info(
                f"[群分析相册] 未能确定目标相册 (群 {group_id})，跳过相册上传。"
            )
            return False

        async def do_upload(content: str, label: str):
            params = {
                "group_id": int(group_id),
                "file": content,
                "album_id": str(album_id),
            }
            if album_name:
                params["album_name"] = album_name

            for action in [
                "upload_image_to_qun_album",
                "upload_group_album",
                "upload_qun_album",
            ]:
                try:
                    await self.bot.call_action(action, **params)
                    logger.debug(
                        f"[群分析相册] 上传成功 ({label}, {action}): 群 {group_id}"
                    )
                    return
                except Exception:
                    continue
            raise RuntimeError("所有相册上传 API 均调用失败")

        return await self._execute_transmission_strategy(
            image_path, do_upload, "OneBot 相册"
        )

    async def get_group_album_list(
        self,
        group_id: str,
    ) -> list[dict]:
        """
        获取群分析相册列表（兼容多种 OneBot 扩展实现）。
        """

        def extract_list(data: Any) -> list[dict]:
            if not data:
                return []
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # 探测常见键名
                lst = (
                    data.get("albums")
                    or data.get("album_list")
                    or data.get("albumList")
                    or data.get("list")
                    or []
                )
                if isinstance(lst, list):
                    return lst
                # 如果 'data' 键本身存在且为列表
                inner_data = data.get("data")
                if isinstance(inner_data, list):
                    return inner_data
                if isinstance(inner_data, dict):
                    return extract_list(inner_data)
            return []

        # 候选 API 名称
        actions = [
            "get_qun_album_list",
            "get_group_album_list",
            "get_group_albums",
            "get_group_root_album_list",
        ]

        for action in actions:
            try:
                logger.debug(
                    f"[群分析相册] 正在通过 {action} 获取列表 (群: {group_id})..."
                )
                result = await self.bot.call_action(
                    action,
                    group_id=int(group_id),  # 确保传整型，对齐 NapCat 等实现
                )
                if result:
                    albums = extract_list(result)
                    if albums:
                        logger.debug(
                            f"[群分析相册] {action} 成功获取到 {len(albums)} 个相册"
                        )
                        return albums
            except Exception as e:
                logger.debug(f"[群分析相册] 接口 {action} 尝试失败: {e}")

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

        logger.debug(
            f"[群分析相册] 正在群 {group_id} 中查找名为 '{album_name}' 的相册..."
        )
        albums = await self.get_group_album_list(group_id)
        for album in albums:
            name = album.get("name") or album.get("album_name", "")
            aid = album.get("album_id") or album.get("id", "")
            if name == album_name and aid:
                logger.info(f"[群分析相册] 成功定位相册: '{album_name}' -> ID: {aid}")
                return str(aid)

        logger.info(f"[群分析相册] 未能找到名为 '{album_name}' 的相册 (群 {group_id})")
        return None

    async def set_reaction(
        self, group_id: str, message_id: str, emoji: str | int, is_add: bool = True
    ) -> bool:
        """
        OneBot 实现消息回应 (set_msg_emoji_like)。
        支持 Go-CQHTTP, NapCat, Lagrange 等 OneBot 实现。
        """
        try:
            reaction_key = str(emoji)
            emoji_id = {
                "analysis_started": "289",  # 🫣 表情 (表示任务已接收)
                "analysis_done": "124",  # 👌 表情 (表示任务处理完成)
                "🔍": "289",
                "📊": "124",
            }.get(reaction_key, reaction_key)

            await self.bot.call_action(
                "set_msg_emoji_like",
                message_id=int(message_id),
                emoji_id=emoji_id,
                emoji_type="1",  # 还原为最稳定的系统表情类型
                set=is_add,
            )
            return True
        except Exception as e:
            logger.debug(f"OneBot set_reaction 失败 (API 可能不支持): {e}")
            return False

    def _get_use_base64(self) -> bool:
        """从插件配置中获取是否启用 Base64"""
        plugin: Any = self.config.get("plugin_instance") if self.config else None
        if plugin and hasattr(plugin, "config_manager"):
            return plugin.config_manager.get_enable_base64_image()
        return False

    def _prepare_path(self, path: str) -> tuple[str, bool, bool]:
        """统一路径预处理。返回: (标准化后的绝对路径, 是否为远程/编码路径, 本地文件是否存在)"""
        is_remote = path.startswith(("http://", "https://", "base64://"))
        if is_remote:
            return path, True, True

        abs_path = os.path.abspath(path)
        exists = os.path.exists(abs_path)
        return abs_path, False, exists

    def _find_item_in_list(
        self,
        items: list[dict],
        target_name: str | None,
        id_keys: list[str],
        name_keys: list[str],
    ) -> str | None:
        """从对象列表中根据名称查找 ID (通用辅助函数)"""
        if not target_name:
            return None

        for item in items:
            name = ""
            for nk in name_keys:
                if item.get(nk):
                    name = item[nk]
                    break

            if name == target_name:
                for ik in id_keys:
                    if item.get(ik):
                        return str(item[ik])
        return None
