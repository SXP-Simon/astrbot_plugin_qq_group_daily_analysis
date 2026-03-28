"""
Feishu/Lark 平台适配器

复用 AstrBot 已有 lark_oapi 生态能力，实现飞书群分析消息读取、成员信息与头像获取。
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Generator, Iterator, Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol, TypeAlias, cast

import aiohttp
from aiohttp import ClientTimeout

from ....domain.value_objects.platform_capabilities import (
    LARK_CAPABILITIES,
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


class _SDKNode(Protocol):
    def __getattr__(self, name: str) -> _SDKNode: ...

    def __call__(self, *args: object, **kwargs: object) -> _SDKNode: ...

    def __await__(self) -> Generator[object, None, _SDKNode]: ...

    def __iter__(self) -> Iterator[_SDKNode]: ...

    def __bool__(self) -> bool: ...

    def __int__(self) -> int: ...


class _BuilderRequest(Protocol):
    @classmethod
    def builder(cls) -> object: ...


CreateFileRequest: type[_BuilderRequest] | None = None
CreateFileRequestBody: type[_BuilderRequest] | None = None
CreateImageRequest: type[_BuilderRequest] | None = None
CreateImageRequestBody: type[_BuilderRequest] | None = None
CreateMessageRequest: type[_BuilderRequest] | None = None
CreateMessageRequestBody: type[_BuilderRequest] | None = None
GetChatMembersRequest: type[_BuilderRequest] | None = None
GetChatRequest: type[_BuilderRequest] | None = None
GetUserRequest: type[_BuilderRequest] | None = None
ListMessageRequest: type[_BuilderRequest] | None = None
ReplyMessageRequest: type[_BuilderRequest] | None = None
ReplyMessageRequestBody: type[_BuilderRequest] | None = None

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | dict[str, "JSONValue"] | list["JSONValue"]

try:
    from lark_oapi.api.contact.v3 import GetUserRequest as _GetUserRequest
    from lark_oapi.api.im.v1 import (
        CreateFileRequest as _CreateFileRequest,
    )
    from lark_oapi.api.im.v1 import (
        CreateFileRequestBody as _CreateFileRequestBody,
    )
    from lark_oapi.api.im.v1 import (
        CreateImageRequest as _CreateImageRequest,
    )
    from lark_oapi.api.im.v1 import (
        CreateImageRequestBody as _CreateImageRequestBody,
    )
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest as _CreateMessageRequest,
    )
    from lark_oapi.api.im.v1 import (
        CreateMessageRequestBody as _CreateMessageRequestBody,
    )
    from lark_oapi.api.im.v1 import (
        GetChatMembersRequest as _GetChatMembersRequest,
    )
    from lark_oapi.api.im.v1 import (
        GetChatRequest as _GetChatRequest,
    )
    from lark_oapi.api.im.v1 import (
        ListMessageRequest as _ListMessageRequest,
    )
    from lark_oapi.api.im.v1 import (
        ReplyMessageRequest as _ReplyMessageRequest,
    )
    from lark_oapi.api.im.v1 import (
        ReplyMessageRequestBody as _ReplyMessageRequestBody,
    )

    CreateFileRequest = _CreateFileRequest
    CreateFileRequestBody = _CreateFileRequestBody
    CreateImageRequest = _CreateImageRequest
    CreateImageRequestBody = _CreateImageRequestBody
    CreateMessageRequest = _CreateMessageRequest
    CreateMessageRequestBody = _CreateMessageRequestBody
    GetChatMembersRequest = _GetChatMembersRequest
    GetChatRequest = _GetChatRequest
    GetUserRequest = _GetUserRequest
    ListMessageRequest = _ListMessageRequest
    ReplyMessageRequest = _ReplyMessageRequest
    ReplyMessageRequestBody = _ReplyMessageRequestBody

    LARK_AVAILABLE = True
except Exception:  # pragma: no cover - 兼容缺依赖环境
    LARK_AVAILABLE = False


class LarkAdapter(PlatformAdapter):
    """飞书平台适配器。"""

    platform_name = "lark"
    _DEFAULT_SCOPE_HINT = (
        "Please grant these Feishu app scopes once: "
        "`im:message:readonly`, `im:chat:readonly`, and user/contact read scopes "
        "for profile avatar fields, then reinstall/re-authorize the app."
    )

    def __init__(
        self,
        bot_instance: object,
        config: Mapping[str, object] | None = None,
    ):
        normalized_config = dict(config) if config is not None else None
        super().__init__(bot_instance, normalized_config)
        self._lark_client: _SDKNode | None = self._resolve_lark_client(bot_instance)
        self._avatar_url_cache: dict[str, str] = {}
        self._member_name_cache: dict[tuple[str, str], str] = {}
        self._member_avatar_cache: dict[tuple[str, str], str] = {}
        self._permission_checked_groups: set[str] = set()
        self._permission_error: str | None = None

    @staticmethod
    def _request_class_or_throw(
        request_cls: type[_BuilderRequest] | None, name: str
    ) -> type[_BuilderRequest]:
        if request_cls is None:
            raise RuntimeError(f"{name} unavailable; install lark_oapi")
        return request_cls

    @staticmethod
    def _builder(request_cls: type[_BuilderRequest]) -> _SDKNode:
        return cast(_SDKNode, request_cls.builder())

    def _init_capabilities(self) -> PlatformCapabilities:
        return LARK_CAPABILITIES

    @staticmethod
    def _resolve_lark_client(bot_instance: object) -> _SDKNode | None:
        if bot_instance is None:
            return None
        # 直接是 lark.Client
        if hasattr(bot_instance, "im") and hasattr(bot_instance, "contact"):
            return cast(_SDKNode, bot_instance)
        # 平台实例上暴露 lark_api
        if hasattr(bot_instance, "lark_api"):
            api = getattr(bot_instance, "lark_api")
            if hasattr(api, "im"):
                return cast(_SDKNode, api)
        # 常见包装层
        for attr in ("client", "_client", "bot"):
            if hasattr(bot_instance, attr):
                client = getattr(bot_instance, attr)
                if hasattr(client, "im"):
                    return cast(_SDKNode, client)
        return None

    @staticmethod
    def _to_seconds(ts: int | None) -> int:
        if not ts:
            return 0
        try:
            ts_int = int(ts)
        except (TypeError, ValueError):
            return 0
        return ts_int // 1000 if ts_int > 10**11 else ts_int

    @staticmethod
    def _safe_json_loads(raw: str | None) -> dict[str, JSONValue]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _is_permission_error(code: int, msg: str) -> bool:
        msg_l = (msg or "").lower()
        return code in {99991663, 99991664, 230001, 20013} or (
            "permission" in msg_l
            or "scope" in msg_l
            or "forbidden" in msg_l
            or "无权限" in msg_l
        )

    @staticmethod
    def _pick_avatar_from_user(user_obj: object, size: int) -> str | None:
        avatar = getattr(user_obj, "avatar", None)
        if avatar is None:
            return None
        if size <= 72 and getattr(avatar, "avatar_72", None):
            return avatar.avatar_72
        if size <= 240 and getattr(avatar, "avatar_240", None):
            return avatar.avatar_240
        if size <= 640 and getattr(avatar, "avatar_640", None):
            return avatar.avatar_640
        return getattr(avatar, "avatar_origin", None) or getattr(
            avatar, "avatar_640", None
        )

    async def prepare_group_member_cache(
        self, group_id: str
    ) -> tuple[bool, str | None]:
        """
        预热群成员缓存并完成权限探测。
        该方法用于在分析前一次性确认“成员信息+头像”权限是否齐备。
        """
        if group_id in self._permission_checked_groups:
            return self._permission_error is None, self._permission_error
        if not LARK_AVAILABLE or not self._lark_client or not self._lark_client.im:
            self._permission_error = "Lark SDK client is not initialized."
            self._permission_checked_groups.add(group_id)
            return False, self._permission_error

        try:
            members = await self.get_member_list(group_id)
            if not members:
                self._permission_error = (
                    f"Cannot list chat members. {self._DEFAULT_SCOPE_HINT}"
                )
                self._permission_checked_groups.add(group_id)
                return False, self._permission_error

            # 只预热近期活跃用户常见数量，避免在超大群上引入不必要延迟
            target_ids = [m.user_id for m in members[:100]]
            avatar_map = await self.batch_get_avatar_urls(target_ids, size=240)
            if target_ids and all(not avatar_map.get(uid) for uid in target_ids):
                self._permission_error = (
                    "Fetched members but cannot read avatar URLs. "
                    f"{self._DEFAULT_SCOPE_HINT}"
                )
                self._permission_checked_groups.add(group_id)
                return False, self._permission_error

            self._permission_error = None
            self._permission_checked_groups.add(group_id)
            return True, None
        except Exception as e:
            self._permission_error = (
                f"Failed to warm up Lark member cache: {e}. {self._DEFAULT_SCOPE_HINT}"
            )
            self._permission_checked_groups.add(group_id)
            return False, self._permission_error

    async def fetch_messages(
        self,
        group_id: str,
        days: int = 1,
        max_count: int = 1000,
        before_id: str | None = None,
        since_ts: int | None = None,
    ) -> list[UnifiedMessage]:
        if not LARK_AVAILABLE or not self._lark_client or not self._lark_client.im:
            return []
        now_seconds = int(__import__("time").time())
        start_seconds = (
            int(since_ts) if since_ts and since_ts > 0 else now_seconds - (days * 86400)
        )

        messages: list[UnifiedMessage] = []
        page_token: str | None = None
        page_size = min(max(max_count, 1), 200)
        seen_ids: set[str] = set()

        while len(messages) < max_count:
            ListMessageRequestClass = self._request_class_or_throw(
                ListMessageRequest, "ListMessageRequest"
            )
            request = (
                self._builder(ListMessageRequestClass)
                .container_id_type("chat")
                .container_id(group_id)
                .start_time(str(start_seconds * 1000))
                .end_time(str(now_seconds * 1000))
                .page_size(min(page_size, max_count - len(messages)))
                .build()
            )
            if page_token:
                request = (
                    self._builder(ListMessageRequestClass)
                    .container_id_type("chat")
                    .container_id(group_id)
                    .start_time(str(start_seconds * 1000))
                    .end_time(str(now_seconds * 1000))
                    .page_size(min(page_size, max_count - len(messages)))
                    .page_token(page_token)
                    .build()
                )

            response = await self._lark_client.im.v1.message.alist(request)
            if not response.success():
                logger.warning(
                    "Lark fetch_messages failed: code=%s, msg=%s",
                    response.code,
                    response.msg,
                )
                break

            items = (response.data.items if response.data else None) or []
            if not items:
                break

            for item in items:
                msg = self._convert_message(item, group_id)
                if not msg or not msg.message_id or msg.message_id in seen_ids:
                    continue
                if before_id and msg.message_id >= before_id:
                    continue
                seen_ids.add(msg.message_id)
                messages.append(msg)
                if len(messages) >= max_count:
                    break

            has_more = bool(response.data and response.data.has_more)
            page_token_raw = (
                getattr(response.data, "page_token", None) if response.data else None
            )
            page_token = str(page_token_raw) if page_token_raw else None
            if not has_more or not page_token:
                break

        messages.sort(key=lambda m: m.timestamp)
        return messages

    def _convert_message(self, item: object, group_id: str) -> UnifiedMessage | None:
        try:
            message_id = str(getattr(item, "message_id", "") or "")
            sender = getattr(item, "sender", None)
            sender_id = str(getattr(sender, "id", "") or "")
            sender_name = (
                self._member_name_cache.get((group_id, sender_id))
                or sender_id[:8]
                or "Unknown"
            )
            body = getattr(item, "body", None)
            raw_content = str(getattr(body, "content", "") or "")
            msg_type = str(getattr(item, "msg_type", "") or "text")
            content = self._safe_json_loads(raw_content)

            contents: list[MessageContent] = []
            text_parts: list[str] = []

            if msg_type == "text":
                text = str(content.get("text", "")).strip()
                if text:
                    text_parts.append(text)
                    contents.append(
                        MessageContent(type=MessageContentType.TEXT, text=text)
                    )
            elif msg_type in {"post", "image"}:
                post_content = content.get("content", [])
                if isinstance(post_content, dict):
                    # 富文本消息常见结构：{"zh_cn":{"title":"","content":[...]}}
                    zh_cn = post_content.get("zh_cn", {})
                    if isinstance(zh_cn, dict):
                        post_content = zh_cn.get("content", [])
                if isinstance(post_content, list):
                    for row in post_content:
                        if not isinstance(row, list):
                            continue
                        for seg in row:
                            if not isinstance(seg, dict):
                                continue
                            tag = seg.get("tag", "")
                            if tag == "text":
                                text = str(seg.get("text", "")).strip()
                                if text:
                                    text_parts.append(text)
                                    contents.append(
                                        MessageContent(
                                            type=MessageContentType.TEXT, text=text
                                        )
                                    )
                            elif tag == "at":
                                at_uid = str(seg.get("user_id", "")).strip()
                                contents.append(
                                    MessageContent(
                                        type=MessageContentType.AT, at_user_id=at_uid
                                    )
                                )
                            elif tag == "img":
                                image_key = str(seg.get("image_key", "")).strip()
                                if image_key:
                                    contents.append(
                                        MessageContent(
                                            type=MessageContentType.IMAGE,
                                            raw_data={"image_key": image_key},
                                        )
                                    )
            else:
                if raw_content:
                    contents.append(
                        MessageContent(
                            type=MessageContentType.UNKNOWN,
                            raw_data={"msg_type": msg_type, "content": raw_content},
                        )
                    )

            if not contents:
                contents.append(
                    MessageContent(
                        type=MessageContentType.TEXT,
                        text="".join(text_parts),
                    )
                )

            return UnifiedMessage(
                message_id=message_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_card=None,
                group_id=group_id,
                text_content=" ".join(text_parts).strip(),
                contents=tuple(contents),
                timestamp=self._to_seconds(getattr(item, "create_time", 0)),
                platform="lark",
                reply_to_id=(
                    str(parent_id)
                    if (parent_id := getattr(item, "parent_id", None))
                    else None
                ),
            )
        except Exception as e:
            logger.debug(f"Lark convert message error: {e}")
            return None

    def convert_to_raw_format(self, messages: list[UnifiedMessage]) -> list[dict]:
        result: list[dict] = []
        for msg in messages:
            chain: list[dict[str, object]] = []
            for content in msg.contents:
                if content.type == MessageContentType.TEXT:
                    chain.append({"type": "text", "data": {"text": content.text}})
                elif content.type == MessageContentType.AT:
                    chain.append({"type": "at", "data": {"qq": content.at_user_id}})
                elif content.type == MessageContentType.IMAGE:
                    chain.append(
                        {
                            "type": "image",
                            "data": {
                                "url": content.url or "",
                                "image_key": (
                                    content.raw_data.get("image_key", "")
                                    if isinstance(content.raw_data, dict)
                                    else ""
                                ),
                            },
                        }
                    )
            result.append(
                {
                    "message_id": msg.message_id,
                    "group_id": msg.group_id,
                    "time": msg.timestamp,
                    "sender": {"user_id": msg.sender_id, "nickname": msg.sender_name},
                    "message": chain,
                    "user_id": msg.sender_id,
                }
            )
        return result

    async def send_text(
        self, group_id: str, text: str, reply_to: str | None = None
    ) -> bool:
        if not self._lark_client or not self._lark_client.im:
            return False
        try:
            ReplyMessageRequestClass = self._request_class_or_throw(
                ReplyMessageRequest, "ReplyMessageRequest"
            )
            ReplyMessageRequestBodyClass = self._request_class_or_throw(
                ReplyMessageRequestBody, "ReplyMessageRequestBody"
            )
            CreateMessageRequestClass = self._request_class_or_throw(
                CreateMessageRequest, "CreateMessageRequest"
            )
            CreateMessageRequestBodyClass = self._request_class_or_throw(
                CreateMessageRequestBody, "CreateMessageRequestBody"
            )

            if reply_to:
                request = (
                    self._builder(ReplyMessageRequestClass)
                    .message_id(reply_to)
                    .request_body(
                        self._builder(ReplyMessageRequestBodyClass)
                        .content(json.dumps({"text": text}, ensure_ascii=False))
                        .msg_type("text")
                        .build()
                    )
                    .build()
                )
                response = await self._lark_client.im.v1.message.areply(request)
            else:
                request = (
                    self._builder(CreateMessageRequestClass)
                    .receive_id_type("chat_id")
                    .request_body(
                        self._builder(CreateMessageRequestBodyClass)
                        .receive_id(group_id)
                        .msg_type("text")
                        .content(json.dumps({"text": text}, ensure_ascii=False))
                        .build()
                    )
                    .build()
                )
                response = await self._lark_client.im.v1.message.acreate(request)
            return bool(response.success())
        except Exception as e:
            logger.error(f"Lark send text failed: {e}")
            return False

    async def send_image(
        self, group_id: str, image_path: str, caption: str = ""
    ) -> bool:
        if not self._lark_client or not self._lark_client.im:
            return False
        temp_path: Path | None = None
        try:
            local_path: Path | None = None
            if image_path.startswith("base64://"):
                data = base64.b64decode(image_path.removeprefix("base64://"))
                with NamedTemporaryFile(delete=False, suffix=".png") as f:
                    f.write(data)
                    temp_path = Path(f.name)
                local_path = temp_path
            elif image_path.startswith("data:"):
                parts = image_path.split(",", 1)
                if len(parts) == 2:
                    data = base64.b64decode(parts[1])
                    with NamedTemporaryFile(delete=False, suffix=".png") as f:
                        f.write(data)
                        temp_path = Path(f.name)
                    local_path = temp_path
            elif image_path.startswith(("http://", "https://")):
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        image_path, timeout=ClientTimeout(total=20)
                    ) as resp:
                        if resp.status != 200:
                            return False
                        data = await resp.read()
                        with NamedTemporaryFile(delete=False, suffix=".png") as f:
                            f.write(data)
                            temp_path = Path(f.name)
                        local_path = temp_path
            else:
                p = Path(image_path)
                if p.exists():
                    local_path = p

            if not local_path:
                return False

            CreateImageRequestClass = self._request_class_or_throw(
                CreateImageRequest, "CreateImageRequest"
            )
            CreateImageRequestBodyClass = self._request_class_or_throw(
                CreateImageRequestBody, "CreateImageRequestBody"
            )

            with local_path.open("rb") as img_file:
                image_req = (
                    self._builder(CreateImageRequestClass)
                    .request_body(
                        self._builder(CreateImageRequestBodyClass)
                        .image_type("message")
                        .image(img_file)
                        .build()
                    )
                    .build()
                )
                image_resp = await self._lark_client.im.v1.image.acreate(image_req)
                if not image_resp.success() or not image_resp.data:
                    return False
                image_key = image_resp.data.image_key

            CreateMessageRequestClass = self._request_class_or_throw(
                CreateMessageRequest, "CreateMessageRequest"
            )
            CreateMessageRequestBodyClass = self._request_class_or_throw(
                CreateMessageRequestBody, "CreateMessageRequestBody"
            )

            send_req = (
                self._builder(CreateMessageRequestClass)
                .receive_id_type("chat_id")
                .request_body(
                    self._builder(CreateMessageRequestBodyClass)
                    .receive_id(group_id)
                    .msg_type("image")
                    .content(json.dumps({"image_key": image_key}, ensure_ascii=False))
                    .build()
                )
                .build()
            )
            send_resp = await self._lark_client.im.v1.message.acreate(send_req)
            if caption:
                await self.send_text(group_id, caption)
            return bool(send_resp.success())
        except Exception as e:
            logger.error(f"Lark send image failed: {e}")
            return False
        finally:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    async def send_file(
        self, group_id: str, file_path: str, filename: str | None = None
    ) -> bool:
        if not self._lark_client or not self._lark_client.im:
            return False
        try:
            p = Path(file_path)
            if not p.exists():
                return False
            with p.open("rb") as file_obj:
                CreateFileRequestClass = self._request_class_or_throw(
                    CreateFileRequest, "CreateFileRequest"
                )
                CreateFileRequestBodyClass = self._request_class_or_throw(
                    CreateFileRequestBody, "CreateFileRequestBody"
                )

                file_req = (
                    self._builder(CreateFileRequestClass)
                    .request_body(
                        self._builder(CreateFileRequestBodyClass)
                        .file_type("stream")
                        .file_name(filename or p.name)
                        .file(file_obj)
                        .build()
                    )
                    .build()
                )
                file_resp = await self._lark_client.im.v1.file.acreate(file_req)
                if not file_resp.success() or not file_resp.data:
                    return False
                file_key = file_resp.data.file_key

            CreateMessageRequestClass = self._request_class_or_throw(
                CreateMessageRequest, "CreateMessageRequest"
            )
            CreateMessageRequestBodyClass = self._request_class_or_throw(
                CreateMessageRequestBody, "CreateMessageRequestBody"
            )

            msg_req = (
                self._builder(CreateMessageRequestClass)
                .receive_id_type("chat_id")
                .request_body(
                    self._builder(CreateMessageRequestBodyClass)
                    .receive_id(group_id)
                    .msg_type("file")
                    .content(json.dumps({"file_key": file_key}, ensure_ascii=False))
                    .build()
                )
                .build()
            )
            msg_resp = await self._lark_client.im.v1.message.acreate(msg_req)
            return bool(msg_resp.success())
        except Exception as e:
            logger.error(f"Lark send file failed: {e}")
            return False

    async def send_forward_msg(self, group_id: str, nodes: list[dict]) -> bool:
        if not nodes:
            return True
        chunks: list[str] = ["📊 群分析报告摘要"]
        for node in nodes:
            data = node.get("data", node)
            name = str(data.get("name", "AstrBot"))
            content = data.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for seg in content:
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        text_parts.append(str(seg.get("data", {}).get("text", "")))
                content = "".join(text_parts)
            chunks.append(f"[{name}] {content}")
        return await self.send_text(group_id, "\n".join(chunks))

    async def get_group_info(self, group_id: str) -> UnifiedGroup | None:
        if not self._lark_client or not self._lark_client.im:
            return None
        try:
            GetChatRequestClass = self._request_class_or_throw(
                GetChatRequest, "GetChatRequest"
            )
            request = self._builder(GetChatRequestClass).chat_id(group_id).build()
            response = await self._lark_client.im.v1.chat.aget(request)
            if not response.success() or not response.data:
                return None
            group_name_raw = getattr(response.data, "name", None)
            owner_id_raw = getattr(response.data, "owner_id", None)
            description_raw = getattr(response.data, "description", None)
            return UnifiedGroup(
                group_id=group_id,
                group_name=str(group_name_raw) if group_name_raw else group_id,
                member_count=int(getattr(response.data, "user_count", 0) or 0),
                owner_id=str(owner_id_raw) if owner_id_raw else None,
                description=str(description_raw) if description_raw else None,
                platform="lark",
            )
        except Exception as e:
            logger.debug(f"Lark get group info failed: {e}")
            return None

    async def get_group_list(self) -> list[str]:
        # 飞书服务端 API 不提供简单“机器人可见群列表”枚举能力
        return []

    async def get_member_list(self, group_id: str) -> list[UnifiedMember]:
        if not self._lark_client or not self._lark_client.im:
            return []
        members: list[UnifiedMember] = []
        page_token: str | None = None
        while True:
            GetChatMembersRequestClass = self._request_class_or_throw(
                GetChatMembersRequest, "GetChatMembersRequest"
            )
            builder = (
                self._builder(GetChatMembersRequestClass)
                .chat_id(group_id)
                .member_id_type("open_id")
                .page_size(200)
            )
            if page_token:
                builder = builder.page_token(page_token)
            request = builder.build()
            response = await self._lark_client.im.v1.chat_members.aget(request)
            if not response.success():
                if self._is_permission_error(
                    int(getattr(response, "code", 0) or 0),
                    str(getattr(response, "msg", "") or ""),
                ):
                    logger.warning(
                        "Lark get member list permission denied: code=%s, msg=%s",
                        response.code,
                        response.msg,
                    )
                break
            items = (response.data.items if response.data else None) or []
            if not items:
                break
            for item in items:
                uid = str(item.member_id or "")
                name = str(item.name or uid)
                self._member_name_cache[(group_id, uid)] = name
                members.append(
                    UnifiedMember(
                        user_id=uid,
                        nickname=name,
                        role="member",
                    )
                )
            if not (
                response.data and response.data.has_more and response.data.page_token
            ):
                break
            page_token_raw = getattr(response.data, "page_token", None)
            page_token = str(page_token_raw) if page_token_raw else None
        return members

    async def _get_user_profile(self, user_id: str) -> _SDKNode | None:
        if not self._lark_client or not self._lark_client.contact:
            return None
        try:
            GetUserRequestClass = self._request_class_or_throw(
                GetUserRequest, "GetUserRequest"
            )
            request = (
                self._builder(GetUserRequestClass)
                .user_id_type("open_id")
                .user_id(user_id)
                .build()
            )
            response = await self._lark_client.contact.v3.user.aget(request)
            if not response.success():
                if self._is_permission_error(
                    int(getattr(response, "code", 0) or 0),
                    str(getattr(response, "msg", "") or ""),
                ):
                    logger.warning(
                        "Lark get user profile permission denied: code=%s, msg=%s",
                        response.code,
                        response.msg,
                    )
                return None
            return response.data
        except Exception as e:
            logger.debug(f"Lark get user profile failed: {e}")
            return None

    async def get_member_info(
        self, group_id: str, user_id: str
    ) -> UnifiedMember | None:
        profile = await self._get_user_profile(user_id)
        if profile and profile.user:
            user = profile.user
            name = str(user.name or user.nickname or user_id)
            avatar = self._pick_avatar_from_user(user, 240)
            if avatar:
                self._member_avatar_cache[(group_id, user_id)] = avatar
                self._avatar_url_cache[user_id] = avatar
            self._member_name_cache[(group_id, user_id)] = name
            return UnifiedMember(
                user_id=str(user.open_id or user_id),
                nickname=name,
                card=str(user.nickname or "") or None,
                role="member",
                avatar_url=avatar,
            )

        cached_name = self._member_name_cache.get((group_id, user_id)) or user_id
        return UnifiedMember(
            user_id=user_id,
            nickname=cached_name,
            role="member",
            avatar_url=self._member_avatar_cache.get((group_id, user_id)),
        )

    async def get_user_avatar_url(self, user_id: str, size: int = 100) -> str | None:
        if user_id in self._avatar_url_cache:
            return self._avatar_url_cache[user_id]
        profile = await self._get_user_profile(user_id)
        if profile and profile.user:
            avatar_url = self._pick_avatar_from_user(profile.user, size)
            if avatar_url:
                self._avatar_url_cache[user_id] = avatar_url
                return avatar_url
        return None

    async def get_user_avatar_data(self, user_id: str, size: int = 100) -> str | None:
        avatar_url = await self.get_user_avatar_url(user_id, size)
        if not avatar_url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    avatar_url, timeout=ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        return None
                    body = await resp.read()
                    mime = resp.headers.get("Content-Type", "image/png")
                    return (
                        f"data:{mime};base64,{base64.b64encode(body).decode('utf-8')}"
                    )
        except Exception:
            return None

    async def get_group_avatar_url(self, group_id: str, size: int = 100) -> str | None:
        group = await self.get_group_info(group_id)
        if not group or not self._lark_client:
            return None
        try:
            GetChatRequestClass = self._request_class_or_throw(
                GetChatRequest, "GetChatRequest"
            )
            req = self._builder(GetChatRequestClass).chat_id(group_id).build()
            rsp = await self._lark_client.im.v1.chat.aget(req)
            if rsp.success() and rsp.data and rsp.data.avatar:
                return str(rsp.data.avatar)
        except Exception:
            pass
        return None

    async def batch_get_avatar_urls(
        self, user_ids: list[str], size: int = 100
    ) -> dict[str, str | None]:
        if not user_ids:
            return {}
        semaphore = asyncio.Semaphore(8)

        async def _fetch(uid: str) -> tuple[str, str | None]:
            async with semaphore:
                return uid, await self.get_user_avatar_url(uid, size)

        pairs = await asyncio.gather(*(_fetch(uid) for uid in user_ids))
        return dict(pairs)

    async def set_reaction(
        self, group_id: str, message_id: str, emoji: str | int, is_add: bool = True
    ) -> bool:
        # 当前插件分析流程不依赖飞书 reaction，这里返回 False 以保持兼容。
        return False
