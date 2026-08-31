"""
活跃任务管理器与 Task Reaper 孤儿回收守护器
负责内存活跃任务追踪、主动中止 (Cancellation) 以及超时任务的自动回收清理。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from ...utils.logger import logger


@dataclass
class ActiveTaskInfo:
    task_id: str
    group_id: str
    group_name: str
    platform: str
    trigger_type: str
    current_stage: str
    started_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    asyncio_task: asyncio.Task[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "group_id": self.group_id,
            "group_name": self.group_name,
            "platform": self.platform,
            "trigger_type": self.trigger_type,
            "current_stage": self.current_stage,
            "started_at": self.started_at,
            "duration_s": round(time.time() - self.started_at, 1),
            "last_heartbeat": self.last_heartbeat,
        }


class ActiveTaskManager:
    """活跃任务管理器与孤儿回收器"""

    def __init__(self, trace_store: Any | None = None):
        self.trace_store = trace_store
        self._tasks: dict[str, ActiveTaskInfo] = {}
        self._lock = asyncio.Lock()
        self._reaper_task: asyncio.Task[None] | None = None
        self._subscribers: set[asyncio.Queue[str]] = set()

    async def register_task(
        self,
        task_id: str,
        group_id: str,
        group_name: str = "",
        platform: str = "",
        trigger_type: str = "manual",
        current_stage: str = "FETCH_MESSAGES",
        asyncio_task: asyncio.Task[Any] | None = None,
    ) -> None:
        """注册新运行中的任务"""
        async with self._lock:
            info = ActiveTaskInfo(
                task_id=task_id,
                group_id=str(group_id),
                group_name=group_name,
                platform=platform,
                trigger_type=trigger_type,
                current_stage=current_stage,
                asyncio_task=asyncio_task,
            )
            self._tasks[task_id] = info
        await self._broadcast_event({"event": "task_started", "data": info.to_dict()})

    async def update_stage(self, task_id: str, stage_name: str) -> None:
        """更新当前活跃任务的阶段名称并更新心跳"""
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].current_stage = stage_name
                self._tasks[task_id].last_heartbeat = time.time()
                info = self._tasks[task_id]
            else:
                info = None

        if info:
            await self._broadcast_event(
                {"event": "task_progress", "data": info.to_dict()}
            )

    update_task_stage = update_stage

    def update_stage_sync(self, task_id: str, stage_name: str) -> None:
        """同步更新活跃任务阶段（供 Span 上下文即时调用）"""
        if task_id in self._tasks:
            self._tasks[task_id].current_stage = stage_name
            self._tasks[task_id].last_heartbeat = time.time()
            info = self._tasks[task_id]
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self._broadcast_event(
                        {"event": "task_progress", "data": info.to_dict()}
                    )
                )
            except RuntimeError:
                pass

    async def finish_task(self, task_id: str) -> None:
        """标记任务结束并移出活跃列表"""
        async with self._lock:
            removed = self._tasks.pop(task_id, None)

        if removed:
            await self._broadcast_event(
                {
                    "event": "task_finished",
                    "data": {"task_id": task_id, "group_id": removed.group_id},
                }
            )

    async def cancel_task(self, task_id: str) -> bool:
        """主动取消任务"""
        async with self._lock:
            task_info = self._tasks.get(task_id)
            if not task_info:
                return False

            if task_info.asyncio_task and not task_info.asyncio_task.done():
                task_info.asyncio_task.cancel()

            self._tasks.pop(task_id, None)

        if self.trace_store:
            try:
                self.trace_store.save_trace(
                    {
                        "trace_id": task_id,
                        "status": "aborted",
                        "error_message": "Task canceled manually via WebUI",
                    }
                )
            except Exception as e:
                logger.warning(f"更新取消任务状态失败: {e}")

        await self._broadcast_event(
            {"event": "task_canceled", "data": {"task_id": task_id}}
        )
        return True

    def get_active_tasks(self) -> list[dict[str, Any]]:
        """获取所有当前正在运行的任务快照"""
        return [t.to_dict() for t in self._tasks.values()]

    # ── SSE 实时广播支持 ──

    def subscribe(self) -> asyncio.Queue[str]:
        """订阅实时事件队列"""
        q: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        """取消订阅"""
        self._subscribers.discard(q)

    async def _broadcast_event(self, event_data: dict[str, Any]) -> None:
        """向所有连接的 WebUI 客户端广播事件"""
        import json

        raw = json.dumps(event_data, ensure_ascii=False)
        for q in list(self._subscribers):
            try:
                q.put_nowait(raw)
            except Exception:
                self._subscribers.discard(q)

    # ── Task Reaper 守护线程 ──

    def start_reaper(
        self, interval_seconds: int = 30, timeout_seconds: int = 600
    ) -> None:
        """启动孤儿任务超时扫描守护协程，并在开机时自动对账清理历史遗留 running 记录"""
        if self.trace_store and hasattr(
            self.trace_store, "reconcile_crashed_traces_on_startup"
        ):
            try:
                reconciled = self.trace_store.reconcile_crashed_traces_on_startup()
                if reconciled > 0:
                    logger.info(
                        f"[TaskReaper] 开机自愈对账：已回收 {reconciled} 条异常中断的幽灵任务"
                    )
            except Exception as e:
                logger.error(f"[TaskReaper] 开机自愈对账异常: {e}")

        if self._reaper_task is None or self._reaper_task.done():
            self._reaper_task = asyncio.create_task(
                self._reaper_loop(interval_seconds, timeout_seconds)
            )

    def stop_reaper(self) -> None:
        """停止守护协程"""
        if self._reaper_task and not self._reaper_task.done():
            self._reaper_task.cancel()

    async def _reaper_loop(self, interval_seconds: int, timeout_seconds: int) -> None:
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                now = time.time()
                timed_out_tasks: list[ActiveTaskInfo] = []

                async with self._lock:
                    for task_id, info in list(self._tasks.items()):
                        if now - info.last_heartbeat > timeout_seconds:
                            timed_out_tasks.append(info)
                            self._tasks.pop(task_id, None)

                for info in timed_out_tasks:
                    logger.warning(
                        f"[TaskReaper] 任务 {info.task_id} (群 {info.group_id}) 超过 {timeout_seconds}s 未更新心跳，强制回收清理"
                    )
                    if info.asyncio_task and not info.asyncio_task.done():
                        info.asyncio_task.cancel()

                    if self.trace_store:
                        try:
                            self.trace_store.save_trace(
                                {
                                    "trace_id": info.task_id,
                                    "status": "failed",
                                    "error_stage": info.current_stage,
                                    "error_message": f"Task timed out after {timeout_seconds}s (Reaped)",
                                }
                            )
                        except Exception as e:
                            logger.error(f"Reaper 更新持久化状态失败: {e}")

                    await self._broadcast_event(
                        {
                            "event": "task_timed_out",
                            "data": {"task_id": info.task_id},
                        }
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TaskReaper] 巡检异常: {e}", exc_info=True)
