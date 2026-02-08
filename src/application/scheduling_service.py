"""
调度服务 - 计划分析的应用服务

该服务管理计划的分析任务并与
分析编排器协调。
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from ..infrastructure.config import ConfigManager
from ..utils.logger import logger


class ScheduledTask:
    """表示一个计划的分析任务。"""

    def __init__(
        self,
        task_id: str,
        group_id: str,
        scheduled_time: str,  # HH:MM 格式
        callback: Callable,
        enabled: bool = True,
    ):
        self.task_id = task_id
        self.group_id = group_id
        self.scheduled_time = scheduled_time
        self.callback = callback
        self.enabled = enabled
        self.last_run: datetime | None = None
        self.next_run: datetime | None = None
        self._calculate_next_run()

    def _calculate_next_run(self) -> None:
        """计算下一次运行时间。"""
        if not self.enabled:
            self.next_run = None
            return

        try:
            hours, minutes = map(int, self.scheduled_time.split(":"))
            now = datetime.now()
            next_run = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            # 如果今天的时间已过，计划明天运行
            if next_run <= now:
                next_run += timedelta(days=1)

            self.next_run = next_run
        except ValueError:
            logger.error(f"无效的计划时间格式: {self.scheduled_time}")
            self.next_run = None

    def should_run(self) -> bool:
        """检查任务现在是否应该运行。"""
        if not self.enabled or not self.next_run:
            return False

        now = datetime.now()

        # 检查我们是否在执行窗口内（5分钟容差）
        if self.next_run <= now <= self.next_run + timedelta(minutes=5):
            # 检查我们今天是否还没有运行
            if self.last_run is None or self.last_run.date() != now.date():
                return True

        return False

    def mark_completed(self) -> None:
        """将任务标记为完成并计划下一次运行。"""
        self.last_run = datetime.now()
        self._calculate_next_run()


class SchedulingService:
    """
    管理计划分析任务的应用服务。

    该服务运行一个后台循环，检查并
    执行计划的任务。
    """

    def __init__(self, config: ConfigManager):
        """
        初始化调度服务。

        Args:
            config: 配置管理器
        """
        self.config = config
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._callbacks: dict[str, Callable] = {}

    def register_callback(self, name: str, callback: Callable) -> None:
        """
        为计划任务注册回调。

        Args:
            name: 回调名称
            callback: 异步回调函数
        """
        self._callbacks[name] = callback

    def add_task(
        self,
        group_id: str,
        scheduled_time: str | None = None,
        callback_name: str = "analyze",
    ) -> str:
        """
        为群组添加计划任务。

        Args:
            group_id: 群组标识符
            scheduled_time: HH:MM 格式的时间（如果未提供，则使用配置默认值）
            callback_name: 要使用的注册回调的名称

        Returns:
            任务 ID
        """
        scheduled_time = scheduled_time or self.config.get_analysis_time()
        task_id = f"task_{group_id}"

        callback = self._callbacks.get(callback_name)
        if not callback:
            logger.warning(f"回调 '{callback_name}' 未注册")
            return task_id

        task = ScheduledTask(
            task_id=task_id,
            group_id=group_id,
            scheduled_time=scheduled_time,
            callback=callback,
            enabled=True,
        )

        self._tasks[task_id] = task
        logger.info(f"为 {scheduled_time} 添加了计划任务 {task_id}")

        return task_id

    def remove_task(self, task_id: str) -> bool:
        """
        移除计划任务。

        Args:
            task_id: 任务标识符

        Returns:
            如果任务被移除则返回 True
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"移除了计划任务 {task_id}")
            return True
        return False

    def enable_task(self, task_id: str) -> bool:
        """启用计划任务。"""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._tasks[task_id]._calculate_next_run()
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """禁用计划任务。"""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            self._tasks[task_id].next_run = None
            return True
        return False

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """
        获取计划任务的状态。

        Args:
            task_id: 任务标识符

        Returns:
            任务状态字典或 None
        """
        task = self._tasks.get(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "group_id": task.group_id,
            "scheduled_time": task.scheduled_time,
            "enabled": task.enabled,
            "last_run": task.last_run.isoformat() if task.last_run else None,
            "next_run": task.next_run.isoformat() if task.next_run else None,
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        """列出所有计划任务。"""
        return [self.get_task_status(tid) for tid in self._tasks.keys()]

    async def start(self) -> None:
        """启动调度服务。"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("调度服务已启动")

    async def stop(self) -> None:
        """停止调度服务。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("调度服务已停止")

    async def _run_loop(self) -> None:
        """主调度循环。"""
        while self._running:
            try:
                await self._check_and_run_tasks()
                # 每分钟检查一次
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度循环出错: {e}")
                await asyncio.sleep(60)

    async def _check_and_run_tasks(self) -> None:
        """检查并执行到期任务。"""
        for task in list(self._tasks.values()):
            if task.should_run():
                try:
                    logger.info(f"正在执行计划任务 {task.task_id}")
                    await task.callback(task.group_id)
                    task.mark_completed()
                    logger.info(f"计划任务 {task.task_id} 已完成")
                except Exception as e:
                    logger.error(f"执行任务 {task.task_id} 失败: {e}")

    def setup_from_config(self) -> None:
        """根据配置设置计划任务。"""
        if not self.config.get_auto_analysis_enabled():
            logger.info("自动分析已禁用")
            return

        enabled_groups = self.config.get_enabled_groups()
        analysis_time = self.config.get_analysis_time()

        for group_id in enabled_groups:
            self.add_task(group_id, analysis_time)

        logger.info(f"设置了 {len(enabled_groups)} 个计划任务")
