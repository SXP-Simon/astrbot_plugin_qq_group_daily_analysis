"""业务记录管理：沿用仓储，提供导入、导出及受保护的内容修订。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from contextlib import AsyncExitStack
from datetime import date
from typing import TYPE_CHECKING, Literal, TypedDict, cast

from astrbot.api.star import StarTools
from diskcache import Cache

from ....application.services.task_guard import DuplicateGroupTaskError
from ....domain.entities.incremental_state import IncrementalBatch
from ....shared.constants import PLUGIN_NAME
from ....shared.type_guards import is_object_list, is_string_mapping
from ...persistence.history_manager import HistoryManager
from ..web_compat import WebApiResponse, error_response, json_response, request

if TYPE_CHECKING:
    from ....application.services.analysis_application_service import (
        AnalysisApplicationService,
    )
    from ...persistence.kv_contracts import (
        CacheAccess,
        KeyValueWriter,
        StoredPreference,
    )
    from ..active_task_manager import ActiveTaskManager

HISTORY_KEY = re.compile(
    r"analysis_(.+)_(\d{4}-\d{2}-\d{2})(?:_(\d{2}-\d{2})(?:_([a-f0-9]{32}))?)?$"
)


class RecordLocator(TypedDict):
    """业务记录的定位字段，不接受文件系统路径。"""

    kind: str
    key: str
    group_id: str
    platform_id: str
    batch_id: str
    date_str: str
    stage_name: str
    trace_id: str


def record_revision(data: object) -> str:
    """将 JSON 规范化后计算版本，拒绝非有限数及过大内容。"""
    payload = json.dumps(
        data, ensure_ascii=False, sort_keys=True, allow_nan=False
    ).encode()
    if len(payload) > 4 * 1024 * 1024:
        raise ValueError("业务记录不能超过 4 MiB")
    return hashlib.sha256(payload).hexdigest()


def parse_locator(raw: dict[str, object]) -> RecordLocator:
    """规范化查询和导入中的定位字段，防止跨记录覆盖。"""
    result: RecordLocator = {
        "kind": "",
        "key": "",
        "group_id": "",
        "platform_id": "",
        "batch_id": "",
        "date_str": "",
        "stage_name": "",
        "trace_id": "",
    }
    for key in result:
        value = raw.get(key, "")
        if (
            not isinstance(value, str)
            or len(value) > 512
            or any(ord(char) < 32 for char in value)
        ):
            raise ValueError("记录定位字段无效")
        result[key] = value
    if result["kind"] not in {"history", "batch", "checkpoint", "avatar"}:
        raise ValueError("未知业务记录类型")
    if result["kind"] == "history":
        match = HISTORY_KEY.fullmatch(result["key"])
        if not match:
            raise ValueError("历史记录键格式无效")
        result["group_id"], result["date_str"] = match[1], match[2]
        date.fromisoformat(match[2])
    elif result["kind"] == "batch" and not all(
        (result["group_id"], result["batch_id"])
    ):
        raise ValueError("请选择群组和批次")
    elif result["kind"] == "checkpoint":
        date.fromisoformat(result["date_str"])
        if not result["group_id"] or not result["stage_name"]:
            raise ValueError("快照定位字段不完整")
    elif result["kind"] == "avatar" and not result["key"]:
        raise ValueError("请选择头像条目")
    return result


def validate_batch(data: dict[str, object], locator: RecordLocator) -> IncrementalBatch:
    """在外部编辑边界校验批次结构，内部继续使用领域实体。

    Args:
        data: 待导入或修改的完整批次。
        locator: 不可更改的群组与批次身份。

    Returns:
        可以交给增量仓储保存的领域实体。

    Raises:
        ValueError: 字段类型、计数或身份不合法。
    """
    if (
        data.get("group_id") != locator["group_id"]
        or data.get("batch_id") != locator["batch_id"]
    ):
        raise ValueError("不能通过编辑改变群组或批次 ID")
    for key in (
        "timestamp",
        "messages_count",
        "characters_count",
        "last_message_timestamp",
    ):
        value = data.get(key, 0)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{key} 必须为非负有限数")
        if key != "timestamp" and not isinstance(value, int):
            raise ValueError(f"{key} 必须为整数")
    for key in ("hourly_msg_counts", "hourly_char_counts", "token_usage"):
        values = data.get(key, {})
        if not is_string_mapping(values) or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in values.values()
        ):
            raise ValueError(f"{key} 必须为非负整数映射")
    for key in ("user_stats", "emoji_stats"):
        if not isinstance(data.get(key, {}), dict):
            raise ValueError(f"{key} 必须为对象")
    users = data.get("user_stats", {})
    if is_string_mapping(users) and any(
        not is_string_mapping(value) for value in users.values()
    ):
        raise ValueError("用户统计值必须为对象")
    for key in ("topics", "golden_quotes"):
        values = data.get(key, [])
        if not is_object_list(values) or any(
            not is_string_mapping(value) for value in values
        ):
            raise ValueError(f"{key} 必须为对象列表")
    participants = data.get("participant_ids", [])
    if not is_object_list(participants) or any(
        not isinstance(value, str) for value in participants
    ):
        raise ValueError("参与者 ID 必须为字符串列表")
    if data.get("chat_quality_review") is not None and not isinstance(
        data["chat_quality_review"], dict
    ):
        raise ValueError("聊天质量产物必须为对象或空值")
    batch = IncrementalBatch.from_dict(data)
    if set(data) - set(batch.to_dict()):
        raise ValueError("批次包含未知字段，请核对导入格式")
    return batch


class ManagedRecordRoutes:
    """处理历史 KV、批次、快照与头像缓存条目。"""

    def __init__(
        self,
        service: AnalysisApplicationService | None,
        active_tasks: ActiveTaskManager,
    ) -> None:
        self.service = service
        self.active_tasks = active_tasks
        self._lock = asyncio.Lock()

    async def _history(self) -> dict[str, dict[str, object]]:
        """只枚举本插件的分析历史，不暴露宿主其他模块的 KV。"""
        from astrbot.core import sp

        if not self.service:
            return {}
        plugin = self.service.history_manager.plugin
        preferences = await sp.range_get_async("plugin", plugin.plugin_id)
        result: dict[str, dict[str, object]] = {}
        for item in preferences:
            raw_value = cast("StoredPreference", item).value
            value = raw_value.get("val") if is_string_mapping(raw_value) else None
            if HISTORY_KEY.fullmatch(item.key) and is_string_mapping(value):
                result[item.key] = value
        return result

    async def _read(self, locator: RecordLocator) -> object | None:
        """通过各模块仓储读取记录，快照使用精确身份防止旧记录回退。"""
        kind = locator["kind"]
        if kind == "avatar":
            directory = StarTools.get_data_dir(PLUGIN_NAME) / "avatar"
            if not directory.exists():
                return None
            with Cache(str(directory)) as cache:
                value = await asyncio.to_thread(
                    cast("CacheAccess", cache).get, locator["key"]
                )
                return {"data_uri": value} if isinstance(value, str) else None
        service = self.service
        if not service:
            raise ValueError("分析服务尚未初始化")
        if kind == "history":
            value = cast(
                "object",
                await service.history_manager.plugin.get_kv_data(locator["key"], None),
            )
            if is_string_mapping(value):
                if (
                    locator["platform_id"]
                    and value.get("platform_id") != locator["platform_id"]
                ):
                    raise ValueError("历史记录与所选平台不一致，请刷新后重试")
                return value
            return None
        if kind == "batch":
            if not service.incremental_store:
                raise ValueError("增量存储尚未初始化")
            store = await service.incremental_store.for_session(
                locator["group_id"], locator["platform_id"]
            )
            batch = await store.get_batch_detail(
                locator["group_id"], locator["batch_id"]
            )
            return batch.to_dict() if batch else None
        if not service.checkpoint_store:
            raise ValueError("快照存储尚未初始化")
        detail = await asyncio.to_thread(
            service.checkpoint_store.get_checkpoint_detail,
            locator["group_id"],
            locator["date_str"],
            locator["stage_name"],
            locator["trace_id"],
        )
        if not detail or any(
            detail.get(key) != locator[key]
            for key in ("group_id", "date_str", "stage_name", "trace_id")
        ):
            return None
        return {
            key: detail.get(key)
            for key in (
                "checkpoint_id",
                "group_id",
                "date_str",
                "stage_name",
                "trace_id",
                "created_at",
                "expire_at",
                "data",
            )
        }

    async def api_list(self) -> WebApiResponse:
        """分页搜索历史归档或头像键，列表不携带完整产物。"""
        try:
            kind = request.query.get("kind", "history")
            search = request.query.get("search", "").casefold()
            page = max(1, int(request.query.get("page", "1")))
            items: list[dict[str, object]] = []
            if kind == "history":
                for key, value in (await self._history()).items():
                    if search not in key.casefold():
                        continue
                    locator = parse_locator({"kind": kind, "key": key})
                    platform = value.get("platform_id")
                    if isinstance(platform, str):
                        locator["platform_id"] = platform
                    items.append(
                        {
                            "locator": locator,
                            "name": key,
                            "size_bytes": len(
                                json.dumps(value, ensure_ascii=False).encode()
                            ),
                        }
                    )
            elif kind == "avatar":
                directory = StarTools.get_data_dir(PLUGIN_NAME) / "avatar"
                if directory.exists():

                    def entries() -> list[dict[str, object]]:
                        """通过缓存 API 读取键，不触碰缓存数据库文件。"""
                        with Cache(str(directory)) as cache:
                            return [
                                {
                                    "locator": parse_locator(
                                        {"kind": kind, "key": key}
                                    ),
                                    "name": key,
                                    "size_bytes": 0,
                                }
                                for key in cache.iterkeys()
                                if isinstance(key, str) and search in key.casefold()
                            ]

                    items = await asyncio.to_thread(entries)
            else:
                raise ValueError("此处仅列出历史存档和头像；批次与快照请使用对应页签")
            items.sort(key=lambda item: str(item["name"]), reverse=True)
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "items": items[(page - 1) * 20 : page * 20],
                        "total": len(items),
                    },
                }
            )
        except ValueError as error:
            return error_response(str(error), status_code=400)
        except (OSError, RuntimeError):
            return error_response("业务记录读取失败，请检查存储后刷新", status_code=500)

    async def api_detail(self) -> WebApiResponse:
        """返回可导出的完整记录及版本号。"""
        try:
            locator = parse_locator(dict(request.query))
            data = await self._read(locator)
            if data is None:
                return error_response("记录已不存在或快照已过期", status_code=404)
            return json_response(
                {
                    "status": "ok",
                    "data": {
                        "locator": locator,
                        "data": data,
                        "revision": record_revision(data),
                    },
                }
            )
        except (ValueError, TypeError) as error:
            return error_response(str(error), status_code=400)

    async def api_mutate(self) -> WebApiResponse:
        """在群任务互斥锁内导入、修订或删除业务记录。"""
        try:
            body = await request.json()
            if type(body) is not dict:
                raise ValueError("无效请求")
            raw = body.get("locator")
            if not is_string_mapping(raw):
                raise ValueError("缺少记录定位字段")
            locator = parse_locator(raw)
            operation = body.get("operation")
            if operation not in {"create", "replace", "delete"}:
                raise ValueError("未知业务记录操作")
            data = body.get("data")
            record_revision(data)
            async with self._lock, AsyncExitStack() as stack:
                current = await self._read(locator)
                if locator["kind"] == "history" and is_string_mapping(current):
                    owner = current.get("platform_id")
                    if isinstance(owner, str):
                        locator["platform_id"] = owner
                if locator["platform_id"] and self.service:
                    locator["platform_id"] = (
                        self.service.bot_manager.resolve_platform_id(
                            locator["platform_id"]
                        )
                    )
                scope = locator["platform_id"] or None
                if locator["kind"] == "checkpoint":
                    scope = None
                if locator["group_id"] and self.service:
                    if any(
                        task.get("group_id") == locator["group_id"]
                        and (
                            not scope
                            or not task.get("platform")
                            or task.get("platform") == scope
                        )
                        for task in self.active_tasks.get_active_tasks()
                    ):
                        raise FileExistsError("此群有任务正在执行，请结束后再修改记录")
                    for task_type in ("daily", "incremental", "final"):
                        await stack.enter_async_context(
                            self.service.group_lock(
                                locator["group_id"], task_type, scope
                            )
                        )
                current = await self._read(locator)
                if operation == "create":
                    if locator["kind"] == "history" and self.service:
                        stored = cast(
                            "object",
                            await self.service.history_manager.plugin.get_kv_data(
                                locator["key"], None
                            ),
                        )
                        if stored is not None:
                            raise FileExistsError(
                                "记录键已存在，不可覆盖日期指针或其他版本"
                            )
                    if current is not None:
                        raise FileExistsError("记录已存在，请打开原记录进行修订")
                elif current is None or body.get("revision") != record_revision(
                    current
                ):
                    raise FileExistsError("记录已变更、删除或过期，请刷新后重试")
                await self._write(
                    locator,
                    cast("Literal['create', 'replace', 'delete']", operation),
                    data,
                    current,
                )
            return json_response({"status": "ok", "data": {"success": True}})
        except (FileExistsError, DuplicateGroupTaskError) as error:
            return error_response(str(error), status_code=409)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            return error_response(str(error), status_code=400)
        except NotImplementedError:
            return error_response("当前存储实现不支持快照修订", status_code=503)
        except (OSError, RuntimeError):
            return error_response(
                "业务记录操作失败，请查看运行日志后重试", status_code=500
            )

    async def _write(
        self,
        locator: RecordLocator,
        operation: Literal["create", "replace", "delete"],
        data: object,
        current: object,
    ) -> None:
        """分别应用模块操作，不将业务记录写成任意文件。"""
        kind = locator["kind"]
        if kind == "avatar":
            if operation != "delete":
                raise ValueError("头像是自动生成的缓存，只支持查看、导出和删除重取")
            with Cache(str(StarTools.get_data_dir(PLUGIN_NAME) / "avatar")) as cache:
                await asyncio.to_thread(
                    cast("CacheAccess", cache).delete, locator["key"]
                )
            return
        service = self.service
        if not service:
            raise ValueError("分析服务尚未初始化")
        if operation != "delete" and not is_string_mapping(data):
            raise ValueError("业务记录必须为 JSON 对象")
        if kind == "batch":
            store = service.incremental_store
            if not store:
                raise ValueError("增量存储尚未初始化")
            store = await store.for_session(locator["group_id"], locator["platform_id"])
            if operation == "delete":
                if not await store.delete_batch(
                    locator["group_id"], locator["batch_id"]
                ):
                    raise FileExistsError("批次删除失败，请刷新后重试")
            elif is_string_mapping(data) and not await store.save_batch(
                validate_batch(data, locator)
            ):
                raise RuntimeError("批次未保存")
            return
        if kind == "checkpoint":
            await self._write_checkpoint(locator, operation, data, current)
            return
        await self._write_history(locator, operation, data)

    async def _write_checkpoint(
        self,
        locator: RecordLocator,
        operation: Literal["create", "replace", "delete"],
        data: object,
        current: object,
    ) -> None:
        """修订或删除既有快照，保留原任务及有效期。"""
        service = self.service
        if not service:
            raise ValueError("分析服务尚未初始化")
        checkpoint_store = service.checkpoint_store
        if not checkpoint_store:
            raise ValueError("快照存储尚未初始化")
        if operation == "create":
            raise ValueError("阶段快照由分析任务创建；可修订或导出已有快照")
        if not is_string_mapping(current):
            raise ValueError("快照格式无效")
        if operation == "delete":
            await asyncio.to_thread(
                checkpoint_store.delete_checkpoint,
                locator["group_id"],
                locator["date_str"],
                locator["stage_name"],
                locator["trace_id"],
            )
        elif is_string_mapping(data):
            if any(
                data.get(key) != value
                for key, value in current.items()
                if key != "data"
            ):
                raise ValueError("仅能修改 data 内的产物，不可修改快照身份或生命周期")
            if type(data.get("data")) is not type(current["data"]):
                raise ValueError("请保持快照产物的根节点类型")
            if not await asyncio.to_thread(
                checkpoint_store.replace_checkpoint_data,
                str(current["checkpoint_id"]),
                current["data"],
                data["data"],
            ):
                raise FileExistsError("快照已变更，请重新读取")
        return

    async def _write_history(
        self,
        locator: RecordLocator,
        operation: Literal["create", "replace", "delete"],
        data: object,
    ) -> None:
        """维护历史版本及每日索引，不覆盖其他版本。"""
        if not self.service:
            raise ValueError("分析服务尚未初始化")
        plugin = self.service.history_manager.plugin
        current = await self._read(locator)
        platform_id = (
            str(current.get("platform_id", ""))
            if is_string_mapping(current)
            else locator["platform_id"]
        )
        match = HISTORY_KEY.fullmatch(locator["key"])
        minute = match[3] if match else None
        daily_key = HistoryManager.latest_key(
            locator["group_id"], locator["date_str"], platform_id
        )
        pointers = [daily_key]
        if platform_id and minute:
            pointers.append(
                HistoryManager.latest_key(
                    locator["group_id"], locator["date_str"], platform_id, minute
                )
            )
        if operation == "delete":
            await plugin.delete_kv_data(locator["key"])
            records = await self._history()
            for pointer_key in pointers:
                pointer = cast("object", await plugin.get_kv_data(pointer_key, None))
                if pointer != locator["key"]:
                    continue
                candidates = [
                    (key, value)
                    for key, value in records.items()
                    if key.startswith(
                        f"analysis_{locator['group_id']}_{locator['date_str']}_"
                    )
                    and str(value.get("platform_id", "")) == platform_id
                    and (pointer_key == daily_key or (minute and f"_{minute}_" in key))
                ]
                if candidates:
                    candidates.sort(
                        key=lambda item: (
                            str(item[1].get("created_at", item[0])),
                            item[0],
                        )
                    )
                    await cast("KeyValueWriter", plugin).put_kv_data(
                        pointer_key, candidates[-1][0]
                    )
                else:
                    await plugin.delete_kv_data(pointer_key)
            if is_string_mapping(current):
                analysis = current.get("analysis")
                trace_id = (
                    analysis.get("trace_id") if is_string_mapping(analysis) else None
                )
                if isinstance(trace_id, str) and trace_id:
                    task_key = f"analysis_task_{trace_id.encode().hex()}"
                    if (
                        cast("object", await plugin.get_kv_data(task_key, None))
                        == locator["key"]
                    ):
                        await plugin.delete_kv_data(task_key)
        elif is_string_mapping(data):
            if "analysis" in data and (
                not isinstance(data["analysis"], dict)
                or not isinstance(data.get("summary"), dict)
            ):
                raise ValueError("历史记录需要完整的 summary 与 analysis 对象")
            if not data:
                raise ValueError("不能保存空的历史记录")
            if platform_id and (
                data.get("platform_id") != platform_id
                or data.get("group_id") != locator["group_id"]
                or data.get("date_str") != locator["date_str"]
            ):
                raise ValueError("不能修改历史记录的会话或日期身份")
            if platform_id and is_string_mapping(current):
                old_analysis = current.get("analysis")
                new_analysis = data.get("analysis")
                if is_string_mapping(old_analysis) and (
                    not is_string_mapping(new_analysis)
                    or new_analysis.get("trace_id") != old_analysis.get("trace_id")
                ):
                    raise ValueError("不能修改历史记录的任务身份")
            analysis = data.get("analysis")
            trace_id = analysis.get("trace_id") if is_string_mapping(analysis) else None
            task_key = (
                f"analysis_task_{trace_id.encode().hex()}"
                if platform_id and isinstance(trace_id, str) and trace_id
                else None
            )
            if task_key:
                owner = await plugin.get_kv_data(task_key, None)
                if owner is not None and owner != locator["key"]:
                    raise ValueError("此任务已有历史版本，不能绑定到另一条记录")
            await cast("KeyValueWriter", plugin).put_kv_data(locator["key"], data)
            if task_key:
                await cast("KeyValueWriter", plugin).put_kv_data(
                    task_key, locator["key"]
                )
            for pointer_key in pointers:
                pointer = cast("object", await plugin.get_kv_data(pointer_key, None))
                if locator["key"] != pointer_key and (
                    pointer is None
                    or (
                        not platform_id
                        and isinstance(pointer, str)
                        and locator["key"] > pointer
                    )
                ):
                    await cast("KeyValueWriter", plugin).put_kv_data(
                        pointer_key, locator["key"]
                    )
