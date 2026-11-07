import pytest

from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.persistence.trace_sqlite_store import (
    TraceSQLiteStore,
)
from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.routes.report_routes import (
    ReportRoutes,
)


def save(store, number, started=100):
    store.save_trace(
        {
            "trace_id": f"t{number:05}",
            "group_id": "group",
            "started_at": started,
            "status": "running",
        }
    )


def test_report_global_dates_sort_missing_file_and_redraw(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    folder = tmp_path / "reports"
    folder.mkdir()
    for number in range(6):
        name = f"report_{number}.png"
        (folder / name).write_bytes(b"image")
        store.register_report_artifact(
            name, "group", "png", name, number, f"trace{number}"
        )
    routes = ReportRoutes(store, None, report_output_dir=folder)
    (folder / "report_1.png").unlink()
    first, total = routes._load_report_history(2, 0, None, None, 1, 4, "asc")
    second, same_total = routes._load_report_history(2, 2, None, None, 1, 4, "asc")
    assert total == same_total == 3
    assert [r["filename"] for r in first + second] == [
        "report_2.png",
        "report_3.png",
        "report_4.png",
    ]
    assert store.count_report_artifacts() == 5
    # 相同文件重绘后按新生成时间进入全局排序，旧快照清理不能删除新登记。
    store.register_report_artifact(
        "report_2.png", "group", "png", "report_2.png", 20, "redraw"
    )
    store.delete_missing_report_artifacts([("report_2.png", "report_2.png", 2)])
    latest, total = routes._load_report_history(1, 0, None, None)
    assert total == 5
    assert latest[0]["trace_id"] == "redraw"


def test_empty_filtered_history_does_not_repeat_directory_scan(tmp_path, monkeypatch):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    folder = tmp_path / "reports"
    folder.mkdir()
    routes = ReportRoutes(store, None, report_output_dir=folder)
    calls = []
    original = routes._scan_report_history

    def scan(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(routes, "_scan_report_history", scan)
    for _ in range(3):
        assert routes._load_report_history(20, 0, None, "no-result") == ([], 0)
    assert len(calls) == 1


def test_report_metadata_update_between_read_and_validation_keeps_response_consistent(
    tmp_path, monkeypatch
):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    folder = tmp_path / "reports"
    folder.mkdir()
    for i in range(2):
        (folder / f"r{i}.png").write_bytes(b"image")
        store.register_report_artifact(f"r{i}.png", "g", "png", f"r{i}.png", i)
    routes = ReportRoutes(store, None, report_output_dir=folder)
    original = routes._read_indexed_reports

    def insert_after_read(*args):
        (folder / "new.png").write_bytes(b"new")
        store.register_report_artifact("new.png", "g", "png", "new.png", 20)
        return original(*args)

    monkeypatch.setattr(routes, "_read_indexed_reports", insert_after_read)
    items, total = routes._load_report_history(100, 0, None, None)
    assert len(items) == total == 2
    assert store.count_report_artifacts() == 3


@pytest.mark.asyncio
async def test_trace_cursor_route_overfetch_and_validation(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.webui.routes import (
        trace_routes,
    )

    store = TraceSQLiteStore(tmp_path / "trace.db")
    for i in range(6):
        save(store, i)
    routes = trace_routes.TraceRoutes(None, store, None)
    monkeypatch.setattr(trace_routes, "request", MagicMock(query={"limit": "3"}))
    result = await routes.api_list_traces()
    body = (
        result.get("data")
        if isinstance(result.get("data"), dict) and "status" in result["data"]
        else result
    )
    assert body["data"]["has_more"] is True
    assert len(body["data"]["items"]) == 3
    monkeypatch.setattr(
        trace_routes,
        "request",
        MagicMock(query={"limit": "3", "before_time": "100", "before_id": "t00003"}),
    )
    result = await routes.api_list_traces()
    body = (
        result.get("data")
        if isinstance(result.get("data"), dict) and "status" in result["data"]
        else result
    )
    assert body["data"]["has_more"] is False
    assert body["data"]["items"][0]["trace_id"] == "t00002"
    for query in (
        {"before_time": "nan", "before_id": "id"},
        {"before_time": "1"},
        {"before_time": "1", "before_id": "id", "offset": "1"},
    ):
        monkeypatch.setattr(trace_routes, "request", MagicMock(query=query))
        result = await routes.api_list_traces()
        assert result.get("status_code") == 400


def test_offline_report_directory_does_not_delete_its_index(tmp_path):
    from unittest.mock import MagicMock

    store = TraceSQLiteStore(tmp_path / "trace.db")
    folder = tmp_path / "reports"
    folder.mkdir()
    offline = tmp_path / "offline-html"
    store.register_report_artifact("r.html", "g", "html", "r.html", 1)
    service = MagicMock()
    service.config_manager.get_html_output_dir.return_value = str(offline)
    routes = ReportRoutes(store, service, report_output_dir=folder)
    assert routes._load_report_history(20, 0, None, None) == ([], 0)
    assert store.count_report_artifacts() == 1
    offline.mkdir()
    (offline / "r.html").write_text("report")
    assert routes._load_report_history(20, 0, None, None)[1] == 1
