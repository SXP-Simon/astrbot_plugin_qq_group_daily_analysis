"""基于群消息量的增量分析触发协调器。"""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from ...utils.logger import logger


class IncrementalTriggerCoordinator:
    """维护每个群的待处理消息计数并触发增量分析。"""

    _KV_KEY = "incremental_trigger_states_v1"
    _SEEN_EVENT_LIMIT = 8192
    _FLUSH_DELAY_SECONDS = 5

    def __init__(
        self,
        config_manager: Any,
        plugin_instance: Any,
        analyze_callback: Callable[[str, str], Awaitable[dict | None]],
    ) -> None:
        """初始化触发协调器。

        Args:
            config_manager: 插件配置管理器。
            plugin_instance: 提供 KV 存储接口的插件实例。
            analyze_callback: 执行单群增量分析的异步回调。
        """
        self.config_manager = config_manager
        self.plugin = plugin_instance
        self.analyze_callback = analyze_callback
        self._states: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._seen_event_ids: OrderedDict[str, None] = OrderedDict()
        self._analysis_tasks: dict[str, asyncio.Task] = {}
        self._flush_task: asyncio.Task | None = None
        self._closed = False
        self._semaphore: asyncio.Semaphore | None = None

    def _is_target_group(self, unified_msg_origin: str) -> bool:
        """判断消息所属群是否启用了增量分析。"""
        if not self.config_manager.get_incremental_enabled():
            return False
        if not self.config_manager.is_group_allowed(unified_msg_origin):
            return False
        if not self.config_manager.is_group_in_filtered_list(
            unified_msg_origin,
            self.config_manager.get_scheduled_group_list_mode(),
            self.config_manager.get_scheduled_group_list(),
        ):
            return False
        return self.config_manager.is_group_in_filtered_list(
            unified_msg_origin,
            self.config_manager.get_incremental_group_list_mode(),
            self.config_manager.get_incremental_group_list(),
        )

    async def _ensure_loaded(self) -> None:
        """首次使用时从 KV 恢复尚未消费的群消息计数。"""
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            data = await self.plugin.get_kv_data(self._KV_KEY, {})
            if isinstance(data, dict) and isinstance(data.get("states"), dict):
                for key, state in data["states"].items():
                    if not isinstance(state, dict):
                        continue
                    platform_id = str(state.get("platform_id", "")).strip()
                    group_id = str(state.get("group_id", "")).strip()
                    if not platform_id or not group_id:
                        continue
                    try:
                        count = max(0, int(state.get("count", 0)))
                    except (TypeError, ValueError):
                        continue
                    self._states[str(key)] = {
                        "platform_id": platform_id,
                        "group_id": group_id,
                        "count": count,
                    }
            self._loaded = True

    def _schedule_flush(self) -> None:
        """合并短时间内的计数更新，避免每条消息都写 KV。"""
        if self._closed or (self._flush_task and not self._flush_task.done()):
            return
        self._flush_task = asyncio.create_task(
            self._delayed_flush(), name="incremental_counter_flush"
        )

    async def _delayed_flush(self) -> None:
        """短暂合并连续计数写入后持久化状态。"""
        try:
            await asyncio.sleep(self._FLUSH_DELAY_SECONDS)
            await self.flush()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"持久化增量消息计数失败：{exc}")

    async def flush(self) -> None:
        """立即持久化当前计数状态。"""
        await self._ensure_loaded()
        async with self._state_lock:
            states = {
                key: dict(state)
                for key, state in self._states.items()
                if int(state.get("count", 0)) > 0
            }
        await self.plugin.put_kv_data(
            self._KV_KEY,
            {"version": 1, "updated_at": time.time(), "states": states},
        )

    async def record_message(
        self,
        platform_id: str,
        group_id: str,
        unified_msg_origin: str,
        message_id: str = "",
    ) -> bool:
        """记录一条群消息，并在达到阈值时安排分析。

        Args:
            platform_id: AstrBot 平台实例 ID。
            group_id: 平台群组 ID。
            unified_msg_origin: AstrBot 统一消息来源。
            message_id: 平台消息 ID，用于抑制重复事件。

        Returns:
            消息是否属于启用增量分析的目标群。
        """
        if self._closed or not self._is_target_group(unified_msg_origin):
            return False

        platform_id = str(platform_id or "").strip()
        group_id = str(group_id or "").strip()
        if not platform_id or not group_id:
            return False

        event_key = f"{platform_id}:{group_id}:{message_id}" if message_id else ""
        if event_key:
            if event_key in self._seen_event_ids:
                self._seen_event_ids.move_to_end(event_key)
                return True
            self._seen_event_ids[event_key] = None
            if len(self._seen_event_ids) > self._SEEN_EVENT_LIMIT:
                self._seen_event_ids.popitem(last=False)

        await self._ensure_loaded()
        state_key = f"{platform_id}:GroupMessage:{group_id}"
        async with self._state_lock:
            state = self._states.setdefault(
                state_key,
                {
                    "platform_id": platform_id,
                    "group_id": group_id,
                    "count": 0,
                },
            )
            state["count"] = int(state["count"]) + 1
            should_trigger = (
                int(state["count"])
                >= self.config_manager.get_incremental_min_messages()
            )

        self._schedule_flush()
        if should_trigger:
            self._schedule_analysis(state_key)
        return True

    def _schedule_analysis(self, state_key: str) -> None:
        """确保同一个群同一时间只有一个消息量触发任务。"""
        if self._closed or state_key in self._analysis_tasks:
            return
        task = asyncio.create_task(
            self._run_analysis(state_key),
            name=f"incremental_volume_{state_key}",
        )
        self._analysis_tasks[state_key] = task

    async def _run_analysis(self, state_key: str) -> None:
        """执行分析并根据实际消费数量修正估算计数。"""
        allow_continuation = False
        count_after_result: int | None = None
        try:
            await self._ensure_loaded()
            async with self._state_lock:
                state = self._states.get(state_key)
                if not state:
                    return
                count_at_start = int(state.get("count", 0))
                platform_id = str(state["platform_id"])
                group_id = str(state["group_id"])

            if self._semaphore is None:
                self._semaphore = asyncio.Semaphore(
                    max(1, self.config_manager.get_max_concurrent_tasks())
                )
            async with self._semaphore:
                result = await self.analyze_callback(group_id, platform_id)

            result = result if isinstance(result, dict) else {}
            consumed = max(0, int(result.get("messages_count", 0)))
            reason = str(result.get("reason", ""))
            async with self._state_lock:
                state = self._states.get(state_key)
                if not state:
                    return
                current_count = int(state.get("count", 0))
                new_arrivals = max(0, current_count - count_at_start)
                if result.get("success"):
                    state["count"] = max(0, current_count - consumed)
                elif reason == "below_threshold":
                    state["count"] = consumed + new_arrivals
                elif reason == "no_messages":
                    state["count"] = new_arrivals
                count_after_result = int(state["count"])
                # 成功消费后可连续排空积压；失败仅在执行期间有新消息时重试。
                allow_continuation = bool(result.get("success") and consumed > 0) or (
                    not result.get("success") and new_arrivals > 0
                )

            self._schedule_flush()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"消息量触发增量分析失败：{exc}", exc_info=True)
        finally:
            self._analysis_tasks.pop(state_key, None)

        if self._closed:
            return
        async with self._state_lock:
            state = self._states.get(state_key)
            current_count = int(state.get("count", 0)) if state else 0
            arrived_after_result = (
                count_after_result is not None and current_count > count_after_result
            )
            should_continue = bool(
                state
                and current_count >= self.config_manager.get_incremental_min_messages()
                and (allow_continuation or arrived_after_result)
            )
        if should_continue:
            self._schedule_analysis(state_key)

    async def start(self) -> int:
        """恢复持久化计数，并继续执行已经达到阈值的群。

        Returns:
            启动时恢复的分析任务数量。
        """
        await self._ensure_loaded()
        async with self._state_lock:
            ready_keys = [
                state_key
                for state_key, state in self._states.items()
                if self._is_target_group(state_key)
                and int(state.get("count", 0))
                >= self.config_manager.get_incremental_min_messages()
            ]
        for state_key in ready_keys:
            self._schedule_analysis(state_key)
        return len(ready_keys)

    async def close(self) -> None:
        """停止后台任务并持久化尚未消费的计数。"""
        self._closed = True
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            await asyncio.gather(self._flush_task, return_exceptions=True)
        tasks = list(self._analysis_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._analysis_tasks.clear()
        await self.flush()
