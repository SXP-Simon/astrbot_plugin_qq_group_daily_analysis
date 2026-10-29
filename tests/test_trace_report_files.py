"""任务详情产物归集的旧数据与文件竞争回归。"""

import json
from pathlib import Path

import pytest

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.parametrize(
    "raw_files",
    [None, 7, {}, [None, {"filename": []}, {"filename": ""}]],
)
def test_trace_report_files_ignores_invalid_legacy_records(tmp_path, raw_files):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    store.save_trace({"trace_id": "legacy", "group_id": "123"})
    directory = tmp_path / "reports"
    directory.mkdir()
    (directory / "daily_legacy.png").write_bytes(b"image")
    with store._get_connection() as conn:
        conn.execute(
            "UPDATE analysis_traces SET extra_json = ? WHERE trace_id = ?",
            (json.dumps({"report_files": raw_files}), "legacy"),
        )
    reports = store.get_trace("legacy")["report_files"]
    assert [report["filename"] for report in reports] == ["daily_legacy.png"]


def test_trace_report_files_sorts_legacy_timestamps_and_deduplicates(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    reports = store._collect_report_files(
        "legacy",
        [
            {"filename": "old.png", "created_at": None},
            {"filename": "new.png", "created_at": 10},
            {"filename": "new.png", "created_at": 5},
        ],
    )
    assert [item["filename"] for item in reports] == ["new.png", "old.png"]
    assert reports[-1]["created_at"] == 0


def test_trace_report_scan_continues_when_one_file_disappears(tmp_path, monkeypatch):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    directory = tmp_path / "reports"
    directory.mkdir()
    missing, valid = directory / "gone_legacy.png", directory / "ok_legacy.html"
    valid.write_text("<html></html>", encoding="utf-8")
    real_stat = Path.stat

    def stat(path, *args, **kwargs):
        if path == missing:
            raise PermissionError("模拟扫描期间文件不可读")
        return real_stat(path, *args, **kwargs)

    real_iterdir = Path.iterdir
    monkeypatch.setattr(
        Path, "iterdir", lambda path: iter([missing, valid]) if path == directory else real_iterdir(path)
    )
    monkeypatch.setattr(Path, "stat", stat)
    reports = store._collect_report_files("legacy", [])
    assert [item["filename"] for item in reports] == [valid.name]
