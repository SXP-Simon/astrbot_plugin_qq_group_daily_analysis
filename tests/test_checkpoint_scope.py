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
