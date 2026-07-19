import re
from collections import Counter, OrderedDict

from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context

from ...infrastructure.persistence.platform_group_registry import PlatformGroupRegistry
from ...utils.logger import logger


class MessageProcessingService:
    """
    消息处理服务

    解析收到的群消息事件，提取内容与发送者信息，持久化历史记录，
    并维护事件驱动平台（Telegram、QQ 官方等）的群组注册表。
    QQ 官方平台特有的重复消息去重逻辑也在本服务中处理。

    职责：
    1. 解析消息内容（文本、图片、@提及等）
    2. 解析发送者展示名（跨平台兼容）
    3. 存储消息历史
    4. 维护群组注册表，供调度器做群组发现（Telegram、QQ 官方等事件驱动平台）
    5. QQ 官方事件消息去重（按 message_id 预占 + 确认机制）
    """

    def __init__(self, context: Context, group_registry: PlatformGroupRegistry):
        self.context = context
        self.group_registry = group_registry
        self._seen_event_ids: OrderedDict[str, None] = OrderedDict()
        self._inflight_event_ids: set[str] = set()
        self._seen_event_ids_limit = 4096

    async def process_message(self, event: AstrMessageEvent) -> None:
        """
        处理并在历史记录中存储消息。
         被 main.py 的 Telegram 和 QQ 官方消息拦截器共同调用。

         Args:
             event: AstrBot 消息事件

         Raises:
             ValueError: 当必要数据无法获取时
             RuntimeError: 当消息内容为空时
        """
        # 1. 获取群组 ID（必需）
        group_id = self._get_group_id_from_event(event)
        if not group_id:
            raise ValueError("无法获取群组 ID，拒绝存储消息")

        # 2. 获取发送者 ID（必需）
        sender_id = event.get_sender_id()
        if not sender_id:
            raise ValueError(f"群 {group_id}: 无法获取发送者 ID，拒绝存储消息")
        sender_id = str(sender_id)

        # 3. 获取发送者名称（昵称优先，必要时回退）
        sender_name = self._resolve_sender_name(event, sender_id)

        # 4. 获取平台 ID（必需）
        platform_id = event.get_platform_id()
        if not platform_id:
            raise ValueError(f"群 {group_id}: 无法获取平台 ID，拒绝存储消息")

        # 5. 提取消息内容
        message_parts = self._extract_message_parts(event)
        if not message_parts:
            # 尝试记录一条警告但不中断流程（或者视为错误）
            # 原逻辑是抛出 RuntimeError
            raise RuntimeError(
                f"群 {group_id}: 消息内容为空 (sender={sender_name})，拒绝存储"
            )

        # 6. 提取事件消息 ID 和事件时间
        msg_obj = getattr(event, "message_obj", None)
        event_message_id = str(getattr(msg_obj, "message_id", "") or "")
        event_timestamp = self._extract_event_timestamp(msg_obj)

        platform_name = str(event.get_platform_name() or "").strip().lower()
        reserved_event_id = False
        if platform_name in {"qq_official", "qq_official_webhook"} and event_message_id:
            reserved_event_id = self._reserve_event_id(event_message_id)
            if not reserved_event_id:
                logger.debug("[QQOfficial] 跳过重复消息事件: %s", event_message_id)
                return
        history_content = {
            "type": "user",
            "message": message_parts,
        }
        if platform_name in {"qq_official", "qq_official_webhook"}:
            history_content["_qq_official"] = {
                "message_id": event_message_id,
                "timestamp": event_timestamp,
            }

        # 7. 存储到数据库
        try:
            await self.context.message_history_manager.insert(
                platform_id=platform_id,
                user_id=group_id,
                content=history_content,
                sender_id=sender_id,
                sender_name=sender_name,
            )
        except BaseException:
            if reserved_event_id:
                self._release_event_id(event_message_id)
            raise
        else:
            if reserved_event_id:
                self._commit_event_id(event_message_id)

        # Register the group so the scheduler can discover platforms that
        # do not provide a group-list API (Telegram, QQ Official, etc.).
        try:
            await self.group_registry.upsert(
                platform_id=platform_id,
                group_id=group_id,
                sender_id=sender_id,
                sender_name=sender_name,
                event_message_id=event_message_id,
            )
        except Exception as e:
            logger.warning(
                "[GroupRegistry] Upsert failed: "
                f"platform_id={platform_id} group_id={group_id} error={e}"
            )

        logger.info(
            f"[{platform_id}] 已缓存群 {group_id} 的消息 (发送者: {sender_name})"
        )

    def _get_group_id_from_event(self, event: AstrMessageEvent) -> str | None:
        """从消息事件中安全获取群组 ID"""
        try:
            group_id = event.get_group_id()
            return group_id if group_id else None
        except Exception:
            return None

    def _resolve_sender_name(self, event: AstrMessageEvent, sender_id: str) -> str:
        """解析发送者展示名"""
        platform_name = str(event.get_platform_name() or "").lower()
        candidates: list[str | None] = []

        msg_obj = getattr(event, "message_obj", None)
        sender_obj = getattr(msg_obj, "sender", None)
        raw_message = getattr(msg_obj, "raw_message", None)
        raw_msg_obj = getattr(raw_message, "message", raw_message)
        from_user = getattr(raw_msg_obj, "from_user", None)

        if platform_name == "telegram":
            if from_user is not None:
                candidates.extend(
                    [
                        getattr(from_user, "full_name", None),
                        getattr(from_user, "first_name", None),
                    ]
                )
            candidates.append(event.get_sender_name())
            if sender_obj is not None:
                candidates.append(getattr(sender_obj, "nickname", None))
            if from_user is not None:
                candidates.append(getattr(from_user, "username", None))
        else:
            candidates.append(event.get_sender_name())
            if sender_obj is not None:
                candidates.append(getattr(sender_obj, "nickname", None))

        if from_user is not None:
            candidates.extend(
                [
                    getattr(from_user, "full_name", None),
                    getattr(from_user, "first_name", None),
                    getattr(from_user, "username", None),
                ]
            )

        for candidate in candidates:
            name = str(candidate or "").strip()
            if not self._is_placeholder_sender_name(name, sender_id):
                return name

        return sender_id

    def _extract_message_parts(self, event: AstrMessageEvent) -> list[dict]:
        """从事件中提取消息内容"""
        message_parts = []
        message = event.message_obj

        # 收集 @ 标记
        pending_mentions: Counter[str] = Counter()
        if message and hasattr(message, "message"):
            for seg in message.message:
                if not hasattr(seg, "type"):
                    continue
                if seg.type not in ("At", "at"):
                    continue

                target = getattr(seg, "target", None) or getattr(seg, "qq", None)
                if target is None and hasattr(seg, "data"):
                    target = seg.data.get("qq") or seg.data.get("target")

                target_str = str(target or "").strip()
                if target_str:
                    pending_mentions[target_str] += 1

                display_name = str(getattr(seg, "name", "") or "").strip()
                if display_name and display_name != target_str:
                    pending_mentions[display_name] += 1

        if message and hasattr(message, "message"):
            for seg in message.message:
                if not hasattr(seg, "type"):
                    continue

                seg_type = seg.type
                if seg_type in ("Plain", "text"):
                    text = getattr(seg, "text", None)
                    if text is None and hasattr(seg, "data"):
                        text = seg.data.get("text")
                    if text:
                        text = self._strip_known_mentions(text, pending_mentions)
                        message_parts.append({"type": "plain", "text": text})

                elif seg_type in ("Image", "image"):
                    url = getattr(seg, "url", None) or (
                        seg.data.get("url") if hasattr(seg, "data") else None
                    )
                    if url:
                        message_parts.append({"type": "image", "url": url})

                elif seg_type in ("At", "at"):
                    target = getattr(seg, "target", None) or getattr(seg, "qq", None)
                    if target is None and hasattr(seg, "data"):
                        target = seg.data.get("qq") or seg.data.get("target")
                    if target:
                        message_parts.append(
                            {
                                "type": "at",
                                "target_id": str(target),
                                "name": str(getattr(seg, "name", "") or ""),
                            }
                        )

                elif seg_type in ("File", "file"):
                    url = getattr(seg, "url", None) or getattr(seg, "file_", None)
                    message_parts.append(
                        {
                            "type": "file",
                            "url": str(url or ""),
                            "name": str(getattr(seg, "name", "") or ""),
                        }
                    )

                elif seg_type in ("Record", "record", "voice"):
                    url = getattr(seg, "url", None) or getattr(seg, "file", None)
                    message_parts.append({"type": "voice", "url": str(url or "")})

                elif seg_type in ("Video", "video"):
                    url = getattr(seg, "url", None) or getattr(seg, "file", None)
                    message_parts.append({"type": "video", "url": str(url or "")})

        if not message_parts and event.message_str:
            message_parts.append({"type": "plain", "text": event.message_str})

        # 清理空文本段
        message_parts = [
            part
            for part in message_parts
            if not (
                part.get("type") == "plain" and not str(part.get("text", "")).strip()
            )
        ]

        return message_parts

    @staticmethod
    def _strip_known_mentions(text: str, pending_mentions: Counter[str]) -> str:
        """从文本中移除已识别的 @ 提及"""
        cleaned = str(text)
        if not cleaned or not pending_mentions:
            return cleaned.strip()

        for mention, remaining in list(pending_mentions.items()):
            if not mention or remaining <= 0:
                continue

            pattern = re.compile(rf"(?<!\w)@{re.escape(mention)}(?!\w)")
            removed = 0
            while removed < remaining:
                cleaned, subn = pattern.subn("", cleaned, count=1)
                if subn == 0:
                    break
                removed += 1

            if removed > 0:
                pending_mentions[mention] -= removed
                if pending_mentions[mention] <= 0:
                    pending_mentions.pop(mention, None)

        return re.sub(r"\s{2,}", " ", cleaned).strip()

    @staticmethod
    def _is_placeholder_sender_name(name: str | None, sender_id: str) -> bool:
        """判断 sender_name 是否为占位值"""
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized.lower() in {"unknown", "none", "null", "nil", "undefined"}:
            return True
        return normalized == str(sender_id).strip()

    @staticmethod
    def _extract_event_timestamp(message_obj: object) -> int:
        """从消息对象中提取平台事件时间戳。"""
        raw_message = getattr(message_obj, "raw_message", None)
        if isinstance(raw_message, dict):
            candidate = raw_message.get("timestamp")
            if not candidate:
                raw_data = raw_message.get("raw_data")
                if isinstance(raw_data, dict):
                    candidate = raw_data.get("timestamp")
        else:
            raw_data = getattr(raw_message, "raw_data", None)
            candidate = getattr(raw_message, "timestamp", None)
            if not candidate and isinstance(raw_data, dict):
                candidate = raw_data.get("timestamp")
        if isinstance(candidate, (int, float)):
            return int(candidate)
        if candidate:
            try:
                from datetime import datetime

                return int(
                    datetime.fromisoformat(
                        str(candidate).replace("Z", "+00:00")
                    ).timestamp()
                )
            except (TypeError, ValueError, OverflowError):
                pass
        return 0

    def _reserve_event_id(self, event_message_id: str) -> bool:
        """预占事件消息 ID：在历史记录持久化期间防止重复入库。"""
        if (
            event_message_id in self._inflight_event_ids
            or event_message_id in self._seen_event_ids
        ):
            if event_message_id in self._seen_event_ids:
                self._seen_event_ids.move_to_end(event_message_id)
            return False
        self._inflight_event_ids.add(event_message_id)
        return True

    def _commit_event_id(self, event_message_id: str) -> None:
        """确认事件消息 ID：标记为已持久化，纳入后续去重。"""
        self._inflight_event_ids.discard(event_message_id)
        if event_message_id in self._seen_event_ids:
            self._seen_event_ids.move_to_end(event_message_id)
        else:
            self._seen_event_ids[event_message_id] = None
        if len(self._seen_event_ids) > self._seen_event_ids_limit:
            self._seen_event_ids.popitem(last=False)

    def _release_event_id(self, event_message_id: str) -> None:
        """释放事件消息 ID：持久化失败或取消时清理预占状态。"""
        self._inflight_event_ids.discard(event_message_id)
