from contextlib import contextmanager

import pytest

from astrbot_plugin_qq_group_daily_analysis.src.infrastructure.persistence.trace_sqlite_store import (
    TraceSQLiteStore,
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


def test_trace_count_and_items_share_read_snapshot(tmp_path):
    writer = TraceSQLiteStore(tmp_path / "trace.db")
    for number in range(6):
        save(writer, number)

    class RacingStore(TraceSQLiteStore):
        @contextmanager
        def _get_connection(self):
            with super()._get_connection() as connection:

                def between_count_and_list(sql):
                    if "SELECT" in sql and "t.*" in sql:
                        save(writer, 6)

                connection.set_trace_callback(between_count_and_list)
                yield connection

    reader = RacingStore(writer.db_path)
    items, total = reader.list_traces(limit=100)
    assert total == len(items) == 6
    assert writer.list_traces(limit=100)[1] == 7


def test_time_cursor_survives_insert_delete_equal_times_and_status_change(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    for number in range(6):
        save(store, number)
    first, _ = store.list_traces(limit=3)
    assert [r["trace_id"] for r in first] == ["t00005", "t00004", "t00003"]
    save(store, 7, 101)
    store.delete_trace("t00004")
    store.delete_trace("t00003")
    with store._get_connection() as conn:
        conn.execute(
            "UPDATE analysis_traces SET status = 'failed' WHERE trace_id = 't00002'"
        )
    older, _ = store.list_traces(limit=3, before_time=100, before_id="t00003")
    assert [r["trace_id"] for r in older] == ["t00002", "t00001", "t00000"]
    assert older[0]["status"] == "failed"
    with pytest.raises(ValueError):
        store.list_traces(before_time=100, before_id="t00003", sort_by="total_tokens")


def test_all_trace_sort_ties_have_unique_order(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    for number in range(6):
        save(store, number)
    for field in ("started_at", "duration_ms", "total_tokens", "compression_ratio"):
        first, _ = store.list_traces(limit=3, sort_by=field)
        second, _ = store.list_traces(limit=3, offset=3, sort_by=field)
        assert [r["trace_id"] for r in first + second] == [
            f"t{n:05}" for n in reversed(range(6))
        ]


def test_time_and_group_query_plans_use_covering_order_indexes(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    with store._get_connection() as conn:
        conn.executemany(
            "INSERT INTO analysis_traces(trace_id,group_id,started_at,status) VALUES(?,?,?,'succeeded')",
            [(f"t{i:05}", str(i % 20), i // 3) for i in range(10000)],
        )
        for where, params, index in [
            ("", (), "idx_traces_started_id"),
            (
                "WHERE group_id = ? AND (started_at, trace_id) < (?, ?)",
                ("5", 2500, "t07500"),
                "idx_traces_group_started_id",
            ),
        ]:
            plan = " ".join(
                str(row[3])
                for row in conn.execute(
                    f"EXPLAIN QUERY PLAN SELECT trace_id,started_at FROM analysis_traces {where} ORDER BY started_at DESC,trace_id DESC LIMIT 20",
                    params,
                )
            )
            assert index in plan
            assert "TEMP B-TREE" not in plan


def test_report_query_plans_use_time_and_group_order_indexes(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    with store._get_connection() as conn:
        conn.executemany(
            "INSERT INTO report_artifacts(filename,group_id,file_format,relative_path,created_at) VALUES(?,?,'png',?,?)",
            [
                (f"r{i:05}.png", str(i % 20), f"r{i:05}.png", i // 3)
                for i in range(10000)
            ],
        )
        for where, params, index in [
            ("", (), "idx_artifacts_created_name"),
            (
                "WHERE group_id = ? AND created_at >= ?",
                ("5", 2500),
                "idx_artifacts_group_created_name",
            ),
        ]:
            plan = " ".join(
                str(row[3])
                for row in conn.execute(
                    f"EXPLAIN QUERY PLAN SELECT filename,created_at FROM report_artifacts {where} ORDER BY created_at DESC,filename DESC LIMIT 20",
                    params,
                )
            )
            assert index in plan
            assert "TEMP B-TREE" not in plan
