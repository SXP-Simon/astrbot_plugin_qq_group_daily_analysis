"""历史记录的平台身份与跨平台同号群回归。"""

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.infrastructure.webui.routes.report_routes import ReportRoutes


def test_history_filters_platform_before_count_and_pagination(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    folder = tmp_path / "reports"
    folder.mkdir()
    for index, platform in enumerate(("telegram", "discord", "telegram", "")):
        trace_id = f"trace-{index}"
        filename = f"{index}.png"
        store.save_trace({
            "trace_id": trace_id, "group_id": "123", "group_name": f"群-{index}",
            "platform": platform, "started_at": index + 1, "status": "running",
        })
        (folder / filename).write_bytes(b"image")
        store.register_report_artifact(filename, "123", "png", filename, index + 1, trace_id)
    # 无关联任务的旧产物不能继承同群号最新任务的平台。
    (folder / "old.png").write_bytes(b"image")
    store.register_report_artifact("old.png", "123", "png", "old.png", 10)
    rows, total = store.list_traces(platform="telegram", group_id="123", limit=1)
    assert total == 2
    assert rows[0]["trace_id"] == "trace-2"
    assert len(store.get_distinct_groups(by_session=True)) == 3
    assert store.list_traces(platform="")[1] == 1
    routes = ReportRoutes(store, None, report_output_dir=folder)
    reports, total = routes._load_report_history(1, 0, "123", None, platform="telegram")
    assert total == 2
    assert reports[0]["group_name"] == "群-2"
    assert reports[0]["platform"] == "telegram"
    unknown, total = routes._load_report_history(20, 0, None, None, platform="")
    assert total == 2
    assert {r["filename"] for r in unknown} == {"3.png", "old.png"}
    assert all(r["platform"] == "" for r in unknown)
    assert routes._load_report_history(20, 0, None, None, platform="missing") == ([], 0)
