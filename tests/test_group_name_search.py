"""群名搜索按平台会话去重的回归测试。"""

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.shared.trace_context import TraceContext


def test_group_name_search_preserves_platforms_and_normalizes_missing_platform(
    tmp_path,
):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    for index, (platform, name) in enumerate(
        [
            ("official-a", "读书旧名"),
            ("official-b", "读书 B"),
            ("official-a", "读书 A"),
            (None, "读书未知旧名"),
            ("", "读书未知新名"),
        ]
    ):
        snapshot = TraceContext(
            trace_id=f"trace-{index}",
            group_id="SAME",
            group_name=name,
            platform=platform or "",
            started_at=index + 1,
        ).to_dict()
        store.save_trace(snapshot)
    # 模拟旧数据库中的 SQL NULL，与现代配置的空字符串属于同一未知平台。
    with store._get_connection() as connection:
        connection.execute(
            "UPDATE analysis_traces SET platform = NULL WHERE trace_id = ?", ("trace-3",)
        )

    groups = store.find_groups_by_name("读书")
    assert [(group["platform"], group["group_name"]) for group in groups] == [
        ("", "读书未知新名"),
        ("official-a", "读书 A"),
        ("official-b", "读书 B"),
    ]
    assert all(group["group_id"] == "SAME" for group in groups)
    assert store.find_groups_by_name("读书", limit=2) == groups[:2]
    assert store.find_groups_by_name("不存在") == []
    assert store.find_groups_by_name(" ") == []
