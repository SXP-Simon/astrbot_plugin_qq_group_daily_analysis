"""任务详情对损坏及非对象旧 JSON 数据的容错回归。"""

import json

import pytest

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore


@pytest.mark.parametrize("raw", ["[]", "null", "7", '"legacy"', "broken-json"])
def test_trace_detail_normalizes_non_object_json(tmp_path, raw):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    store.save_trace(
        {
            "trace_id": "legacy",
            "group_id": "123",
            "extra": {"llm_prompts": {"topics": {"prompt": "保留提示词"}}},
            "spans": [{"stage_name": "LLM_ANALYSIS"}],
            "token_usage": {"total_tokens": 7},
            "performance_metrics": {"total_duration_ms": 10},
        }
    )
    with store._get_connection() as conn:
        for table, column in (
            ("trace_spans", "stage_payload_json"),
            ("token_usage", "per_analyzer_tokens_json"),
            ("performance_metrics", "metrics_json"),
        ):
            conn.execute(
                f"UPDATE {table} SET {column} = ? WHERE trace_id = ?",
                (raw, "legacy"),
            )
    detail = store.get_trace("legacy")
    assert detail["spans"][0]["payload"]["prompts"]["topics"]["prompt"] == "保留提示词"
    assert detail["token_usage"]["per_analyzer"] == {}
    assert detail["performance_metrics"]["metrics_extra"] == {}

    with store._get_connection() as conn:
        conn.execute(
            "UPDATE analysis_traces SET extra_json = ? WHERE trace_id = ?",
            (raw, "legacy"),
        )
    detail = store.get_trace("legacy")
    assert detail["extra"] == {}
    assert detail["report_files"] == []


def test_trace_detail_preserves_valid_json_objects(tmp_path):
    store = TraceSQLiteStore(tmp_path / "trace.db")
    store.save_trace({"trace_id": "valid", "group_id": "123"})
    extra = {"llm_prompts": {"topics": {"prompt": "有效提示词"}}}
    with store._get_connection() as conn:
        conn.execute(
            "UPDATE analysis_traces SET extra_json = ? WHERE trace_id = ?",
            (json.dumps(extra), "valid"),
        )
    assert store.get_trace("valid")["extra"] == extra
