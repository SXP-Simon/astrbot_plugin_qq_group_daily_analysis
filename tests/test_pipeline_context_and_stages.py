"""
PipelineContext、AnalysisStage 与 Checkpoint 对齐机制单元测试
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from src.application.services.pipeline_context import PipelineContext, PipelineStep
from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.shared.constants import AnalysisStage, TaskStatus
from src.shared.trace_context import TraceContext


def test_analysis_stage_and_task_status_enum_compatibility():
    """验证 AnalysisStage 与 TaskStatus 枚举具备字符串兼容性与规范定义。"""
    assert AnalysisStage.FETCH_MESSAGES == "FETCH_MESSAGES"
    assert AnalysisStage.CLEAN_MESSAGES == "CLEAN_MESSAGES"
    assert AnalysisStage.STATS_ANALYSIS == "STATS_ANALYSIS"
    assert AnalysisStage.LLM_ANALYSIS == "LLM_ANALYSIS"
    assert AnalysisStage.SAVE_SUMMARY == "SAVE_SUMMARY"
    assert AnalysisStage.RENDER_REPORT == "RENDER_REPORT"
    assert AnalysisStage.DISPATCH_REPORT == "DISPATCH_REPORT"
    assert AnalysisStage.CHECKPOINT_RESTORE == "CHECKPOINT_RESTORE"

    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.RUNNING == "running"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.FAILED == "failed"
    assert TaskStatus.ABORTED == "aborted"


@pytest.mark.asyncio
async def test_pipeline_step_context_execution_and_checkpoint_saving(tmp_path: Path):
    """验证 PipelineContext 在 step 执行正常退出时自动持久化 Checkpoint。"""
    db_path = tmp_path / "test_traces.db"
    store = CheckpointStore(db_path)

    with TraceContext(trace_id="trace_pipe_001") as trace:
        pipeline = PipelineContext(
            trace=trace,
            checkpoint_store=store,
            group_id="10001",
            date_str="2026-09-10",
        )

        async with pipeline.step(
            AnalysisStage.CLEAN_MESSAGES,
            initial_payload={"raw_count": 100},
            save_checkpoint=True,
            serializer=lambda x: {"cleaned_messages": x},
        ) as step:
            step.set_payload(cleaned_count=80)
            step.set_output(["msg1", "msg2", "msg3"])

        # 检查 Span 记录
        assert len(trace._spans) == 1
        span = trace._spans[0]
        assert span["stage_name"] == AnalysisStage.CLEAN_MESSAGES.value
        assert span["status"] == "success"
        assert span["payload"]["raw_count"] == 100
        assert span["payload"]["cleaned_count"] == 80
        assert span["payload"]["checkpoint_saved"] is True

        # 检查 CheckpointStore 持久化
        cached = store.get_checkpoint(
            "10001", "2026-09-10", AnalysisStage.CLEAN_MESSAGES.value
        )
        assert cached is not None
        assert cached == {"cleaned_messages": ["msg1", "msg2", "msg3"]}


@pytest.mark.asyncio
async def test_pipeline_step_context_handles_warning_and_failure(tmp_path: Path):
    """验证 PipelineContext 对警告和异常的捕获与状态标记。"""
    db_path = tmp_path / "test_traces.db"
    store = CheckpointStore(db_path)

    with TraceContext(trace_id="trace_pipe_002") as trace:
        pipeline = PipelineContext(
            trace=trace,
            checkpoint_store=store,
            group_id="10002",
            date_str="2026-09-10",
        )

        # 1. 警告阶段
        async with pipeline.step(AnalysisStage.LLM_ANALYSIS) as step:
            step.mark_warning("部分分析子任务超时")

        assert trace._spans[0]["status"] == "warning"
        assert trace._spans[0]["payload"]["warning"] == "部分分析子任务超时"

        # 2. 异常阶段
        with pytest.raises(RuntimeError, match="Network timeout"):
            async with pipeline.step(AnalysisStage.FETCH_MESSAGES) as step:
                raise RuntimeError("Network timeout")

        assert trace._spans[1]["status"] == "failed"
        assert "Network timeout" in trace._spans[1]["payload"]["error"]


def test_checkpoint_store_query_by_group_date(tmp_path: Path):
    """验证 CheckpointStore 按群号和日期查询多阶段快照列表的能力。"""
    db_path = tmp_path / "test_traces.db"
    store = CheckpointStore(db_path)

    group_id = "group_query_test"
    date_str = "2026-09-10"

    store.save_checkpoint(
        group_id, date_str, AnalysisStage.CLEAN_MESSAGES.value, {"clean": True}
    )
    store.save_checkpoint(
        group_id, date_str, AnalysisStage.LLM_ANALYSIS.value, {"llm": True}
    )
    store.save_checkpoint(
        group_id, date_str, "INCREMENTAL_BATCH_a1b2c3d4", {"batch_id": "a1b2c3d4"}
    )

    checkpoints = store.get_checkpoints_by_group_date(group_id, date_str)
    assert len(checkpoints) == 3
    stage_names = [cp["stage_name"] for cp in checkpoints]
    assert AnalysisStage.CLEAN_MESSAGES.value in stage_names
    assert AnalysisStage.LLM_ANALYSIS.value in stage_names
    assert "INCREMENTAL_BATCH_a1b2c3d4" in stage_names
