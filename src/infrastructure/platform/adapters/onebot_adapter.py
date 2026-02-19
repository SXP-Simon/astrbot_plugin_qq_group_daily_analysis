"""
OneBot v11 平台适配器

支持 NapCat、go-cqhttp、Lagrange 及其他 OneBot 实现。
"""

import asyncio
import base64
import time
from datetime import datetime, timedelta, timezone
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
        self._context = None
        self._platform_id = (
            str(config.get("platform_id", "") or "").strip() if config else ""
        )

        # 这些值由 ConfigManager 负责边界约束；适配器仅消费已清洗值。
        self._history_batch_size = (
            int(config.get("onebot_history_batch_size", 100) or 100) if config else 100
        )
        self._history_api_max_retries = (
            int(config.get("onebot_history_api_max_retries", 2) or 2) if config else 2
        )
        self._history_retry_backoff_seconds = (
            float(config.get("onebot_history_retry_backoff_seconds", 1.0) or 1.0)
            if config
            else 1.0
        )
        self._history_circuit_breaker_threshold = (
            int(config.get("onebot_history_circuit_breaker_threshold", 3) or 3)
            if config
            else 3
        )
        self._history_circuit_breaker_cooldown_seconds = (
            int(config.get("onebot_history_circuit_breaker_cooldown_seconds", 300) or 300)
            if config
            else 300
        )
        self._history_local_page_size = min(max(self._history_batch_size, 50), 300)

        self._napcat_error_hits = 0
        self._napcat_circuit_open_until = 0.0

    def _init_capabilities(self) -> PlatformCapabilities:
        """返回预定义的 OneBot v11 能力集。"""
        return ONEBOT_V11_CAPABILITIES

    def _get_nearest_size(self, requested_size: int) -> int:
        """从支持的尺寸列表中找到最接近请求尺寸的一个。"""
        return min(self.AVAILABLE_SIZES, key=lambda x: abs(x - requested_size))

    def set_context(self, context: Any) -> None:
        """注入 AstrBot Context，用于优先读取 message_history_manager。"""
        self._context = context

    @staticmethod
    def _is_napcat_video_info_error(err: Exception) -> bool:
        """判断是否命中 NapCat 视频 info 解析异常。"""
        text = str(err).lower()
        return "getgroupvideourl" in text and "reading 'info'" in text

    def _is_napcat_circuit_open(self) -> bool:
        """熔断器是否处于开启状态。"""
        return time.time() < self._napcat_circuit_open_until

    def _record_napcat_failure(self) -> None:
        """记录一次 NapCat 指定错误并必要时触发熔断。"""
        self._napcat_error_hits += 1
        threshold = self._history_circuit_breaker_threshold
        if self._napcat_error_hits < threshold:
            return

        cooldown = self._history_circuit_breaker_cooldown_seconds
        self._napcat_circuit_open_until = time.time() + cooldown
        self._napcat_error_hits = 0
        logger.warning(
            "NapCat 历史接口熔断已开启："
            f"cooldown={cooldown}s"
        )

    def _record_napcat_success(self) -> None:
        """成功后复位错误计数。"""
        self._napcat_error_hits = 0

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

        优先从 AstrBot 的 message_history_manager 读取缓存，
        避免在 NapCat 上调用 get_group_msg_history 触发高负载媒体解析。
        """
        target_count = max(1, int(max_count))

        cached_messages = await self._fetch_messages_from_history_manager(
            group_id=group_id,
            days=days,
            max_count=target_count,
            before_id=before_id,
        )
        if cached_messages:
            return cached_messages

        if self._is_napcat_circuit_open():
            remain = int(self._napcat_circuit_open_until - time.time())
            logger.warning(
                "NapCat 历史接口熔断中，跳过 get_group_msg_history："
                f"group_id={group_id}, remaining={max(remain, 0)}s"
            )
            return []

        return await self._fetch_messages_via_api_with_retry(
            group_id=group_id,
            days=days,
            max_count=target_count,
            before_id=before_id,
        )

    async def _fetch_messages_via_api_with_retry(
        self,
        group_id: str,
        days: int,
        max_count: int,
        before_id: str | None,
    ) -> list[UnifiedMessage]:
        """通过小批次分页 + 退避重试获取 OneBot 历史消息。"""
        if not hasattr(self.bot, "call_action"):
            return []

        max_retries = self._history_api_max_retries
        backoff = self._history_retry_backoff_seconds

        for attempt in range(max_retries + 1):
            try:
                result = await self._fetch_messages_via_api_batched(
                    group_id=group_id,
                    days=days,
                    max_count=max_count,
                    before_id=before_id,
                )
                self._record_napcat_success()
                return result
            except Exception as e:
                is_napcat_error = self._is_napcat_video_info_error(e)
                if is_napcat_error:
                    self._record_napcat_failure()

                if attempt >= max_retries:
                    logger.warning(f"OneBot 获取消息失败（重试耗尽）: {e}")
                    return []

                sleep_s = backoff * (2**attempt)
                logger.warning(
                    "OneBot 获取消息失败，准备重试: "
                    f"attempt={attempt + 1}/{max_retries}, backoff={sleep_s:.1f}s, err={e}"
                )
                await asyncio.sleep(sleep_s)

        return []

    async def _fetch_messages_via_api_batched(
        self,
        group_id: str,
        days: int,
        max_count: int,
        before_id: str | None,
    ) -> list[UnifiedMessage]:
        """使用小批次分页拉取 OneBot 历史消息。"""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        batch_size = min(self._history_batch_size, max_count)

        cursor_seq: int | None = None
        if before_id:
            try:
                cursor_seq = int(before_id)
            except (TypeError, ValueError):
                logger.warning(f"OneBot before_id 无效: {before_id}")

        collected: list[UnifiedMessage] = []
        seen_message_ids: set[str] = set()

        while len(collected) < max_count:
            params: dict[str, Any] = {
                "group_id": int(group_id),
                "count": min(batch_size, max_count - len(collected)),
            }
            if cursor_seq is not None:
                params["message_seq"] = cursor_seq

            result = await self.bot.call_action("get_group_msg_history", **params)
            raw_list = result.get("messages", []) if isinstance(result, dict) else []
            if not raw_list:
                break

            oldest_seq: int | None = None
            added_in_batch = 0

            for raw_msg in raw_list:
                msg_time = datetime.fromtimestamp(raw_msg.get("time", 0))
                if not (start_time <= msg_time <= end_time):
                    continue

                sender_id = str(raw_msg.get("sender", {}).get("user_id", ""))
                if sender_id in self.bot_self_ids:
                    continue

                unified = self._convert_message(raw_msg, group_id)
                if not unified:
                    continue
                if unified.message_id and unified.message_id in seen_message_ids:
                    continue

                if unified.message_id:
                    seen_message_ids.add(unified.message_id)
                collected.append(unified)
                added_in_batch += 1

                seq_candidates = [
                    raw_msg.get("message_seq"),
                    raw_msg.get("real_id"),
                    raw_msg.get("message_id"),
                ]
                for seq in seq_candidates:
                    try:
                        seq_int = int(seq)
                    except (TypeError, ValueError):
                        continue
                    if oldest_seq is None or seq_int < oldest_seq:
                        oldest_seq = seq_int

                if len(collected) >= max_count:
                    break

            if len(raw_list) < params["count"]:
                break
            if added_in_batch == 0:
                break
            if oldest_seq is None:
                break

            next_cursor = oldest_seq - 1
            if cursor_seq is not None and next_cursor >= cursor_seq:
                break
            cursor_seq = next_cursor

        collected.sort(key=lambda m: m.timestamp)
        return collected

    async def _fetch_messages_from_history_manager(
        self,
        group_id: str,
        days: int,
        max_count: int,
        before_id: str | None,
    ) -> list[UnifiedMessage]:
        """优先读取 AstrBot 消息历史，避免触发 NapCat 历史 API 的重型解析。"""
        if not self._context or not hasattr(self._context, "message_history_manager"):
            return []

        try:
            history_mgr = self._context.message_history_manager
            platform_id = self._platform_id or "default"

            before_id_int: int | None = None
            if before_id:
                try:
                    before_id_int = int(before_id)
                except (TypeError, ValueError):
                    logger.warning(f"OneBot before_id 无效: {before_id}")

            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
            page_size = min(max_count, self._history_local_page_size)
            current_page = 1
            messages: list[UnifiedMessage] = []

            while len(messages) < max_count:
                records = await history_mgr.get(
                    platform_id=platform_id,
                    user_id=group_id,
                    page=current_page,
                    page_size=page_size,
                )
                if not records:
                    break

                oldest_record_time: datetime | None = None
                for record in records:
                    if before_id_int is not None:
                        try:
                            if int(record.id) >= before_id_int:
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
                    if msg.sender_id in self.bot_self_ids:
                        continue
                    messages.append(msg)

                if len(messages) >= max_count:
                    break
                if oldest_record_time and oldest_record_time < cutoff_time:
                    break
                if len(records) < page_size:
                    break
                current_page += 1

            messages.sort(key=lambda m: m.timestamp)
            if len(messages) > max_count:
                messages = messages[-max_count:]

            if messages:
                logger.info(
                    f"OneBot 从本地历史缓存读取群 {group_id} 消息: {len(messages)} 条"
                )
            return messages
        except Exception as e:
            logger.warning(f"OneBot 读取本地消息历史失败，将回退 API 拉取: {e}")
            return []

    def _convert_history_record(
        self, record: Any, group_id: str
    ) -> UnifiedMessage | None:
        """将 message_history_manager 记录转换为 UnifiedMessage。"""
        try:
            content = record.content or {}
            message_parts = content.get("message", [])

            text_content = ""
            contents: list[MessageContent] = []
            for part in message_parts:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type", "")
                if part_type in ("plain", "text"):
                    text = str(part.get("text", "") or "")
                    text_content += text
                    contents.append(
                        MessageContent(type=MessageContentType.TEXT, text=text)
                    )
                elif part_type == "image":
                    contents.append(
                        MessageContent(
                            type=MessageContentType.IMAGE,
                            url=part.get("url", "") or part.get("attachment_id", ""),
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
                elif part_type in ("face", "mface", "bface", "sface", "emoji"):
                    contents.append(
                        MessageContent(
                            type=MessageContentType.EMOJI,
                            emoji_id=str(part.get("id", "") or part.get("emoji_id", "")),
                            raw_data={"face_type": part_type},
                        )
                    )

            if not contents:
                fallback_text = str(getattr(record, "message_str", "") or "")
                if fallback_text:
                    text_content = fallback_text
                contents.append(
                    MessageContent(type=MessageContentType.TEXT, text=text_content)
                )

            sender_id = str(getattr(record, "sender_id", "") or "")
            sender_name = str(getattr(record, "sender_name", "") or "").strip()

            return UnifiedMessage(
                message_id=str(getattr(record, "id", "") or ""),
                sender_id=sender_id,
                sender_name=sender_name or sender_id or "Unknown",
                sender_card=None,
                group_id=group_id,
                text_content=text_content,
                contents=tuple(contents),
                timestamp=int(getattr(record, "created_at").timestamp()),
                platform="onebot",
                reply_to_id=None,
            )
        except Exception as e:
            logger.debug(f"OneBot 转换本地历史记录失败: {e}")
            return None

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
            message = []

            if caption:
                message.append({"type": "text", "data": {"text": caption}})

            if image_path.startswith(("http://", "https://")):
                file_str = image_path
            elif image_path.startswith("base64://"):
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
        except Exception as e:
            logger.error(f"OneBot 图片发送失败: {e}")
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
            await self.bot.call_action(
                "upload_group_file",
                group_id=int(group_id),
                file=file_path,
                name=filename or file_path.replace("\\", "/").split("/")[-1],
            )
            return True
        except Exception as e:
            logger.error(f"OneBot 文件发送失败: {e}")
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
