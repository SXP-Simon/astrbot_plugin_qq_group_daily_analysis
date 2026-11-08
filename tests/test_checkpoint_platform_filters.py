"""快照平台来源与分页计数回归。"""

from src.infrastructure.persistence.checkpoint_store import CheckpointStore
from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


def test_checkpoint_platform_uses_its_trace_not_latest_group(tmp_path):
    database = tmp_path / "state.db"
    traces = TraceSQLiteStore(database)
    store = CheckpointStore(database)
    for number, platform in enumerate(("telegram", "discord", "telegram")):
        trace_id = f"t{number}"
        traces.save_trace({"trace_id": trace_id, "group_id": "123", "platform": platform,
                           "group_name": f"{platform} 示例群", "status": "running"})
        store.save_checkpoint("123", "2026-11-07", "LLM_ANALYSIS", {}, trace_id)
    store.save_checkpoint("123", "2026-11-07", "LLM_ANALYSIS", {})
    rows, total = store.list_all_checkpoints(group_id="123", platform="telegram", limit=1)
    assert total == 2 and len(rows) == 1
    assert rows[0]["platform"] == "telegram"
    assert rows[0]["group_name"] == "telegram 示例群"
    assert store.list_all_checkpoints(platform="")[1] == 1
    assert store.list_all_checkpoints(platform="missing") == ([], 0)
    assert {g["platform"] for g in store.get_checkpoint_group_sessions()} == {"", "telegram", "discord"}


def test_standalone_checkpoint_store_keeps_unknown_identity(tmp_path):
    store = CheckpointStore(tmp_path / "standalone.db")
    store.save_checkpoint("old", "2026-11-07", "LLM_ANALYSIS", {"text": "旧数据"}, "missing-trace")
    items, total = store.list_all_checkpoints(platform="")
    assert total == 1 and items[0]["platform"] == ""
    assert store.get_checkpoint_group_sessions() == [{"group_id": "old", "group_name": "", "platform": ""}]
    assert store.list_all_checkpoints(platform="telegram") == ([], 0)
