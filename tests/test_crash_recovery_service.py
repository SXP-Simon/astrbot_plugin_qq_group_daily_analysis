"""
Unit tests for CrashRecoveryService (Startup crash reconciliation and dispatch staleness policy).
"""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.crash_recovery_service import (
    CrashRecoveryService,
)
from src.shared.constants import (
    AnalysisStage,
    TaskStatus,
)


@pytest.fixture
def mock_trace_store():
    store = MagicMock()
    store.get_crashed_traces_on_startup.return_value = []
    return store


@pytest.fixture
def mock_checkpoint_store():
    store = MagicMock()
    store.get_checkpoint.return_value = None
    return store


@pytest.fixture
def mock_analysis_service():
    service = MagicMock()
    service.resume_analysis = AsyncMock()
    return service


@pytest.fixture
def mock_dispatcher():
    dispatcher = MagicMock()
    dispatcher.dispatch = AsyncMock(return_value=True)
    return dispatcher


@pytest.mark.asyncio
async def test_recover_crashed_tasks_empty(
    mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
):
    service = CrashRecoveryService(
        mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
    )
    result = await service.recover_crashed_tasks()
    assert result == {"recovered": 0, "archived": 0, "aborted": 0}


@pytest.mark.asyncio
async def test_recover_crashed_tasks_same_day_dispatches(
    mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
):
    today = dt.datetime.now()
    started_at = today.timestamp()
    today_str = today.strftime("%Y-%m-%d")

    mock_trace_store.get_crashed_traces_on_startup.return_value = [
        {
            "trace_id": "trace_today_1",
            "group_id": "123456",
            "platform": "aiocqhttp",
            "trigger_type": "auto",
            "started_at": started_at,
        }
    ]

    mock_checkpoint_store.get_checkpoint.side_effect = lambda g, d, stage, **kwargs: (
        {"statistics": {}, "unified_messages": []}
        if stage == AnalysisStage.CLEAN_MESSAGES.value
        else None
    )

    mock_analysis_service.resume_analysis.return_value = {
        "success": True,
        "analysis_result": {"statistics": MagicMock(), "topics": []},
        "platform_id": "aiocqhttp",
    }

    service = CrashRecoveryService(
        mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
    )
    result = await service.recover_crashed_tasks()

    assert result == {"recovered": 1, "archived": 0, "aborted": 0}
    mock_analysis_service.resume_analysis.assert_awaited_once_with(
        trace_id="trace_today_1",
        group_id="123456",
        platform_id="aiocqhttp",
        date_str=today_str,
    )
    mock_dispatcher.dispatch.assert_awaited_once_with(
        "123456",
        {
            "statistics": mock_analysis_service.resume_analysis.return_value[
                "analysis_result"
            ]["statistics"],
            "topics": [],
        },
        "aiocqhttp",
    )


@pytest.mark.asyncio
async def test_recover_crashed_tasks_cross_day_silently_archives(
    mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
):
    yesterday = dt.datetime.now() - dt.timedelta(days=1)
    started_at = yesterday.timestamp()
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    mock_trace_store.get_crashed_traces_on_startup.return_value = [
        {
            "trace_id": "trace_yesterday_1",
            "group_id": "123456",
            "platform": "aiocqhttp",
            "trigger_type": "auto",
            "started_at": started_at,
        }
    ]

    mock_checkpoint_store.get_checkpoint.side_effect = lambda g, d, stage, **kwargs: (
        {"statistics": {}, "unified_messages": []}
        if stage == AnalysisStage.CLEAN_MESSAGES.value
        else None
    )

    mock_analysis_service.resume_analysis.return_value = {
        "success": True,
        "analysis_result": {"statistics": MagicMock(), "topics": []},
        "platform_id": "aiocqhttp",
    }

    service = CrashRecoveryService(
        mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
    )
    result = await service.recover_crashed_tasks()

    assert result == {"recovered": 0, "archived": 1, "aborted": 0}
    mock_analysis_service.resume_analysis.assert_awaited_once_with(
        trace_id="trace_yesterday_1",
        group_id="123456",
        platform_id="aiocqhttp",
        date_str=yesterday_str,
    )
    # Cross-day task must NOT dispatch to the group
    mock_dispatcher.dispatch.assert_not_called()


@pytest.mark.asyncio
async def test_recover_crashed_tasks_no_checkpoint_aborted(
    mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
):
    mock_trace_store.get_crashed_traces_on_startup.return_value = [
        {
            "trace_id": "trace_no_cp",
            "group_id": "999888",
            "platform": "aiocqhttp",
            "trigger_type": "manual",
            "started_at": dt.datetime.now().timestamp(),
        }
    ]

    mock_checkpoint_store.get_checkpoint.return_value = None

    service = CrashRecoveryService(
        mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
    )
    result = await service.recover_crashed_tasks()

    assert result == {"recovered": 0, "archived": 0, "aborted": 1}
    mock_analysis_service.resume_analysis.assert_not_called()
    mock_dispatcher.dispatch.assert_not_called()
    mock_trace_store.save_trace.assert_called_once()
    saved_payload = mock_trace_store.save_trace.call_args[0][0]
    assert saved_payload["trace_id"] == "trace_no_cp"
    assert saved_payload["status"] == TaskStatus.ABORTED.value


@pytest.mark.asyncio
async def test_recover_crashed_tasks_passes_current_boot_id(
    mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
):
    """验证 recover_crashed_tasks 会将当前 PROCESS_BOOT_ID 传递给 trace_store 进行过滤。"""
    service = CrashRecoveryService(
        mock_trace_store, mock_checkpoint_store, mock_analysis_service, mock_dispatcher
    )
    custom_boot_id = "test_pid_1234:boot_uuid_999"
    await service.recover_crashed_tasks(current_boot_id=custom_boot_id)

    mock_trace_store.get_crashed_traces_on_startup.assert_called_once_with(
        current_boot_id=custom_boot_id
    )


def test_sqlite_store_boot_id_filtering_and_migration(tmp_path):
    """集成验证 SQLite 仓储中的 pid / boot_id 持久化、自动增量迁移以及开机对账过滤。"""
    from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
    from src.shared.constants import PROCESS_BOOT_ID, PROCESS_PID

    db_file = tmp_path / "test_trace.db"
    store = TraceSQLiteStore(db_file)

    current_boot = PROCESS_BOOT_ID
    dead_boot = "99999:dead_uuid_0000:100000"

    # 1. 插入一条属于当前进程（热重载中）的 running 任务
    store.save_trace(
        {
            "trace_id": "hot_reload_task_1",
            "group_id": "111",
            "status": "running",
            "pid": PROCESS_PID,
            "boot_id": current_boot,
        }
    )

    # 2. 插入一条属于已死亡历史进程的 running 任务
    store.save_trace(
        {
            "trace_id": "dead_process_task_2",
            "group_id": "222",
            "status": "running",
            "pid": 99999,
            "boot_id": dead_boot,
        }
    )

    # 3. 验证 get_crashed_traces_on_startup(current_boot_id=current_boot)
    #    应精准过滤掉 hot_reload_task_1，只返回 dead_process_task_2！
    crashed = store.get_crashed_traces_on_startup(current_boot_id=current_boot)
    assert len(crashed) == 1
    assert crashed[0]["trace_id"] == "dead_process_task_2"
    assert crashed[0]["pid"] == 99999
    assert crashed[0]["boot_id"] == dead_boot

    # 4. 验证 reconcile_crashed_traces_on_startup(current_boot_id=current_boot)
    #    仅将 dead_process_task_2 标记为 aborted，绝不篡改 hot_reload_task_1！
    reconciled = store.reconcile_crashed_traces_on_startup(current_boot_id=current_boot)
    assert reconciled == 1

    # 5. 验证数据库中两者的最终状态
    trace_hot = store.get_trace("hot_reload_task_1")
    trace_dead = store.get_trace("dead_process_task_2")

    assert trace_hot is not None
    assert trace_hot["status"] == "running"  # 保持 running，旧协程可正常跑完发图！

    assert trace_dead is not None
    assert trace_dead["status"] == "aborted"  # 死亡进程任务被正确回收

