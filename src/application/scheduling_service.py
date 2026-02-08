"""
Scheduling Service - Application service for scheduled analysis

This service manages scheduled analysis tasks and coordinates
with the analysis orchestrator.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from astrbot.api import logger

from ..infrastructure.config import ConfigManager
from ..shared.constants import TASK_STATE_PENDING, TASK_STATE_RUNNING, TASK_STATE_COMPLETED


class ScheduledTask:
    """Represents a scheduled analysis task."""

    def __init__(
        self,
        task_id: str,
        group_id: str,
        scheduled_time: str,  # HH:MM format
        callback: Callable,
        enabled: bool = True,
    ):
        self.task_id = task_id
        self.group_id = group_id
        self.scheduled_time = scheduled_time
        self.callback = callback
        self.enabled = enabled
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self._calculate_next_run()

    def _calculate_next_run(self) -> None:
        """Calculate the next run time."""
        if not self.enabled:
            self.next_run = None
            return

        try:
            hours, minutes = map(int, self.scheduled_time.split(":"))
            now = datetime.now()
            next_run = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            # If the time has passed today, schedule for tomorrow
            if next_run <= now:
                next_run += timedelta(days=1)

            self.next_run = next_run
        except ValueError:
            logger.error(f"Invalid scheduled time format: {self.scheduled_time}")
            self.next_run = None

    def should_run(self) -> bool:
        """Check if the task should run now."""
        if not self.enabled or not self.next_run:
            return False

        now = datetime.now()

        # Check if we're within the execution window (5 minute tolerance)
        if self.next_run <= now <= self.next_run + timedelta(minutes=5):
            # Check if we haven't run today
            if self.last_run is None or self.last_run.date() != now.date():
                return True

        return False

    def mark_completed(self) -> None:
        """Mark the task as completed and schedule next run."""
        self.last_run = datetime.now()
        self._calculate_next_run()


class SchedulingService:
    """
    Application service for managing scheduled analysis tasks.

    This service runs a background loop that checks for and
    executes scheduled tasks.
    """

    def __init__(self, config: ConfigManager):
        """
        Initialize the scheduling service.

        Args:
            config: Configuration manager
        """
        self.config = config
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, Callable] = {}

    def register_callback(self, name: str, callback: Callable) -> None:
        """
        Register a callback for scheduled tasks.

        Args:
            name: Callback name
            callback: Async callback function
        """
        self._callbacks[name] = callback

    def add_task(
        self,
        group_id: str,
        scheduled_time: Optional[str] = None,
        callback_name: str = "analyze",
    ) -> str:
        """
        Add a scheduled task for a group.

        Args:
            group_id: Group identifier
            scheduled_time: Time in HH:MM format (uses config default if not provided)
            callback_name: Name of registered callback to use

        Returns:
            Task ID
        """
        scheduled_time = scheduled_time or self.config.get_analysis_time()
        task_id = f"task_{group_id}"

        callback = self._callbacks.get(callback_name)
        if not callback:
            logger.warning(f"Callback '{callback_name}' not registered")
            return task_id

        task = ScheduledTask(
            task_id=task_id,
            group_id=group_id,
            scheduled_time=scheduled_time,
            callback=callback,
            enabled=True,
        )

        self._tasks[task_id] = task
        logger.info(f"Added scheduled task {task_id} for {scheduled_time}")

        return task_id

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a scheduled task.

        Args:
            task_id: Task identifier

        Returns:
            True if task was removed
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info(f"Removed scheduled task {task_id}")
            return True
        return False

    def enable_task(self, task_id: str) -> bool:
        """Enable a scheduled task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = True
            self._tasks[task_id]._calculate_next_run()
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """Disable a scheduled task."""
        if task_id in self._tasks:
            self._tasks[task_id].enabled = False
            self._tasks[task_id].next_run = None
            return True
        return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a scheduled task.

        Args:
            task_id: Task identifier

        Returns:
            Task status dictionary or None
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

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all scheduled tasks."""
        return [self.get_task_status(tid) for tid in self._tasks.keys()]

    async def start(self) -> None:
        """Start the scheduling service."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduling service started")

    async def stop(self) -> None:
        """Stop the scheduling service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduling service stopped")

    async def _run_loop(self) -> None:
        """Main scheduling loop."""
        while self._running:
            try:
                await self._check_and_run_tasks()
                # Check every minute
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduling loop: {e}")
                await asyncio.sleep(60)

    async def _check_and_run_tasks(self) -> None:
        """Check for and execute due tasks."""
        for task in list(self._tasks.values()):
            if task.should_run():
                try:
                    logger.info(f"Executing scheduled task {task.task_id}")
                    await task.callback(task.group_id)
                    task.mark_completed()
                    logger.info(f"Completed scheduled task {task.task_id}")
                except Exception as e:
                    logger.error(f"Failed to execute task {task.task_id}: {e}")

    def setup_from_config(self) -> None:
        """Set up scheduled tasks from configuration."""
        if not self.config.get_auto_analysis_enabled():
            logger.info("Auto analysis is disabled")
            return

        enabled_groups = self.config.get_enabled_groups()
        analysis_time = self.config.get_analysis_time()

        for group_id in enabled_groups:
            self.add_task(group_id, analysis_time)

        logger.info(f"Set up {len(enabled_groups)} scheduled tasks")
