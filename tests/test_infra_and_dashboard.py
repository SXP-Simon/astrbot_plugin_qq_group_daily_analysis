"""
单元测试与自测用例：TraceSQLiteStore, CheckpointStore, TraceContext, ActiveTaskManager, WebUIBridge
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest

from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.active_task_manager import ActiveTaskManager
from src.shared.trace_context import TraceContext

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


@pytest.fixture
def temp_db(tmp_path: Path):
    return tmp_path / "test_traces.db"


def test_trace_sqlite_store_crud_and_metrics(temp_db: Path):
    store = TraceSQLiteStore(temp_db)

    # 1. 插入一条完整 Trace
    trace_data = {
        "trace_id": "test_trace_001",
        "group_id": "123456",
        "group_name": "测试群A",
        "platform": "qq",
        "trigger_type": "manual",
        "status": "succeeded",
        "started_at": time.time() - 10,
        "completed_at": time.time(),
        "duration_ms": 10000.0,
        "spans": [
            {
                "span_id": "test_trace_001_FETCH",
                "stage_name": "FETCH_MESSAGES",
                "status": "success",
                "started_at": time.time() - 10,
                "duration_ms": 1500.0,
                "payload": {"msg_count": 2000},
            },
            {
                "span_id": "test_trace_001_TOPICS",
                "stage_name": "LLM_TOPICS",
                "status": "success",
                "started_at": time.time() - 8.5,
                "duration_ms": 4000.0,
            },
        ],
        "context_metrics": {
            "raw_message_count": 2000,
            "cleaned_message_count": 1200,
            "compression_ratio": 0.6,
            "incremental_batches": 2,
        },
        "token_usage": {
            "prompt_tokens": 5000,
            "completion_tokens": 1200,
            "total_tokens": 6200,
            "estimated_cost": 0.008,
            "per_analyzer": {"topics": {"total_tokens": 3000}},
        },
    }

    store.save_trace(trace_data)

    # 2. 读取并验证
    retrieved = store.get_trace("test_trace_001")
    assert retrieved is not None
    assert retrieved["trace_id"] == "test_trace_001"
    assert retrieved["group_name"] == "测试群A"
    assert retrieved["status"] == "succeeded"
    assert len(retrieved["spans"]) == 2
    assert retrieved["context_metrics"]["raw_message_count"] == 2000
    assert retrieved["context_metrics"]["compression_ratio"] == 0.6
    assert retrieved["token_usage"]["total_tokens"] == 6200

    # 3. 列表分页查询、时间范围与搜索
    items, total = store.list_traces(
        limit=10,
        search="测试群A",
        start_time=time.time() - 3600,
        end_time=time.time() + 3600,
        sort_by="started_at",
        sort_order="desc",
    )
    assert total == 1
    assert items[0]["trace_id"] == "test_trace_001"
    assert items[0]["total_tokens"] == 6200

    # 3.1 查询群组列表
    groups = store.get_distinct_groups()
    assert len(groups) == 1
    assert groups[0]["group_id"] == "123456"

    # 4. KPI 概览统计
    metrics = store.get_metrics_summary()
    assert metrics["total_traces"] == 1
    assert metrics["succeeded_count"] == 1
    assert metrics["failed_count"] == 0
    assert metrics["total_tokens_spent"] == 6200
    assert metrics["success_rate"] == 100.0


def test_trace_startup_crash_reconciliation(temp_db: Path):
    store = TraceSQLiteStore(temp_db)

    # 插入一条处于 running 状态的未完成任务（模拟进程掉电）
    store.save_trace(
        {
            "trace_id": "crashed_job_001",
            "group_id": "777",
            "group_name": "崩溃群",
            "status": "running",
            "started_at": time.time() - 100,
        }
    )

    # 开机自愈对账扫描
    reconciled = store.reconcile_crashed_traces_on_startup()
    assert reconciled == 1

    # 校验已被自动修正为 aborted，并带上崩溃自愈元数据
    trace = store.get_trace("crashed_job_001")
    assert trace is not None
    assert trace["status"] == "aborted"
    assert trace["error_stage"] == "CRASH_RECOVERY"
    assert "开机已自动回收" in trace["error_message"]


def test_checkpoint_store(temp_db: Path):
    store = CheckpointStore(temp_db)

    # 1. 保存阶段产物
    topics_data = {"topics": ["AI开发", "Python3.12"]}
    store.save_checkpoint("group_101", "2026-08-25", "topics", topics_data)

    # 2. 读取
    cached = store.get_checkpoint("group_101", "2026-08-25", "topics")
    assert cached == topics_data

    # 3. 未命中
    assert store.get_checkpoint("group_101", "2026-08-25", "quotes") is None

    # 4. 清理
    store.clear_checkpoints("group_101", "2026-08-25")
    assert store.get_checkpoint("group_101", "2026-08-25", "topics") is None


def test_trace_context_spans_and_auto_persistence(temp_db: Path):
    store = TraceSQLiteStore(temp_db)
    TraceContext.set_global_store(store)

    ctx = TraceContext(
        trace_id="auto_save_001",
        group_id="88888",
        group_name="自动保存群",
        platform="telegram",
    )

    with ctx:
        with ctx.span("FETCH_STAGE", {"count": 100}):
            time.sleep(0.01)

        ctx.set_context_metrics(raw_message_count=500, cleaned_message_count=250)
        ctx.add_token_usage(
            prompt_tokens=1000, completion_tokens=200, analyzer_name="topics"
        )

    # 退出上下文后应自动调用 finish 并持久化入库
    saved = store.get_trace("auto_save_001")
    assert saved is not None
    assert saved["status"] == "succeeded"
    assert len(saved["spans"]) == 1
    assert saved["spans"][0]["stage_name"] == "FETCH_STAGE"
    assert saved["context_metrics"]["compression_ratio"] == 0.5
    assert saved["token_usage"]["total_tokens"] == 1200


@pytest.mark.asyncio
async def test_active_task_manager_and_reaper(temp_db: Path):
    store = TraceSQLiteStore(temp_db)
    manager = ActiveTaskManager(trace_store=store)

    # 1. 注册任务
    async def dummy_job():
        await asyncio.sleep(5)

    task_coro = asyncio.create_task(dummy_job())
    await manager.register_task(
        task_id="active_001",
        group_id="999",
        group_name="活跃群",
        current_stage="FETCH_MESSAGES",
        asyncio_task=task_coro,
    )

    active = manager.get_active_tasks()
    assert len(active) == 1
    assert active[0]["task_id"] == "active_001"
    assert active[0]["current_stage"] == "FETCH_MESSAGES"

    # 2. 更新进度
    await manager.update_stage("active_001", "LLM_ANALYSIS")
    active_updated = manager.get_active_tasks()
    assert active_updated[0]["current_stage"] == "LLM_ANALYSIS"

    # 3. 取消
    canceled = await manager.cancel_task("active_001")
    assert canceled is True
    assert len(manager.get_active_tasks()) == 0
    await asyncio.sleep(0.01)
    assert task_coro.cancelled()

    # 检查数据库状态被标记为 aborted
    aborted_trace = store.get_trace("active_001")
    assert aborted_trace is not None
    assert aborted_trace["status"] == "aborted"
