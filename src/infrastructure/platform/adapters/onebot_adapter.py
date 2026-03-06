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
                    if start_timestamp <= msg_time <= int(end_time.timestamp()):
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

                # 优先使用 seq_val (针对 LLBot)，如果没有则回退回 ID
                new_anchor_id = seq_val if seq_val is not None else mid_val

                # 如果时间已经超过限制，或者锚点没有变化（说明已经到底），则停止
                if chunk_earliest_time < start_timestamp:
                    logger.debug(
                        f"OneBot 分页拉取：消息时间 ({chunk_earliest_time}) 早于起始时间 ({start_timestamp})，回溯完成。"
                    )
                    break

                if current_anchor_id and str(new_anchor_id) == str(current_anchor_id):
                    logger.debug(
                        "OneBot 分页拉取：消息锚点没有变化，可能已到达历史尽头。"
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
        向群组发送图片消息。

        Args:
            group_id (str): 目标群号
            image_path (str): 图片路径或URL
            caption (str): 图片消息的描述文字

        Returns:
            bool: 是否发送成功
        """
        try:
            use_base64 = False
            plugin = self.config.get("plugin_instance") if self.config else None
            if plugin and hasattr(plugin, "config_manager"):
                use_base64 = plugin.config_manager.get_enable_base64_image()

            base_message = []
            if caption:
                base_message.append({"type": "text", "data": {"text": caption}})

            # 可选策略：开启时，本地文件优先直接转 Base64 发送
            if use_base64 and not image_path.startswith(
                ("http://", "https://", "base64://")
            ):
                b64_str = await self._get_base64_from_file(image_path)
                if b64_str:
                    message = list(base_message)
                    message.append({"type": "image", "data": {"file": b64_str}})
                    await self.bot.call_action(
                        "send_group_msg",
                        group_id=int(group_id),
                        message=message,
                    )
                    logger.info(f"OneBot Base64 直传图片成功: 群 {group_id}")
                    return True
                logger.warning("OneBot Base64 直传失败，将回退到默认路径优先策略")

            # 默认策略（上游现有行为）：
            # 1) 优先尝试物理路径；2) 路径失败则回退 Base64
            file_str = image_path
            if not image_path.startswith(("http://", "https://", "base64://")):
                if os.path.isabs(image_path):
                    # 如果是绝对路径且以 / 开头，只需加 file:// 即可构成 file:///
                    if image_path.startswith("/"):
                        file_str = f"file://{image_path}"
                    else:
                        file_str = f"file:///{image_path}"
                else:
                    # 如果是相对路径，转为绝对路径
                    file_str = f"file:///{os.path.abspath(image_path)}"

            try:
                message = list(base_message)
                message.append({"type": "image", "data": {"file": file_str}})
                await self.bot.call_action(
                    "send_group_msg",
                    group_id=int(group_id),
                    message=message,
                )
                return True
            except Exception as e:
                # 如果是网络图片或 Base64 输入，路径回退无意义，直接失败
                if image_path.startswith(("http://", "https://", "base64://")):
                    raise e

                logger.warning(f"路径发送图片失败 ({e})，尝试 Base64 回退模式...")
                b64_str = await self._get_base64_from_file(image_path)
                if not b64_str:
                    logger.error(f"Base64 回退失败：无法读取图片文件 {image_path}")
                    raise e

                message = list(base_message)
                message.append({"type": "image", "data": {"file": b64_str}})
                await self.bot.call_action(
                    "send_group_msg",
                    group_id=int(group_id),
                    message=message,
                )
                logger.info(f"Base64 回退模式发送图片成功: 群 {group_id}")
                return True

        except Exception as e:
            # 识别 OneBot 的“假失败”情况：如果由于图片过大导致超时，其实图片往往已在后台由 OneBot 自动重传并最终会成功。
            error_str = str(e).lower()
            # 判定为“疑似成功”的特征：超时、1200、网络错误
            is_potential_success = (
                "timeout" in error_str or "1200" in error_str or "网络错误" in error_str
            )

            if is_potential_success:
                logger.warning(
                    f"OneBot 发送群 {group_id} 图片出现疑似超时 ({e})。 "
                    "这通常是因为图片较大导致上传缓慢。如果群内稍后出现了图片，请忽略随后可能的重试提示。"
                )
                return (
                    False  # 返回 False，由上层 RetryManager 接管（带 20s 延迟观察期）
                )

            logger.error(f"OneBot 图片发送最终失败: {e}")
            return False

    async def was_image_sent_recently(
        self, group_id: str, seconds: int = 60, token: str | None = None
    ) -> bool:
        """
        [真相检查] 检查最近 X 秒内，机器人是否已经向该群发送过图片。
        用于判断之前的“超时/1200”错误是否其实已经在后台发送成功。
        """
        try:
            # 1. 获取最近的消息历史 (OneBot 标准 API)
            try:
                history = await self.bot.call_action(
                    "get_group_msg_history",
                    group_id=int(group_id),
                    count=50,  # 适度缩减扫描深度以提高成功率
                )
            except Exception as e:
                logger.warning(
                    f"[OneBot] was_image_sent_recently: get_group_msg_history 失败 (可能 API 繁忙): {e}"
                )
                return False  # API 失败时，我们保持谨慎，但不阻止重试

            if not history or "messages" not in history:
                messages = history if isinstance(history, list) else []
            else:
                messages = history["messages"]

            # 2. 逆序检查
            import time

            now = time.time()
            # 1. 优先从内存缓存中获取机器人 ID
            self_id = self.bot_self_ids[0] if self.bot_self_ids else ""

            if not self_id:
                # 尝试从 bot 实例中获取多个可能的 ID 属性
                self_id = (
                    str(getattr(self.bot, "self_id", ""))
                    or str(getattr(self.bot, "uin", ""))
                    or str(getattr(self.bot, "user_id", ""))
                )

            if not self_id:
                # 最后的 API 兜底：尝试从 login_info 获取
                try:
                    login_info = await self.bot.call_action("get_login_info")
                    if login_info and "user_id" in login_info:
                        self_id = str(login_info["user_id"])
                        # 更新缓存，下次无需重复请求
                        if self_id not in self.bot_self_ids:
                            self.bot_self_ids.append(self_id)
                        logger.info(f"[OneBot] 成功通过 API 获取到机器人 ID: {self_id}")
                except Exception as e:
                    logger.debug(
                        f"[OneBot] was_image_sent_recently: get_login_info API 调用失败: {e}"
                    )

            if not self_id:
                logger.warning(
                    "[OneBot] was_image_sent_recently: 无法确定机器人 ID，历史回显校验可能不准确"
                )

            # [优化] 如果提供了 token，我们也尝试从 caption 中提取 ID 部分进行更精准匹配
            search_token = None
            if token and "[ID: " in token:
                import re

                match = re.search(r"\[ID: ([^\]]+)\]", token)
                if match:
                    search_token = match.group(0)  # 例如 "[ID: report_XXXX]"

            for msg in reversed(messages):
                msg_time = msg.get("time", 0)
                # 只检查约定时间范围内的消息
                if now - msg_time > seconds:
                    break

                # 检查发送者是否是机器人自己
                user_id = str(
                    msg.get("user_id", msg.get("sender", {}).get("user_id", ""))
                )
                if user_id not in self.bot_self_ids:
                    # 如果内存中没有，尝试最后一次实时提取作为兜底
                    if not self_id or user_id != self_id:
                        continue

                # 检查消息内容是否包含图片
                raw_message = msg.get("message", [])
                # 适配字符串形式或列表形式的消息
                msg_str = str(raw_message)

                has_image = "[CQ:image" in msg_str or '"type": "image"' in msg_str

                if has_image:
                    if search_token:
                        # 精确匹配 TraceID
                        if search_token in msg_str:
                            logger.info(
                                f"[OneBot] [真相检查] 发现匹配 ID ({search_token}) 的历史图片。拦截重复发送。群: {group_id}"
                            )
                            return True
                        else:
                            logger.debug(
                                f"[OneBot] [真相检查] 发现机器人发送的图片，但 ID 不匹配。跳过。群: {group_id}"
                            )
                    else:
                        # 广义匹配（回退模式）
                        logger.info(
                            f"[OneBot] [真相检查] 发现近期发送过的图片回显 (广义匹配)。无需重试。群: {group_id}"
                        )
                        return True

            return False
        except Exception as e:
            logger.debug(f"回显自检失败: {e}")
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
                    logger.error(f"Base64 回退失败：无法读取文件 {file_path}")
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
                    logger.error(f"Base64 回退失败：无法读取文件 {file_path}")
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
                    logger.error(f"Base64 回退失败：无法读取图片文件 {image_path}")
                    raise e1

                # 重新尝试两个可能的 API 名
                params = {}
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
