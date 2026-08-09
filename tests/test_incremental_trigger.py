import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from src.domain.entities.incremental_state import IncrementalBatch
from src.infrastructure.persistence.incremental_store import IncrementalStore
from src.infrastructure.scheduler.auto_scheduler import AutoScheduler
from src.infrastructure.scheduler.incremental_trigger import (
    IncrementalTriggerCoordinator,
)


class FakeConfigManager:
    """提供消息量触发测试所需配置。"""

    def __init__(self, allowed=True):
        self.allowed = allowed

    def get_incremental_enabled(self):
        return True

    def is_group_allowed(self, unified_msg_origin):
        return self.allowed

    def is_group_in_filtered_list(self, unified_msg_origin, mode, group_list):
        return True

    def get_scheduled_group_list_mode(self):
        return "blacklist"

    def get_scheduled_group_list(self):
        return []

    def get_incremental_group_list_mode(self):
        return "blacklist"

    def get_incremental_group_list(self):
        return []

    def get_incremental_min_messages(self):
        return 3

    def get_max_concurrent_tasks(self):
        return 2


class FakePlugin:
    """使用内存字典模拟 AstrBot KV 存储。"""

    def __init__(self):
        self.data = {}

    async def get_kv_data(self, key, default):
        return self.data.get(key, default)

    async def put_kv_data(self, key, value):
        self.data[key] = value


async def wait_for_task_completion(coordinator, state_key):
    """等待指定群的分析任务退出。

    Args:
        coordinator: 增量触发协调器。
        state_key: 群状态键。
    """
    for _ in range(100):
        if state_key not in coordinator._analysis_tasks:
            return
        await asyncio.sleep(0)
    raise AssertionError("增量分析任务未按预期结束")


def test_message_count_threshold_triggers_once_and_consumes_count():
    calls = []

    async def analyze(group_id, platform_id):
        calls.append((group_id, platform_id))
        return {"success": True, "messages_count": 3}

    async def scenario():
        coordinator = IncrementalTriggerCoordinator(
            FakeConfigManager(), FakePlugin(), analyze
        )
        umo = "onebot-main:GroupMessage:123456"
        await coordinator.record_message("onebot-main", "123456", umo, "1")
        await coordinator.record_message("onebot-main", "123456", umo, "2")
        assert calls == []

        await coordinator.record_message("onebot-main", "123456", umo, "3")
        await wait_for_task_completion(coordinator, umo)

        assert calls == [("123456", "onebot-main")]
        assert coordinator._states[umo]["count"] == 0
        await coordinator.close()

    asyncio.run(scenario())


def test_duplicate_event_id_does_not_increase_message_count():
    calls = []

    async def analyze(group_id, platform_id):
        calls.append((group_id, platform_id))
        return {"success": True, "messages_count": 3}

    async def scenario():
        coordinator = IncrementalTriggerCoordinator(
            FakeConfigManager(), FakePlugin(), analyze
        )
        umo = "onebot-main:GroupMessage:123456"
        await coordinator.record_message("onebot-main", "123456", umo, "1")
        await coordinator.record_message("onebot-main", "123456", umo, "1")
        await coordinator.record_message("onebot-main", "123456", umo, "2")
        assert coordinator._states[umo]["count"] == 2
        assert calls == []
        await coordinator.close()

    asyncio.run(scenario())


def test_start_resumes_persisted_count_at_threshold():
    calls = []

    async def analyze(group_id, platform_id):
        calls.append((group_id, platform_id))
        return {"success": True, "messages_count": 3}

    async def scenario():
        plugin = FakePlugin()
        umo = "onebot-main:GroupMessage:123456"
        plugin.data["incremental_trigger_states_v1"] = {
            "states": {
                umo: {
                    "platform_id": "onebot-main",
                    "group_id": "123456",
                    "count": 3,
                }
            }
        }
        coordinator = IncrementalTriggerCoordinator(
            FakeConfigManager(), plugin, analyze
        )

        scheduled = await coordinator.start()
        await wait_for_task_completion(coordinator, umo)

        assert scheduled == 1
        assert calls == [("123456", "onebot-main")]
        await coordinator.close()

    asyncio.run(scenario())


def test_start_does_not_resume_group_removed_from_target_list():
    calls = []

    async def analyze(group_id, platform_id):
        calls.append((group_id, platform_id))
        return {"success": True, "messages_count": 3}

    async def scenario():
        plugin = FakePlugin()
        umo = "onebot-main:GroupMessage:123456"
        plugin.data["incremental_trigger_states_v1"] = {
            "states": {
                umo: {
                    "platform_id": "onebot-main",
                    "group_id": "123456",
                    "count": 3,
                }
            }
        }
        coordinator = IncrementalTriggerCoordinator(
            FakeConfigManager(allowed=False), plugin, analyze
        )

        assert await coordinator.start() == 0
        assert calls == []
        await coordinator.close()

    asyncio.run(scenario())


def test_failed_analysis_keeps_count_and_waits_for_new_message():
    calls = []

    async def analyze(group_id, platform_id):
        calls.append((group_id, platform_id))
        return {"success": False, "reason": "timeout", "messages_count": 0}

    async def scenario():
        coordinator = IncrementalTriggerCoordinator(
            FakeConfigManager(), FakePlugin(), analyze
        )
        umo = "onebot-main:GroupMessage:123456"
        for message_id in ("1", "2", "3"):
            await coordinator.record_message("onebot-main", "123456", umo, message_id)
        await wait_for_task_completion(coordinator, umo)
        await asyncio.sleep(0)

        assert calls == [("123456", "onebot-main")]
        assert coordinator._states[umo]["count"] == 3

        await coordinator.record_message("onebot-main", "123456", umo, "4")
        await wait_for_task_completion(coordinator, umo)

        assert calls == [
            ("123456", "onebot-main"),
            ("123456", "onebot-main"),
        ]
        assert coordinator._states[umo]["count"] == 4
        await coordinator.close()

    asyncio.run(scenario())


def test_message_during_failed_analysis_does_not_immediately_retry():
    calls = []
    started = asyncio.Event()
    release = asyncio.Event()

    async def analyze(group_id, platform_id):
        calls.append((group_id, platform_id))
        started.set()
        await release.wait()
        return {"success": False, "reason": "timeout", "messages_count": 0}

    async def scenario():
        coordinator = IncrementalTriggerCoordinator(
            FakeConfigManager(), FakePlugin(), analyze
        )
        umo = "onebot-main:GroupMessage:123456"
        for message_id in ("1", "2", "3"):
            await coordinator.record_message(
                "onebot-main", "123456", umo, message_id
            )
        await started.wait()

        await coordinator.record_message("onebot-main", "123456", umo, "4")
        release.set()
        await wait_for_task_completion(coordinator, umo)
        await asyncio.sleep(0)

        assert calls == [("123456", "onebot-main")]
        assert coordinator._states[umo]["count"] == 4

        await coordinator.record_message("onebot-main", "123456", umo, "5")
        await wait_for_task_completion(coordinator, umo)
        assert calls == [
            ("123456", "onebot-main"),
            ("123456", "onebot-main"),
        ]
        await coordinator.close()

    asyncio.run(scenario())


def test_burst_messages_are_processed_in_fixed_batches():
    calls = []

    async def analyze(group_id, platform_id):
        calls.append((group_id, platform_id))
        return {"success": True, "messages_count": 3}

    async def scenario():
        coordinator = IncrementalTriggerCoordinator(
            FakeConfigManager(), FakePlugin(), analyze
        )
        umo = "onebot-main:GroupMessage:123456"
        for message_id in ("1", "2", "3", "4", "5", "6"):
            await coordinator.record_message("onebot-main", "123456", umo, message_id)
        await wait_for_task_completion(coordinator, umo)

        assert calls == [
            ("123456", "onebot-main"),
            ("123456", "onebot-main"),
        ]
        assert coordinator._states[umo]["count"] == 0
        await coordinator.close()

    asyncio.run(scenario())


def test_incremental_batch_index_is_idempotent():
    async def scenario():
        plugin = FakePlugin()
        store = IncrementalStore(plugin)
        batch = IncrementalBatch(
            group_id="123456",
            batch_id="stable-batch-id",
            timestamp=100.0,
            messages_count=3,
        )

        assert await store.save_batch(batch)
        batch.timestamp = 101.0
        assert await store.save_batch(batch)

        index = plugin.data["incr_batch_index_123456"]
        assert index == [{"batch_id": "stable-batch-id", "timestamp": 101.0}]

    asyncio.run(scenario())


def test_incremental_cursor_distinguishes_messages_in_same_second():
    async def scenario():
        plugin = FakePlugin()
        store = IncrementalStore(plugin)

        await store.update_last_analyzed_cursor("123456", 100, {"2", "1"})
        timestamp, message_ids = await store.get_last_analyzed_cursor("123456")

        assert timestamp == 100
        assert message_ids == {"1", "2"}
        assert plugin.data["incr_last_ts_123456"] == {
            "timestamp": 100,
            "message_ids": ["1", "2"],
        }

    asyncio.run(scenario())


def test_incremental_cursor_reads_legacy_timestamp():
    async def scenario():
        plugin = FakePlugin()
        plugin.data["incr_last_ts_123456"] = 100
        store = IncrementalStore(plugin)

        assert await store.get_last_analyzed_cursor("123456") == (100, set())

    asyncio.run(scenario())


def test_incremental_schema_has_no_obsolete_batch_settings():
    schema_path = Path(__file__).parents[1] / "_conf_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    incremental_items = schema["incremental"]["items"]
    removed_settings = {
        "incremental_interval_minutes",
        "incremental_max_daily_analyses",
        "incremental_active_start_hour",
        "incremental_active_end_hour",
        "incremental_stagger_seconds",
        "incremental_watchdog_minutes",
        "incremental_counter_flush_seconds",
        "incremental_cooldown_seconds",
        "incremental_safe_limit",
    }

    assert removed_settings.isdisjoint(incremental_items)
    assert "incremental_min_messages" in incremental_items


def test_incremental_mode_only_registers_scheduled_report_jobs():
    scheduler = object.__new__(AutoScheduler)
    scheduler.config_manager = SimpleNamespace(
        is_auto_analysis_enabled=Mock(return_value=True),
        get_incremental_enabled=Mock(return_value=True),
    )
    scheduler.scheduler_job_ids = []
    scheduler._terminating = False
    scheduler.unschedule_jobs = Mock()
    scheduler._schedule_report_time_jobs = Mock()
    cron_scheduler = object()
    context = SimpleNamespace(cron_manager=SimpleNamespace(scheduler=cron_scheduler))

    scheduler.schedule_jobs(context)

    scheduler.unschedule_jobs.assert_called_once_with(context)
    scheduler._schedule_report_time_jobs.assert_called_once_with(cron_scheduler)
