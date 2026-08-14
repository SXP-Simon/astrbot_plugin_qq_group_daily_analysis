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
    _SEMAPHORE_WARN_SECONDS = 15.0

    def __init__(
        self,
        config_manager: Any,
        plugin_instance: Any,
        analyze_callback: Callable[[str, str], Awaitable[dict | None]],
        on_analysis_succeeded: Callable[[str, str], None] | None = None,
    ) -> None:
        """初始化触发协调器。

        Args:
            config_manager: 插件配置管理器。
            plugin_instance: 提供 KV 存储接口的插件实例。
            analyze_callback: 执行单群增量分析的异步回调。
            on_analysis_succeeded: 批次成功结算后执行的同步通知回调。
        """
        self.config_manager = config_manager
        self.plugin = plugin_instance
        self.analyze_callback = analyze_callback
        self.on_analysis_succeeded = on_analysis_succeeded
        self._states: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._seen_event_ids: OrderedDict[str, None] = OrderedDict()
        self._analysis_tasks: dict[str, asyncio.Task] = {}
        self._running_state_keys: set[str] = set()
        self._state_versions: dict[str, int] = {}
        self._target_config_signature: tuple[Any, ...] | None = None
        self._flush_task: asyncio.Task | None = None
        self._closed = False
        self._semaphore: asyncio.Semaphore | None = None

    def is_target_group(self, unified_msg_origin: str) -> bool:
        """判断消息所属群是否启用了增量分析。"""
        if not self.config_manager.get_incremental_enabled():
            return False
        return self.config_manager.is_incremental_group_allowed(unified_msg_origin)

    def _get_target_config_signature(self) -> tuple[Any, ...]:
        """生成影响增量目标群判定的配置快照。"""

        def get_group_list(getter_name: str) -> tuple[str, ...]:
            getter = getattr(self.config_manager, getter_name, None)
            values = getter() if callable(getter) else []
            if not isinstance(values, (list, tuple, set)):
                values = [values]
            return tuple(sorted({str(value).strip() for value in values}))

        def get_group_mode(getter_name: str, default: str) -> str:
            getter = getattr(self.config_manager, getter_name, None)
            value = getter() if callable(getter) else default
            return str(value).strip().lower()

        return (
            bool(self.config_manager.get_incremental_enabled()),
            get_group_mode("get_group_list_mode", "none"),
            get_group_list("get_group_list"),
            get_group_mode("get_scheduled_group_list_mode", "whitelist"),
            get_group_list("get_scheduled_group_list"),
            get_group_mode("get_incremental_group_list_mode", "whitelist"),
            get_group_list("get_incremental_group_list"),
        )

    async def refresh_target_states(self) -> None:
        """在名单配置变化后清理不再允许的待处理状态。"""
        await self._ensure_loaded()
        config_signature = self._get_target_config_signature()
        if config_signature == self._target_config_signature:
            return

        tasks_to_cancel: list[asyncio.Task] = []
        removed_state_keys: list[str] = []
        cancelled_state_keys: list[str] = []
        removed_count = 0
        is_initial_snapshot = self._target_config_signature is None
        async with self._state_lock:
            for state_key in list(self._states):
                if self.is_target_group(state_key):
                    continue
                self._states.pop(state_key, None)
                self._state_versions[state_key] = (
                    self._state_versions.get(state_key, 0) + 1
                )
                removed_count += 1
                removed_state_keys.append(state_key)
                task = self._analysis_tasks.get(state_key)
                if task and state_key not in self._running_state_keys:
                    # 尚未进入分析服务的任务可以安全取消。先移出任务表，避免
                    # 任务在首次执行前被取消而没有机会运行 finally，留下幽灵任务。
                    self._analysis_tasks.pop(state_key, None)
                    tasks_to_cancel.append(task)
                    cancelled_state_keys.append(state_key)
            self._target_config_signature = config_signature
            active_task_count = len(self._analysis_tasks)

        for task in tasks_to_cancel:
            task.cancel()
        if removed_count:
            self._schedule_flush()
        if is_initial_snapshot:
            logger.debug(
                "增量名单初始快照已建立：清理待处理群=%s，当前活跃群任务=%s",
                removed_count,
                active_task_count,
            )
        else:
            logger.info(
                "增量名单配置已更新：清理待处理群=%s，取消未开始任务=%s，当前活跃群任务=%s",
                removed_count,
                len(tasks_to_cancel),
                active_task_count,
            )
        if removed_state_keys:
            logger.debug(
                "增量名单变更明细：移出群=%s，取消未开始任务=%s",
                ", ".join(sorted(removed_state_keys)),
                ", ".join(sorted(cancelled_state_keys)) or "无",
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
                        "version": 1,
                    }
                    self._state_versions[str(key)] = 1
            self._loaded = True
            state_details = ", ".join(
                f"{state_key}={int(state['count'])}"
                for state_key, state in sorted(self._states.items())
            )
            logger.debug(
                "增量计数状态恢复完成: 群数=%s, 待处理消息=%s, 群计数=[%s]",
                len(self._states),
                sum(int(state.get("count", 0)) for state in self._states.values()),
                state_details or "无",
            )

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
                key: {
                    "platform_id": state["platform_id"],
                    "group_id": state["group_id"],
                    "count": int(state["count"]),
                }
                for key, state in self._states.items()
                if int(state.get("count", 0)) > 0
            }
        await self.plugin.put_kv_data(
            self._KV_KEY,
            {"version": 1, "updated_at": time.time(), "states": states},
        )
        logger.debug(
            "增量计数状态已持久化: 群数=%s, 待处理消息=%s",
            len(states),
            sum(int(state.get("count", 0)) for state in states.values()),
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
        if self._closed:
            return False

        await self.refresh_target_states()
        if not self.is_target_group(unified_msg_origin):
            return False

        platform_id = str(platform_id or "").strip()
        group_id = str(group_id or "").strip()
        if not platform_id or not group_id:
            return False

        event_key = f"{platform_id}:{group_id}:{message_id}" if message_id else ""
        if event_key:
            if event_key in self._seen_event_ids:
                self._seen_event_ids.move_to_end(event_key)
                logger.debug(
                    "忽略重复增量消息事件: platform=%s, group=%s, message_id=%s",
                    platform_id,
                    group_id,
                    message_id,
                )
                return True
            self._seen_event_ids[event_key] = None
            if len(self._seen_event_ids) > self._SEEN_EVENT_LIMIT:
                self._seen_event_ids.popitem(last=False)

        await self._ensure_loaded()
        state_key = f"{platform_id}:GroupMessage:{group_id}"
        async with self._state_lock:
            state = self._states.get(state_key)
            if state is None:
                version = self._state_versions.get(state_key, 0) + 1
                self._state_versions[state_key] = version
                state = {
                    "platform_id": platform_id,
                    "group_id": group_id,
                    "count": 0,
                    "version": version,
                }
                self._states[state_key] = state
            state["count"] = int(state["count"]) + 1
            pending_count = int(state["count"])
            threshold = self.config_manager.get_incremental_min_messages()
            should_trigger = pending_count >= threshold

        self._schedule_flush()
        if should_trigger:
            self._schedule_analysis(state_key)
        logger.debug(
            "增量消息 Hook 已记录: platform=%s, group=%s, pending=%s, "
            "threshold=%s, 已安排任务=%s, 当前活跃群任务=%s",
            platform_id,
            group_id,
            pending_count,
            threshold,
            state_key in self._analysis_tasks,
            len(self._analysis_tasks),
        )
        return True

    def _schedule_analysis(self, state_key: str) -> None:
        """确保同一个群同一时间只有一个消息量触发任务。"""
        if (
            self._closed
            or state_key in self._analysis_tasks
            or not self.is_target_group(state_key)
        ):
            return
        state = self._states.get(state_key, {})
        task = asyncio.create_task(
            self._run_analysis(state_key),
            name=f"incremental_volume_{state_key}",
        )
        self._analysis_tasks[state_key] = task
        logger.debug(
            "增量消息计数达到阈值，安排分析任务: platform=%s, group=%s, pending=%s, "
            "threshold=%s, 当前活跃群任务=%s",
            state.get("platform_id", ""),
            state.get("group_id", ""),
            int(state.get("count", 0)),
            self.config_manager.get_incremental_min_messages(),
            len(self._analysis_tasks),
        )

    async def _run_analysis(self, state_key: str) -> None:
        """执行分析并根据实际消费数量修正估算计数。"""
        allow_continuation = False
        discarded = False
        task_version = -1
        current_task = asyncio.current_task()
        try:
            await self.refresh_target_states()
            async with self._state_lock:
                state = self._states.get(state_key)
                if not state:
                    return
                count_at_start = int(state.get("count", 0))
                platform_id = str(state["platform_id"])
                group_id = str(state["group_id"])
                task_version = int(state.get("version", 0))

            logger.debug(
                "增量分析任务开始: platform=%s, group=%s, pending_at_start=%s",
                platform_id,
                group_id,
                count_at_start,
            )
            started_at = time.monotonic()

            if self._semaphore is None:
                self._semaphore = asyncio.Semaphore(
                    max(1, self.config_manager.get_max_concurrent_tasks())
                )
            wait_started_at = time.monotonic()
            logger.debug(
                "增量分析等待调度槽位: platform=%s, group=%s, available=%s, active_tasks=%s",
                platform_id,
                group_id,
                getattr(self._semaphore, "_value", None),
                len(self._analysis_tasks),
            )
            while True:
                try:
                    await asyncio.wait_for(
                        self._semaphore.acquire(), timeout=self._SEMAPHORE_WARN_SECONDS
                    )
                    break
                except TimeoutError:
                    logger.warning(
                        "增量分析等待调度槽位超过 %.0fs: platform=%s, group=%s, "
                        "available=%s, active_tasks=%s",
                        time.monotonic() - wait_started_at,
                        platform_id,
                        group_id,
                        getattr(self._semaphore, "_value", None),
                        len(self._analysis_tasks),
                    )
            logger.debug(
                "增量分析已取得调度槽位: platform=%s, group=%s, wait=%.2fs, available=%s",
                platform_id,
                group_id,
                time.monotonic() - wait_started_at,
                getattr(self._semaphore, "_value", None),
            )
            try:
                async with self._state_lock:
                    state = self._states.get(state_key)
                    if (
                        not state
                        or int(state.get("version", -1)) != task_version
                        or not self.is_target_group(state_key)
                    ):
                        return
                    self._running_state_keys.add(state_key)
                try:
                    result = await self.analyze_callback(group_id, platform_id)
                finally:
                    self._running_state_keys.discard(state_key)
            finally:
                self._semaphore.release()
                logger.debug(
                    "增量分析已释放调度槽位: platform=%s, group=%s, available=%s",
                    platform_id,
                    group_id,
                    getattr(self._semaphore, "_value", None),
                )

            result = result if isinstance(result, dict) else {}
            consumed = max(0, int(result.get("messages_count", 0)))
            reason = str(result.get("reason", ""))
            await self.refresh_target_states()
            async with self._state_lock:
                state = self._states.get(state_key)
                if (
                    not state
                    or int(state.get("version", -1)) != task_version
                    or not self.is_target_group(state_key)
                ):
                    discarded = True
                    remaining_count = 0
                    new_arrivals = 0
                else:
                    current_count = int(state.get("count", 0))
                    new_arrivals = max(0, current_count - count_at_start)
                    if result.get("success"):
                        state["count"] = max(0, current_count - consumed)
                    elif reason == "below_threshold":
                        state["count"] = consumed + new_arrivals
                    elif reason == "no_messages":
                        state["count"] = new_arrivals
                    # 成功消费后可连续排空积压；失败必须等待任务结束后的新消息。
                    allow_continuation = bool(result.get("success") and consumed > 0)
                    remaining_count = int(state.get("count", 0))

            logger.debug(
                "增量分析计数结算: platform=%s, group=%s, success=%s, reason=%s, "
                "pending_at_start=%s, new_arrivals=%s, consumed=%s, remaining=%s, "
                "allow_continuation=%s, discarded=%s, 当前活跃群任务=%s, duration=%.2fs",
                platform_id,
                group_id,
                bool(result.get("success")),
                reason or "none",
                count_at_start,
                new_arrivals,
                consumed,
                remaining_count,
                allow_continuation,
                discarded,
                len(self._analysis_tasks),
                time.monotonic() - started_at,
            )

            self._schedule_flush()
            if (
                result.get("success")
                and consumed > 0
                and not discarded
                and self.on_analysis_succeeded
            ):
                try:
                    self.on_analysis_succeeded(group_id, platform_id)
                except Exception as exc:
                    logger.error(f"通知增量批次成功事件失败：{exc}", exc_info=True)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"消息量触发增量分析失败：{exc}", exc_info=True)
        finally:
            if self._analysis_tasks.get(state_key) is current_task:
                self._analysis_tasks.pop(state_key, None)
            logger.debug(
                "增量分析任务已结束：state=%s，当前活跃群任务=%s",
                state_key,
                len(self._analysis_tasks),
            )

        if self._closed:
            return
        async with self._state_lock:
            state = self._states.get(state_key)
            current_count = int(state.get("count", 0)) if state else 0
            should_continue = bool(
                state
                and self.is_target_group(state_key)
                and current_count >= self.config_manager.get_incremental_min_messages()
                and (
                    allow_continuation
                    or (discarded and int(state.get("version", -1)) != task_version)
                )
            )
        if should_continue:
            logger.debug(
                "增量分析继续处理待办批次: state=%s, pending=%s, threshold=%s",
                state_key,
                current_count,
                self.config_manager.get_incremental_min_messages(),
            )
            self._schedule_analysis(state_key)

    async def start(self) -> int:
        """恢复持久化计数，并继续执行已经达到阈值的群。

        Returns:
            启动时恢复的分析任务数量。
        """
        await self.refresh_target_states()
        async with self._state_lock:
            ready_keys = [
                state_key
                for state_key, state in self._states.items()
                if self.is_target_group(state_key)
                and int(state.get("count", 0))
                >= self.config_manager.get_incremental_min_messages()
            ]
        for state_key in ready_keys:
            self._schedule_analysis(state_key)
        logger.info(
            "增量状态恢复完成：恢复任务=%s，当前活跃群任务=%s",
            len(ready_keys),
            len(self._analysis_tasks),
        )
        if ready_keys:
            logger.debug("增量状态恢复任务明细：群=%s", ", ".join(sorted(ready_keys)))
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
