"""追踪快照合并应保留历史诊断，并按文件名合并有效产物。"""

import pytest

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.parametrize("replace_prompts", [True, False])
def test_trace_merge_preserves_diagnostics_and_artifact_order(tmp_path, replace_prompts):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    store.save_trace({"trace_id": "trace", "group_id": "123", "extra": {
        "report_files": [{"filename": "old.png", "path": "original"}],
        "llm_prompts": {"topics": "old prompt"}, "llm_attempts": [{"attempt": 1}],
    }})
    metadata = {"report_files": [None, {}, {"filename": "old.png", "path": "ignored"}, {"filename": "new.html"}]}
    if replace_prompts:
        metadata["llm_prompts"] = {"topics": "new prompt"}
    store.save_trace({"trace_id": "trace", "group_id": "123", "metadata": metadata})
    detail = store.get_trace("trace")
    assert detail["extra"]["report_files"] == [{"filename": "old.png", "path": "original"}, {"filename": "new.html"}]
    assert detail["extra"]["llm_attempts"] == [{"attempt": 1}]
    assert detail["extra"]["llm_prompts"]["topics"] == ("new prompt" if replace_prompts else "old prompt")
    assert set(store.get_report_trace_map()) == {"old.png", "new.html"}


def test_trace_metadata_keeps_existing_scalar_and_merges_containers(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    store.save_trace({
        "trace_id": "trace", "group_id": "123",
        "extra": {"scalar": "保留值", "nested": {"old": 1}, "items": [1]},
        "metadata": {"scalar": "新值", "nested": {"new": 2}, "items": [2], "added": "新增"},
    })
    extra = store.get_trace("trace")["extra"]
    assert extra["scalar"] == "保留值"
    assert extra["nested"] == {"old": 1, "new": 2}
    assert extra["items"] == [2]
    assert extra["added"] == "新增"
