"""任务排他锁与并发槽位守卫模块

负责群组任务防重互斥锁、活跃任务跟踪以及全局 LLM 并发信号量槽位调度。
"""

from __future__ import annotations

import asyncio
import time as time_mod
import weakref
from contextlib import asynccontextmanager

from ...shared.trace_context import TraceContext
from ...utils.logger import logger

_LLM_SEMAPHORE_INFO_SECONDS = 1.0
_LLM_SEMAPHORE_WARN_SECONDS = 15.0


class DuplicateGroupTaskError(Exception):
    """当同一个群组在同一时间尝试启动相同类型的重复任务时抛出。"""


class TaskGuard:
    """任务并发控制与排他锁管理器。"""

    def __init__(self, max_concurrent: int = 1):
        """初始化任务守卫。

        Args:
            max_concurrent: 最大允许的 LLM 全局并发任务数。
        """
        self._locks = weakref.WeakValueDictionary()
        self._active_tasks: set[str] = set()
        self._max_concurrent = max(1, int(max_concurrent))
        self.llm_semaphore = asyncio.Semaphore(self._max_concurrent)

    def is_group_running(self, group_id: str, task_type: str = "daily") -> bool:
        """检查指定群的特定任务是否正在运行中。

        Args:
            group_id: 群组唯一标识。
            task_type: 任务类型（如 'daily', 'final', 'incremental' 等）。

        Returns:
            True 表示任务正在执行，False 表示空闲。
        """
        lock_key = f"{task_type}:{group_id}"
        return lock_key in self._active_tasks

    @asynccontextmanager
    async def group_lock(self, group_id: str, task_type: str = "analysis"):
        """获取群组排他锁上下文管理器。

        保证同一时间同一个群只能有一个同类型任务在执行，退出时自动释放。

        Args:
            group_id: 群号。
            task_type: 任务类型。

        Yields:
            None: 成功获取锁后进入上下文。

        Raises:
            DuplicateGroupTaskError: 当任务已在运行时抛出，避免竞态重复执行。
        """
        lock_key = f"{task_type}:{group_id}"
        lock = self._locks.get(lock_key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[lock_key] = lock

        if lock_key in self._active_tasks:
            logger.warning(f"群 {group_id} 的 {task_type} 任务已在运行，跳过本次请求")
            raise DuplicateGroupTaskError(f"Duplicate task for {lock_key}")

        self._active_tasks.add(lock_key)
        try:
            async with lock:
                logger.debug(f"[Lock] 已获取群 {group_id} 的 {task_type} 排他锁")
                yield
        finally:
            self._active_tasks.discard(lock_key)
            logger.debug(f"[Lock] 已释放群 {group_id} 的 {task_type} 排他锁")

    @asynccontextmanager
    async def llm_slot(self, group_id: str, stage: str):
        """占用全局 LLM 分析并发槽位上下文管理器。

        Args:
            group_id: 当前任务所属群号。
            stage: 分析阶段名称。

        Yields:
            None: 成功进入槽位后交还控制权。
        """
        trace = TraceContext.current()
        missing_marker = object()
        previous_stage = missing_marker
        previous_group_id = missing_marker
        if trace:
            previous_stage = trace.metadata.get("llm_stage", missing_marker)
            previous_group_id = trace.metadata.get("llm_group_id", missing_marker)
            trace.metadata["llm_stage"] = stage
            trace.metadata["llm_group_id"] = group_id

        wait_started_at = time_mod.monotonic()
        logger.debug(
            f"[LLM 队列观测] 等待分析槽位: group={group_id}, stage={stage}, "
            f"available={getattr(self.llm_semaphore, '_value', None)}/"
            f"{self._max_concurrent}, active={len(self._active_tasks)}"
        )

        while True:
            try:
                await asyncio.wait_for(
                    self.llm_semaphore.acquire(), timeout=_LLM_SEMAPHORE_WARN_SECONDS
                )
                break
            except TimeoutError:
                logger.warning(
                    f"[LLM 队列观测] 等待分析槽位超过 "
                    f"{time_mod.monotonic() - wait_started_at:.0f}s: "
                    f"group={group_id}, stage={stage}, "
                    f"available={getattr(self.llm_semaphore, '_value', None)}/"
                    f"{self._max_concurrent}, active={len(self._active_tasks)}"
                )

        waited_seconds = time_mod.monotonic() - wait_started_at
        log_method = (
            logger.info
            if waited_seconds >= _LLM_SEMAPHORE_INFO_SECONDS
            else logger.debug
        )
        log_method(
            f"[LLM 队列观测] 已进入分析槽位: group={group_id}, stage={stage}, "
            f"wait={waited_seconds:.2f}s, "
            f"available={getattr(self.llm_semaphore, '_value', None)}/"
            f"{self._max_concurrent}, active={len(self._active_tasks)}"
        )

        run_started_at = time_mod.monotonic()
        try:
            yield
        finally:
            self.llm_semaphore.release()
            logger.debug(
                f"[LLM 队列观测] 已释放分析槽位: group={group_id}, stage={stage}, "
                f"duration={time_mod.monotonic() - run_started_at:.2f}s, "
                f"available={getattr(self.llm_semaphore, '_value', None)}/"
                f"{self._max_concurrent}, active={len(self._active_tasks)}"
            )
            if trace:
                if previous_stage is missing_marker:
                    trace.metadata.pop("llm_stage", None)
                else:
                    trace.metadata["llm_stage"] = previous_stage
                if previous_group_id is missing_marker:
                    trace.metadata.pop("llm_group_id", None)
                else:
                    trace.metadata["llm_group_id"] = previous_group_id
