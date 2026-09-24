"""
OneBot v11 平台适配器

支持 NapCat、go-cqhttp、Lagrange 及其他 OneBot 实现。
"""

import asyncio
import base64
import os
import time
from datetime import datetime
from pathlib import Path
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
from .onebot import (
    OneBotDriver,
    OneBotDriverFactory,
    StandardOneBotDriver,
)


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

    # 协议端头像获取：单请求超时、成功缓存与失败负缓存的存活时间（秒）
    AVATAR_FETCH_TIMEOUT = 1.5
    AVATAR_URL_TTL = 3600.0
    AVATAR_NEGATIVE_TTL = 600.0

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
        self.filter_bot_messages = (
            config.get("filter_bot_messages", True) if config else True
        )

        # 协议端方言驱动（默认使用标准驱动，首次调用时通过 _ensure_driver 自动探测）
        self._driver: OneBotDriver = StandardOneBotDriver()
        self._driver_detected = False
        self._driver_detection_lock = asyncio.Lock()

        # 禁言状态缓存 (group_id -> timestamp)
        self._muted_groups_cache = {}
        # 群角色缓存 (group_id -> (role, timestamp))，用于 get_group_member_info 超时降级
        self._group_role_cache: dict[str, tuple[str, float]] = {}
        # 协议端头像缓存 (uid -> (url, expires_at))；负缓存 (uid -> expires_at)
        self._avatar_url_cache: dict[str, tuple[str, float]] = {}
        self._avatar_url_negative_cache: dict[str, float] = {}
        # 并发去重 (uid -> in-flight Task)，同一用户并发请求只触发一次协议调用
        self._avatar_inflight_tasks: dict[str, asyncio.Task[str | None]] = {}

    def _init_capabilities(self) -> PlatformCapabilities:
        """返回预定义的 OneBot v11 能力集。"""
        return ONEBOT_V11_CAPABILITIES

    async def _ensure_driver(self) -> OneBotDriver:
        """确保并返回已探测适配的协议端方言驱动（带并发锁保护）。"""
        if not self._driver_detected:
            async with self._driver_detection_lock:
                if not self._driver_detected:
                    self._driver = await OneBotDriverFactory.detect_driver(self.bot)
                    self._driver_detected = True
        return self._driver

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

        driver = await self._ensure_driver()

        try:
            chunk_size = 100  # 每次拉取 100 条，较为稳健
            all_raw_messages = []
            seen_raw_ids: set[str] = set()

            # 确定回溯的起始时间点（以配置的 days 作为最远回溯边界，避免 since_ts 跨天/长期停机时越界拉取）
            start_timestamp = self.calculate_effective_start_timestamp(
                days=days, since_ts=since_ts
            )

            # 使用 message_seq 或 message_id 进行分页回溯拉取
            current_anchor_id = before_id

            logger.info(
                f"OneBot 开始分页回溯消息 (驱动: {driver.name}): 群 {group_id}, "
                f"起始时间 {datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S')}, "
                f"上限 {max_count} 条"
            )

            while len(all_raw_messages) < max_count:
                fetch_count = min(chunk_size, max_count - len(all_raw_messages))
                params = driver.build_history_params(
                    group_id=group_id,
                    count=fetch_count,
                    anchor_id=current_anchor_id,
                )
                logger.debug(
                    f"OneBot 分页请求 (驱动: {driver.name}): group_id={group_id}, params={params}"
                )

                result = None
                fetch_error = None
                # 单页请求最多尝试三次，避免 NapCat 偶发 WebSocket 超时导致整次分析失败。
                for attempt in range(1, 4):
                    try:
                        result = await self.bot.call_action(
                            "get_group_msg_history", **params
                        )
                        fetch_error = None
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        fetch_error = exc
                        if attempt < 3:
                            logger.warning(
                                f"OneBot 分页拉取失败，将进行第 {attempt + 1} 次尝试："
                                f"群 {group_id}，错误：{exc}"
                            )
                            await asyncio.sleep(attempt)

                if fetch_error is not None:
                    if all_raw_messages:
                        logger.warning(
                            f"OneBot 分页拉取重试耗尽，停止继续回溯并处理已获取的 "
                            f"{len(all_raw_messages)} 条消息：群 {group_id}，错误：{fetch_error}"
                        )
                    else:
                        logger.warning(
                            f"OneBot 分页拉取重试耗尽，且尚未获取到消息："
                            f"群 {group_id}，错误：{fetch_error}"
                        )
                    break

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

                    # 使用集合去重分页重叠消息，避免消息量较大时反复线性扫描。
                    if not msg_id or msg_id in seen_raw_ids:
                        continue

                    # 时间范围判定与集合去重
                    if start_timestamp <= msg_time <= int(datetime.now().timestamp()):
                        all_raw_messages.append(raw_msg)
                        seen_raw_ids.add(msg_id)

                # 由当前驱动提取回溯锚点
                new_anchor_id = driver.extract_history_anchor(chunk_earliest_msg)

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
        """将统一格式转换回 OneBot v11 原生字典格式。

        Args:
            messages: 统一消息列表。

        Returns:
            list[dict]: OneBot 格式的消息字典列表。
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
            self._record_mute_status(group_id, False)  # 成功发送，清除禁言缓存
            return True
        except Exception as e:
            if self._is_mute_exception(e):
                self._record_mute_status(group_id, True)
            logger.error(f"OneBot 文本发送失败: {e}")
            return False

    def _is_send_timeout(self, e: Exception) -> bool:
        """判断是否为 NapCat/NTQQ 客户端发送超时。

        当 NapCat 上传大图到 QQ 服务器耗时超过动作等待时间时，
        NT 消息服务实际上已经将消息接收并入队发送。此时若盲目重试会直接导致群内重复发送多张。
        """
        if not e:
            return False
        err_str = str(e).lower()
        if "timeout" in err_str or "timed out" in err_str:
            return True
        if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
            return True
        for attr in ("message", "wording"):
            val = str(getattr(e, attr, "") or "").lower()
            if "timeout" in val or "nodeikernelmsgservice/sendmsg" in val:
                return True
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
        严格限制同一模式最多尝试 1 次，并在捕获 NT 发送超时时避免触发重发刷屏。

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
                    except Exception as e:
                        if self._is_send_timeout(e):
                            logger.warning(
                                f"[{label}] Base64 优先发送请求超时（NT 消息服务已接收，为避免重复投递不再重发）: {e}"
                            )
                            return True
                        logger.warning(
                            f"[{label}] Base64 优先发送失败 ({e})，准备尝试路径模式..."
                        )

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
                    if self._is_send_timeout(e):
                        logger.warning(
                            f"[{label}] 路径模式发送请求超时（NT 消息服务已接收，为避免重复投递不再重发）: {e}"
                        )
                        return True
                    if not use_base64 and not is_remote:
                        logger.warning(
                            f"[{label}] 路径发送失败 ({e})，准备 Base64 补救..."
                        )
                    else:
                        logger.error(f"[{label}] 发送失败: {e}")
                        return False
            else:
                if not use_base64:
                    logger.error(f"[{label}] 文件不存在且未开启 Base64: {abs_path}")
                    return False

            # 3. 兜底回退：仅当第一步未尝试过 Base64 时才执行
            if not use_base64 and not is_remote:
                b64 = await self._get_base64_from_file(abs_path)
                if b64:
                    try:
                        await worker(b64, "Base64 补发")
                        return True
                    except Exception as e:
                        if self._is_send_timeout(e):
                            logger.warning(
                                f"[{label}] Base64 补发请求超时（NT 消息服务已接收，为避免重复投递不再重发）: {e}"
                            )
                            return True
                        logger.error(f"[{label}] Base64 补发失败: {e}")
                        return False

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
            try:
                await self.bot.call_action(
                    "send_group_msg", group_id=int(group_id), message=msg
                )
                self._record_mute_status(group_id, False)
            except Exception as e:
                if self._is_mute_exception(e):
                    self._record_mute_status(group_id, True)
                raise
            logger.debug(f"[OneBot] 图片发送成功 ({label}): 群 {group_id}")

        sent = await self._execute_transmission_strategy(
            image_path, do_send, "OneBot 图片", format_path_as_url=True
        )
        if sent:
            return True

        stream_threshold = self._get_napcat_stream_threshold_bytes()
        path = Path(image_path)
        if (
            stream_threshold <= 0
            or not path.is_file()
            or path.stat().st_size < stream_threshold
        ):
            return False

        driver = await self._ensure_driver()
        uploaded_path = await driver.upload_stream_file(self.bot, path)
        if not uploaded_path:
            return False

        logger.warning(
            "[OneBot] 常规图片发送失败: %s，准备通过 NapCat Stream API 重试",
            path.name,
        )
        try:
            await do_send(uploaded_path, "NapCat 流式上传重试")
            return True
        except Exception as exc:
            logger.warning(f"[OneBot] NapCat 流式上传图片重试失败: {exc}")
            return False

    async def send_file(
        self,
        group_id: str,
        file_path: str,
        filename: str | None = None,
    ) -> bool:
        """通过群文件功能上传并发送文件。"""

        async def do_upload(content: str, label: str):
            try:
                await self.bot.call_action(
                    "upload_group_file",
                    group_id=int(group_id),
                    file=content,
                    name=filename or os.path.basename(file_path),
                )
                self._record_mute_status(group_id, False)
            except Exception as e:
                if self._is_mute_exception(e):
                    self._record_mute_status(group_id, True)
                raise
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
            self._record_mute_status(group_id, False)
            return True
        except Exception as e:
            if self._is_mute_exception(e):
                self._record_mute_status(group_id, True)
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

            info = result
            if isinstance(result, dict) and isinstance(result.get("data"), dict):
                info = result["data"]

            return UnifiedGroup(
                group_id=str(info.get("group_id", group_id)),
                group_name=info.get("group_name", ""),
                member_count=info.get("member_count", 0),
                owner_id=str(info.get("owner_id", "")) or None,
                create_time=info.get("group_create_time"),
                platform="onebot",
            )
        except Exception as e:
            logger.debug(f"[OneBot] 获取群 {group_id} 信息失败: {e}")
            return None

    async def get_group_list(self) -> list[str]:
        """获取当前机器人已加入的所有群组 ID 列表。"""
        try:
            result = await self.bot.call_action("get_group_list")
            groups: list[dict] = []
            if isinstance(result, list):
                groups = [g for g in result if isinstance(g, dict)]
            elif isinstance(result, dict):
                data = result.get("data")
                if isinstance(data, list):
                    groups = [g for g in data if isinstance(g, dict)]
                elif isinstance(data, dict):
                    raw = data.get("group_list") or data.get("list")
                    if isinstance(raw, list):
                        groups = [g for g in raw if isinstance(g, dict)]
                if not groups:
                    raw = result.get("group_list") or result.get("list")
                    if isinstance(raw, list):
                        groups = [g for g in raw if isinstance(g, dict)]
            return [str(g.get("group_id", "")) for g in groups if g.get("group_id")]
        except Exception as e:
            logger.debug(f"[OneBot] 获取群列表失败: {e}")
            return []

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        """拉取整个群组成员列表。"""
        try:
            result = await self.bot.call_action(
                "get_group_member_list",
                group_id=int(group_id),
            )

            raw_members: list[dict] = []
            if isinstance(result, list):
                raw_members = [m for m in result if isinstance(m, dict)]
            elif isinstance(result, dict):
                data = result.get("data")
                if isinstance(data, list):
                    raw_members = [m for m in data if isinstance(m, dict)]
                elif isinstance(data, dict):
                    raw = (
                        data.get("member_list")
                        or data.get("members")
                        or data.get("list")
                    )
                    if isinstance(raw, list):
                        raw_members = [m for m in raw if isinstance(m, dict)]
                if not raw_members:
                    raw = (
                        result.get("member_list")
                        or result.get("members")
                        or result.get("list")
                    )
                    if isinstance(raw, list):
                        raw_members = [m for m in raw if isinstance(m, dict)]

            members = []
            for m in raw_members:
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
        except Exception as e:
            logger.debug(f"[OneBot] 获取群 {group_id} 成员列表失败: {e}")
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

            info = result
            if isinstance(result, dict) and isinstance(result.get("data"), dict):
                info = result["data"]

            return UnifiedMember(
                user_id=str(info.get("user_id", user_id)),
                nickname=info.get("nickname", ""),
                card=info.get("card", "") or None,
                role=info.get("role", "member"),
                join_time=info.get("join_time"),
            )
        except Exception as e:
            logger.debug(f"[OneBot] 获取群 {group_id} 成员 {user_id} 信息失败: {e}")
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

    @staticmethod
    def _extract_protocol_avatar_url(payload: Any) -> str | None:
        """从协议端用户资料响应中提取头像 URL。"""
        if not isinstance(payload, dict):
            return None
        targets: list[dict[str, Any]] = [payload]
        if isinstance(payload.get("data"), dict):
            targets.append(payload["data"])
        for target in targets:
            for key in (
                "avatar_url",
                "avatar",
                "headimgurl",
                "head_img",
                "user_avatar",
            ):
                value = target.get(key)
                if not isinstance(value, str):
                    continue
                text = value.strip()
                if text.startswith(("http://", "https://")):
                    return text
        return None

    async def _fetch_avatar_url_from_protocol(self, user_id: str) -> str | None:
        """
        通过协议端资料接口获取真实头像 URL。

        部分 OneBot 实现（桥接、映射 ID 场景）的用户 ID 不是真实 QQ 号，
        官方 CDN 地址只会返回默认头像；此类实现通常会在
        get_stranger_info / get_user_info 响应中携带真实头像。
        """
        uid_text = str(user_id).strip()
        uid_param: int | str = int(uid_text) if uid_text.isdigit() else uid_text
        for action_name in ("get_stranger_info", "get_user_info"):
            try:
                result = await asyncio.wait_for(
                    self.bot.call_action(action_name, user_id=uid_param),
                    timeout=self.AVATAR_FETCH_TIMEOUT,
                )
            except Exception as exc:
                logger.debug(
                    f"[OneBot] {action_name} 获取头像失败 user_id={user_id}: {exc}"
                )
                continue
            url = self._extract_protocol_avatar_url(result)
            if url:
                logger.debug(
                    f"[OneBot] {action_name} 成功获取到真实头像 URL: user_id={user_id}, url={url}"
                )
                return url
            logger.debug(
                f"[OneBot] {action_name} 响应中未包含可用头像字段 (user_id={user_id})"
            )
        return None

    async def _fetch_avatar_url_shared(self, user_id: str) -> str | None:
        """获取协议端头像 URL；同一用户的并发请求共享同一个 in-flight 任务。"""
        task = self._avatar_inflight_tasks.get(user_id)
        if task is None:
            task = asyncio.create_task(self._fetch_avatar_url_from_protocol(user_id))
            self._avatar_inflight_tasks[user_id] = task
        try:
            return await task
        finally:
            if self._avatar_inflight_tasks.get(user_id) is task:
                self._avatar_inflight_tasks.pop(user_id, None)

    def _build_cdn_avatar_url(self, user_id: str, size: int) -> str:
        return self._driver.build_user_avatar_cdn_url(user_id, size)

    async def get_user_avatar_url(
        self,
        user_id: str,
        size: int = 100,
    ) -> str | None:
        """
        获取用户头像 URL。

        优先使用协议端返回的真实头像（成功缓存 1 小时），失败时回退
        QQ 官方 CDN 地址。纯 QQ 场景下协议端返回的即官方地址，行为与
        原实现一致。

        Args:
            user_id (str): QQ 号
            size (int): 期望像素大小

        Returns:
            str: 格式化后的 URL
        """
        uid = str(user_id).strip()
        if not uid:
            return None

        cached = self._avatar_url_cache.get(uid)
        if cached:
            url, expires_at = cached
            if time.monotonic() < expires_at:
                logger.debug(f"[OneBot] 用户 {uid} 命中头像正缓存: {url}")
                return url
            logger.debug(f"[OneBot] 用户 {uid} 头像正缓存已过期，准备重新获取")
            self._avatar_url_cache.pop(uid, None)

        negative_until = self._avatar_url_negative_cache.get(uid, 0.0)
        if time.monotonic() < negative_until:
            cdn_url = self._build_cdn_avatar_url(uid, size)
            logger.debug(
                f"[OneBot] 用户 {uid} 处于负缓存期内 (剩余 {negative_until - time.monotonic():.1f}s)，"
                f"跳过协议端查询直接回退 QQ CDN: {cdn_url}"
            )
            return cdn_url

        protocol_url = await self._fetch_avatar_url_shared(uid)
        if protocol_url:
            self._avatar_url_cache[uid] = (
                protocol_url,
                time.monotonic() + self.AVATAR_URL_TTL,
            )
            self._avatar_url_negative_cache.pop(uid, None)
            return protocol_url

        # 负缓存 10 分钟，避免协议端不支持资料接口时反复超时
        self._avatar_url_negative_cache[uid] = (
            time.monotonic() + self.AVATAR_NEGATIVE_TTL
        )
        cdn_url = self._build_cdn_avatar_url(uid, size)
        logger.debug(
            f"[OneBot] 用户 {uid} 协议端未提供头像，写入负缓存({self.AVATAR_NEGATIVE_TTL}s)，回退 QQ CDN: {cdn_url}"
        )
        return cdn_url

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
        return self._driver.build_group_avatar_cdn_url(group_id, size)

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

    async def is_group_muted(self, group_id: str) -> bool:
        """
        检查 OneBot 平台下的群聊是否被禁言（包括全体禁言或对 Bot 自身禁言）。
        """
        group_id_str = str(group_id)

        # 1. 检查最近缓存的禁言状态（5分钟内有效）
        last_mute_time = self._muted_groups_cache.get(group_id_str)
        if last_mute_time and (time.time() - last_mute_time) < 300:
            logger.info(
                f"[OneBot] 从缓存中检测到群 {group_id_str} 最近处于禁言状态，跳过分析"
            )
            return True

        if not hasattr(self.bot, "call_action"):
            return False

        # 确保方言驱动已探测并绑定
        await self._ensure_driver()

        # 2. 获取 Bot 自身的 QQ 号，并过滤掉非法的字符串（如 functools.partial 或含字母/特殊字符的异常值）
        bot_user_id = None
        if self.bot_self_ids:
            valid_ids = [
                str(uid)
                for uid in self.bot_self_ids
                if uid
                and isinstance(uid, (str, int))
                and not callable(uid)
                and "partial" not in str(uid)
                and str(uid).isdigit()
            ]
            if valid_ids:
                bot_user_id = valid_ids[0]

        if not bot_user_id:
            try:
                # 设定 5.0 秒超时，防止接口请求无限挂起
                login_info = await asyncio.wait_for(
                    self.bot.call_action("get_login_info"), timeout=5.0
                )
                if login_info:
                    info = (
                        login_info.get("data")
                        if isinstance(login_info, dict)
                        and isinstance(login_info.get("data"), dict)
                        else login_info
                    )
                    if isinstance(info, dict) and "user_id" in info:
                        bot_user_id = str(info["user_id"])
                        self.bot_self_ids = [bot_user_id]
            except Exception as e:
                if self._is_mute_exception(e):
                    self._record_mute_status(group_id, True)
                    logger.info(
                        f"[OneBot] 从 get_login_info 异常中检测到 Bot 在群 {group_id} 中已被禁言"
                    )
                    return True
                logger.warning(f"[OneBot] 获取 Bot 自身登录信息失败: {e}")

        # 3. 检查 Bot 是否被个人禁言，并获取 Bot 在群内的角色
        is_individually_muted = False
        role = "member"  # 默认为 member 以防万一
        if bot_user_id:
            try:
                # 设定 5.0 秒超时，且不传递 no_cache=True 以免强制向腾讯服务器同步导致高延时超时
                member_info = await asyncio.wait_for(
                    self.bot.call_action(
                        "get_group_member_info",
                        group_id=int(group_id),
                        user_id=int(bot_user_id),
                    ),
                    timeout=5.0,
                )
                if member_info:
                    info = (
                        member_info.get("data")
                        if isinstance(member_info, dict)
                        and isinstance(member_info.get("data"), dict)
                        else member_info
                    )
                    if isinstance(info, dict):
                        role = info.get("role", "member")
                        # 缓存角色信息，用于 get_group_member_info 超时时降级使用
                        self._group_role_cache[group_id_str] = (role, time.time())
                        shut_up_time = info.get("shut_up_time", 0)
                        if shut_up_time > 0:
                            # 如果 shut_up_time 是 Unix 时间戳
                            if shut_up_time > 1000000000:
                                if shut_up_time > time.time():
                                    is_individually_muted = True
                            else:
                                # 否则认为是相对禁言剩余时间（秒）
                                is_individually_muted = True
            except TimeoutError:
                # 超时降级：优先使用缓存的角色（角色几乎不会变）
                cached_role = self._group_role_cache.get(group_id_str)
                if cached_role:
                    role = cached_role[0]
                    logger.warning(
                        f"[OneBot] 获取群成员信息超时，使用缓存角色: {role} (group_id={group_id}, user_id={bot_user_id})"
                    )
                else:
                    logger.warning(
                        f"[OneBot] 获取群成员信息超时且无角色缓存，将按 member 处理 (group_id={group_id}, user_id={bot_user_id})"
                    )
            except Exception as e:
                if self._is_mute_exception(e):
                    self._record_mute_status(group_id, True)
                    logger.info(
                        f"[OneBot] 从 get_group_member_info 异常中检测到 Bot 在群 {group_id} 中已被禁言"
                    )
                    return True
                logger.warning(
                    f"[OneBot] 获取群成员信息失败 (group_id={group_id}, user_id={bot_user_id}): {e}"
                )

        if is_individually_muted:
            self._record_mute_status(group_id, True)
            logger.info(f"[OneBot] 检测到 Bot 在群 {group_id} 中已被单独禁言")
            return True

        # 4. 如果 Bot 不是管理员或群主，则需要检查群聊是否开启了全群禁言
        # 管理员 (admin) 和群主 (owner) 在全群禁言下依然可以发言
        if role not in ("admin", "owner"):
            try:
                # 设定 5.0 秒超时，不传 no_cache=True
                group_info = await asyncio.wait_for(
                    self.bot.call_action(
                        "get_group_info",
                        group_id=int(group_id),
                    ),
                    timeout=5.0,
                )
                if group_info:
                    info = (
                        group_info.get("data")
                        if isinstance(group_info, dict)
                        and isinstance(group_info.get("data"), dict)
                        else group_info
                    )
                    if isinstance(info, dict):
                        driver = await self._ensure_driver()
                        if driver.is_whole_ban(info):
                            self._record_mute_status(group_id, True)
                            logger.info(
                                f"[OneBot] 检测到群 {group_id} 开启了全群禁言，且 Bot 为普通成员"
                            )
                            return True
            except TimeoutError:
                logger.warning(f"[OneBot] 获取群信息超时 (group_id={group_id})")
            except Exception as e:
                if self._is_mute_exception(e):
                    self._record_mute_status(group_id, True)
                    logger.info(
                        f"[OneBot] 从 get_group_info 异常中检测到 Bot 在群 {group_id} 中已被禁言"
                    )
                    return True
                logger.warning(f"[OneBot] 获取群信息失败 (group_id={group_id}): {e}")

        # 如果所有检测均未发现禁言，则暂时视为未禁言
        return False

    def _is_mute_exception(self, e: Exception) -> bool:
        """判断是否为禁言异常（委派给当前绑定的协议端驱动）。"""
        return self._driver.is_mute_exception(e)

    def _record_mute_status(self, group_id: Any, is_muted: bool):
        group_id_str = str(group_id)
        if is_muted:
            # Prune expired cache entries if cache size grows too large (threshold of 1000)
            if len(self._muted_groups_cache) >= 1000:
                now = time.time()
                expired_keys = [
                    k for k, t in self._muted_groups_cache.items() if now - t >= 300
                ]
                for k in expired_keys:
                    self._muted_groups_cache.pop(k, None)

                # If still over threshold, evict the oldest entry to prevent unbounded growth
                if len(self._muted_groups_cache) >= 1000:
                    oldest_key = min(
                        self._muted_groups_cache,
                        key=lambda k: self._muted_groups_cache[k],
                    )
                    self._muted_groups_cache.pop(oldest_key, None)

            self._muted_groups_cache[group_id_str] = time.time()
        else:
            self._muted_groups_cache.pop(group_id_str, None)

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
        target_filename = filename or os.path.basename(file_path)
        logger.debug(
            f"[OneBot] 正在上传群文件 (群 {group_id}): 文件='{file_path}', 目标文件名='{target_filename}', 目标文件夹 ID='{folder_id}'"
        )

        async def do_upload(content: str, label: str):
            params = {
                "group_id": int(group_id),
                "file": content,
                "name": target_filename,
            }
            if folder_id:
                params["folder"] = folder_id
            await self.bot.call_action("upload_group_file", **params)
            logger.info(
                f"[OneBot] 群文件发送成功 ({label}): {params['name']} (群 {group_id})"
            )

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
            logger.debug(
                f"[OneBot] 正在群 {group_id} 中创建群文件夹 '{folder_name}'..."
            )
            result = await self.bot.call_action(
                "create_group_file_folder",
                group_id=int(group_id),
                name=folder_name,
                parent_id="/",
            )
            # go-cqhttp, NapCat, LLOneBot 等实现可能返回顶层或嵌套在 data 里的 folder_id
            folder_id = None
            if isinstance(result, dict):
                data = result.get("data")
                if isinstance(data, dict):
                    folder_id = (
                        data.get("folder_id") or data.get("id") or data.get("folderId")
                    )
                elif isinstance(data, str) and data:
                    folder_id = data
                if not folder_id:
                    folder_id = (
                        result.get("folder_id")
                        or result.get("id")
                        or result.get("folderId")
                    )
            elif isinstance(result, str) and result:
                folder_id = result

            logger.info(
                f"[OneBot] 群文件夹创建成功: '{folder_name}' (群 {group_id})"
                + (f" [ID: {folder_id}]" if folder_id else "")
            )
            return str(folder_id) if folder_id is not None else None
        except Exception as e:
            error_msg = str(e).lower()
            # 文件夹已存在的情况不视为错误
            if "exist" in error_msg or "已存在" in error_msg:
                logger.info(f"[OneBot] 群文件夹已存在: '{folder_name}' (群 {group_id})")
                return None  # 需要通过 get_group_file_root_folders 获取 ID
            logger.error(f"[OneBot] 群文件夹创建失败: {e}")
            return None

    async def get_group_file_root_folders(
        self,
        group_id: str,
    ) -> list[dict]:
        """
        获取群文件根目录下的文件夹列表。

        兼容顶层 folders、data.folders 及直接返回列表等多种 OneBot 实现规范。

        Args:
            group_id: 目标群号

        Returns:
            list[dict]: 文件夹列表，每项包含 folder_id/name 等字段。
                        API 不可用时返回空列表。
        """
        try:
            logger.debug(f"[OneBot] 正在获取群 {group_id} 的根目录文件夹列表...")
            result = await self.bot.call_action(
                "get_group_root_files",
                group_id=int(group_id),
            )
            folders: list[dict] = []
            if isinstance(result, list):
                folders = [f for f in result if isinstance(f, dict)]
            elif isinstance(result, dict):
                data = result.get("data")
                if isinstance(data, list):
                    folders = [f for f in data if isinstance(f, dict)]
                elif isinstance(data, dict):
                    raw_folders = (
                        data.get("folders")
                        or data.get("folder_list")
                        or data.get("folderList")
                        or data.get("list")
                    )
                    if isinstance(raw_folders, list):
                        folders = [f for f in raw_folders if isinstance(f, dict)]
                if not folders:
                    raw_folders = (
                        result.get("folders")
                        or result.get("folder_list")
                        or result.get("folderList")
                        or result.get("list")
                    )
                    if isinstance(raw_folders, list):
                        folders = [f for f in raw_folders if isinstance(f, dict)]

            logger.debug(
                f"[OneBot] 获取群文件夹列表成功 (群 {group_id}): 提取到 {len(folders)} 个文件夹, 原始响应={result}"
            )
            return folders
        except Exception as e:
            logger.debug(f"[OneBot] 获取群文件夹列表失败 (群 {group_id}): {e}")
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
            str | None: 匹配或新创建的 folder_id，若均失败返回 None
        """
        if not folder_name:
            return None

        target_name = str(folder_name).strip()
        logger.debug(
            f"[OneBot] 正在群 {group_id} 中查找或创建文件夹: '{target_name}'..."
        )

        # 1. 先尝试查找已有文件夹
        folders = await self.get_group_file_root_folders(group_id)
        for folder in folders:
            name = (
                folder.get("folder_name")
                or folder.get("name")
                or folder.get("folderName")
                or ""
            )
            fid = (
                folder.get("folder_id")
                or folder.get("id")
                or folder.get("folderId")
                or ""
            )
            if str(name).strip() == target_name and fid:
                logger.debug(
                    f"[OneBot] 匹配到已有群文件夹: '{target_name}' [ID: {fid}] (群 {group_id})"
                )
                return str(fid)

        # 2. 未找到，尝试创建
        created_id = await self.create_group_file_folder(group_id, target_name)
        if created_id:
            logger.info(
                f"[OneBot] 成功创建并获取到群文件夹 ID: '{target_name}' [ID: {created_id}] (群 {group_id})"
            )
            return str(created_id)

        # 3. 创建后再次查找（某些实现创建时不返回 ID）
        folders = await self.get_group_file_root_folders(group_id)
        for folder in folders:
            name = (
                folder.get("folder_name")
                or folder.get("name")
                or folder.get("folderName")
                or ""
            )
            fid = (
                folder.get("folder_id")
                or folder.get("id")
                or folder.get("folderId")
                or ""
            )
            if str(name).strip() == target_name and fid:
                logger.debug(
                    f"[OneBot] 创建后二次查询匹配到群文件夹: '{target_name}' [ID: {fid}] (群 {group_id})"
                )
                return str(fid)

        logger.warning(
            f"[OneBot] 无法获取群文件夹 ID: '{target_name}' (群 {group_id})，将上传到根目录"
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
        """上传图片到群相册（OneBot 扩展 API）。"""
        # 如果未显式传入 album_id 但指定了 album_name，先尝试定位相册 ID
        if not album_id and album_name:
            album_id = await self.find_album_id(group_id, album_name)

        # 严格模式：指定了相册名但未解析到 album_id 时，禁止上传
        if strict_mode and album_name and not album_id:
            logger.info(
                f"[群分析相册] 严格模式开启：未找到相册 '{album_name}' (群 {group_id})，停止上传。"
            )
            return False

        # 非严格模式下的兜底查询
        if not album_id:
            albums = await self.get_group_album_list(group_id)
            if albums:
                first = albums[0]
                album_id = (
                    first.get("album_id") or first.get("id") or first.get("albumId")
                )
                if album_name:
                    logger.info(
                        f"[群分析相册] 未找到相册 '{album_name}'，回退到默认相册 (群 {group_id})"
                    )

        if not album_id:
            logger.info(
                f"[群分析相册] 未能确定目标相册 (群 {group_id})，跳过相册上传。"
            )
            return False

        async def do_upload(content: str, label: str):
            driver = await self._ensure_driver()
            await driver.upload_group_album(
                bot=self.bot,
                group_id=group_id,
                album_id=str(album_id),
                album_name=album_name,
                file_content=content,
            )

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
        driver = await self._ensure_driver()
        return await driver.get_group_album_list(self.bot, group_id)

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

        target_name = str(album_name).strip()
        logger.debug(
            f"[群分析相册] 正在群 {group_id} 中查找名为 '{target_name}' 的相册..."
        )
        albums = await self.get_group_album_list(group_id)
        for album in albums:
            name = (
                album.get("name")
                or album.get("album_name")
                or album.get("albumName")
                or album.get("title")
            )
            aid = album.get("album_id") or album.get("id") or album.get("albumId")
            logger.debug(
                f"[群分析相册] 正在匹配相册: 目标='{target_name}', 当前相册名称='{name}', 原始数据={album}"
            )
            if name and str(name).strip() == target_name:
                if aid is not None:
                    logger.info(
                        f"[群分析相册] 成功定位相册: '{target_name}' -> ID: {aid}"
                    )
                    return str(aid)
                logger.debug(
                    f"[群分析相册] 相册 '{name}' 名称匹配，但未找到有效的 album_id"
                )

        logger.info(f"[群分析相册] 未能找到名为 '{target_name}' 的相册 (群 {group_id})")
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

            logger.debug(
                f"[OneBot] 正在设置表情回应: 群={group_id}, 消息ID={message_id}, emoji={emoji} (解析ID={emoji_id}, is_add={is_add})"
            )
            await self.bot.call_action(
                "set_msg_emoji_like",
                message_id=int(message_id),
                emoji_id=emoji_id,
                emoji_type="1",  # 还原为最稳定的系统表情类型
                set=is_add,
            )
            self._record_mute_status(group_id, False)
            logger.debug(
                f"[OneBot] 表情回应设置成功: 群={group_id}, 消息ID={message_id}, emoji_id={emoji_id}"
            )
            return True
        except Exception as e:
            if self._is_mute_exception(e):
                self._record_mute_status(group_id, True)
            logger.debug(
                f"[OneBot] set_reaction 失败 (群 {group_id}, 消息 {message_id}, API 可能不支持): {e}"
            )
            return False

    def _get_use_base64(self) -> bool:
        """从插件配置中获取是否启用 Base64"""
        plugin: Any = self.config.get("plugin_instance") if self.config else None
        if plugin and hasattr(plugin, "config_manager"):
            return plugin.config_manager.get_enable_base64_image()
        return False

    def _get_napcat_stream_threshold_bytes(self) -> int:
        """获取配置的 NapCat 流式上传兜底阈值（字节）。"""
        plugin: Any = self.config.get("plugin_instance") if self.config else None
        if not plugin or not hasattr(plugin, "config_manager"):
            return 0
        try:
            threshold_mb = plugin.config_manager.get_napcat_stream_threshold_mb()
            return max(0, int(float(threshold_mb) * 1024 * 1024))
        except (TypeError, ValueError):
            return 0

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
