"""任务详情产物归集的旧数据与文件竞争回归。"""

import json
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.parametrize("suffix", ["png", "html"])
@pytest.mark.parametrize("recorded", [False, True])
def test_legacy_trace_finds_clean_filename_without_changing_database_key(
    tmp_path, suffix, recorded
):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    original_trace = "legacy_\x11日常\x10交流群\x7f_end"
    filename = f"report_123_legacy_日常交流群_end.{suffix}"
    snapshot = {"trace_id": original_trace, "group_id": "123"}
    if recorded:
        snapshot["metadata"] = {"report_files": [{"filename": filename}]}
    store.save_trace(snapshot)
    directory = tmp_path / "reports"
    directory.mkdir()
    (directory / filename).write_bytes(b"report")
    (directory / "unrelated.png").write_bytes(b"other")

    trace = store.get_trace(original_trace)
    assert trace["trace_id"] == original_trace
    assert [report["filename"] for report in trace["report_files"]] == [filename]
    assert store.get_trace("legacy_日常交流群_end") is None


@pytest.mark.parametrize("trace_id", ["", "\x10", "\x00\x11\x7f"])
def test_empty_cleaned_trace_never_matches_all_reports(tmp_path, trace_id):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    directory = tmp_path / "reports"
    directory.mkdir()
    (directory / "unrelated.png").write_bytes(b"other")
    assert store._collect_report_files(trace_id, []) == []


def test_legacy_scan_still_matches_original_posix_filename(tmp_path, monkeypatch):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    directory = tmp_path / "reports"
    directory.mkdir()
    original_trace = "legacy_\x11日常_end"
    filename = f"report_{original_trace}.png"
    # 模拟 POSIX 上已存在的原始文件名，无需在 Windows 创建控制字符文件。
    legacy_file = SimpleNamespace(
        name=filename,
        suffix=".png",
        is_file=lambda: True,
        stat=lambda: SimpleNamespace(st_mtime=1, st_size=6),
        resolve=lambda: directory / filename,
    )
    original_iterdir = Path.iterdir
    monkeypatch.setattr(
        Path,
        "iterdir",
        lambda path: (
            iter([legacy_file]) if path == directory else original_iterdir(path)
        ),
    )
    reports = store._collect_report_files(original_trace, [])
    assert [report["filename"] for report in reports] == [filename]
