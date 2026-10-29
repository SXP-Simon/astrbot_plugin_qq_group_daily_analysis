"""旧产物回填只在索引为空时执行，并保留有效文件。"""

import json

import pytest

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.parametrize("already_indexed", [True, False])
def test_legacy_artifact_backfill_preserves_one_time_gate(tmp_path, already_indexed):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    store.save_trace({"trace_id": "legacy", "group_id": "123", "started_at": 1000})
    with store._get_connection() as conn:
        conn.execute(
            "UPDATE analysis_traces SET extra_json = ? WHERE trace_id = ?",
            (json.dumps({"report_files": [None, {}, {"filename": "report.html"}]}), "legacy"),
        )
        if already_indexed:
            conn.execute(
                "INSERT INTO report_artifacts VALUES (?, ?, ?, ?, ?, ?)",
                ("indexed.png", "legacy", "123", "image", "indexed.png", 1000),
            )
    reopened = TraceSQLiteStore(store.db_path)
    with reopened._get_connection() as conn:
        rows = conn.execute("SELECT filename, file_format FROM report_artifacts").fetchall()
    assert [(row["filename"], row["file_format"]) for row in rows] == (
        [("indexed.png", "image")] if already_indexed else [("report.html", "html")]
    )
