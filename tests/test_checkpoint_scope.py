"""检查点回退查询的群组和日期隔离回归测试。"""

import pytest

from src.infrastructure.persistence.checkpoint_store import CheckpointStore


@pytest.mark.parametrize(
    "group_id,date_str", [("other", "2026-10-29"), ("123", "2026-10-28")]
)
def test_trace_fallback_rejects_other_group_or_date(tmp_path, group_id, date_str):
    store = CheckpointStore(tmp_path / "checkpoints.db")
    store.save_checkpoint(
        "123",
        "2026-10-29",
        "LLM_ANALYSIS",
        {"result": "private"},
        trace_id="same-trace",
    )
    assert (
        store.get_checkpoint(group_id, date_str, "LLM_ANALYSIS", trace_id="same-trace")
        is None
    )
    assert store.get_checkpoint(
        "123", "2026-10-29", "LLM_ANALYSIS", trace_id="same-trace"
    ) == {"result": "private"}

@pytest.mark.parametrize("method", ["get_checkpoint_detail", "delete_checkpoint"])
def test_explicit_task_never_falls_back_to_legacy_record(tmp_path, method):
    """查询或删除不存在的任务时，不得借用同群旧记录。"""
    store = CheckpointStore(tmp_path / "checkpoints.db")
    store.save_checkpoint("123", "2026-11-07", "LLM_ANALYSIS", {"old": True})
    result = getattr(store, method)("123", "2026-11-07", "LLM_ANALYSIS", "missing-task")
    assert not result
    assert store.get_checkpoint("123", "2026-11-07", "LLM_ANALYSIS") == {"old": True}


@pytest.mark.parametrize("group_id,date_str", [("other", "2026-11-07"), ("123", "2026-11-06")])
def test_detail_rejects_trace_from_other_group_or_date(tmp_path, group_id, date_str):
    """详情查询与正文查询采用相同的任务、群号和日期约束。"""
    store = CheckpointStore(tmp_path / "checkpoints.db")
    store.save_checkpoint("123", "2026-11-07", "LLM_ANALYSIS", {"private": True}, trace_id="task-one")
    assert store.get_checkpoint_detail(group_id, date_str, "LLM_ANALYSIS", "task-one") is None
    assert store.get_checkpoint_detail("123", "2026-11-07", "LLM_ANALYSIS", "task-one")["data"] == {"private": True}
