"""快照修订不改变身份和生命周期。"""

from src.infrastructure.persistence.checkpoint_store import CheckpointStore


def test_replace_preserves_metadata_and_rejects_stale_data(tmp_path):
    store = CheckpointStore(tmp_path / "traces.db")
    store.save_checkpoint(
        "onebot:123", "2026-11-03", "LLM_ANALYSIS", {"topics": []}, trace_id="trace-one"
    )
    before = store.get_checkpoint_detail(
        "onebot:123", "2026-11-03", "LLM_ANALYSIS", "trace-one"
    )
    assert before
    assert not store.replace_checkpoint_data("nonexistent", {"topics": []}, {})
    assert store.replace_checkpoint_data(
        before["checkpoint_id"], {"topics": []}, {"topics": [{"topic": "updated"}]}
    )
    assert not store.replace_checkpoint_data(
        before["checkpoint_id"], {"topics": []}, {}
    )
    after = store.get_checkpoint_detail(
        "onebot:123", "2026-11-03", "LLM_ANALYSIS", "trace-one"
    )
    assert after
    for key in (
        "checkpoint_id",
        "created_at",
        "expire_at",
        "group_id",
        "date_str",
        "trace_id",
        "stage_name",
    ):
        assert after[key] == before[key]
    assert after["data"]["topics"][0]["topic"] == "updated"
