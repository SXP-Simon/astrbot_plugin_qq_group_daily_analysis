"""
测试全链路性能指标与运行期内存 (RSS) / I/O 监控模块
"""

import asyncio
from pathlib import Path

from src.infrastructure.persistence.trace_sqlite_store import TraceSQLiteStore
from src.shared.constants import AnalysisStage
from src.shared.trace_context import TraceContext, _get_process_rss_mb


def test_process_rss_memory_sampling():
    """测试进程 RSS 内存采样函数返回正浮点数。"""
    rss = _get_process_rss_mb()
    assert isinstance(rss, float)
    assert rss >= 0.0


def test_trace_context_performance_metrics_lifecycle():
    """测试 TraceContext 全生命周期中内存打点与 performance_metrics 计算。"""
    with TraceContext(trace_id="test_perf_trace", group_id="123456") as trace:
        assert trace._init_memory_mb >= 0.0
        assert trace._peak_memory_mb >= trace._init_memory_mb

        with trace.span(AnalysisStage.FETCH_MESSAGES, {"fetched_count": 100}) as span_rec:
            assert span_rec.get("start_memory_mb") is not None
            assert span_rec["payload"]["fetched_count"] == 100

        # 校验 span 结束后的指标填充
        assert len(trace._spans) == 1
        span_0 = trace._spans[0]
        assert span_0.get("duration_ms") is not None
        assert span_0.get("end_memory_mb") is not None
        assert span_0.get("delta_memory_mb") is not None
        assert span_0["payload"]["start_memory_mb"] == span_0["start_memory_mb"]
        assert span_0["payload"]["end_memory_mb"] == span_0["end_memory_mb"]

        with trace.span(AnalysisStage.CLEAN_MESSAGES, {"raw_count": 100, "cleaned_count": 80}):
            pass

    # Trace 结束后的全局 performance_metrics
    data = trace.to_dict()
    assert "performance_metrics" in data
    perf = data["performance_metrics"]
    assert "init_memory_mb" in perf
    assert "peak_memory_mb" in perf
    assert "final_memory_mb" in perf
    assert "delta_memory_mb" in perf
    assert perf["peak_memory_mb"] >= perf["init_memory_mb"]
    assert len(data["spans"]) == 2


def test_trace_sqlite_store_performance_metrics_persistence(tmp_path: Path):
    """测试 TraceSQLiteStore 对 performance_metrics 表的存储与完整读取。"""
    db_path = tmp_path / "test_traces.db"
    store = TraceSQLiteStore(db_path)

    trace = TraceContext(trace_id="trace_db_test", group_id="999888", platform="onebot")
    with trace:
        with trace.span(
            AnalysisStage.RENDER_REPORT,
            {
                "template": "scrapbook",
                "format": "image",
                "template_render_ms": 45.2,
                "html_size_kb": 128.5,
                "t2i_render_ms": 1250.0,
                "image_bytes": 450123,
                "dimensions": "1200x4800",
            },
        ):
            pass

        with trace.span(
            AnalysisStage.DISPATCH_REPORT,
            {
                "transmission_mode": "base64",
                "raw_image_kb": 439.5,
                "base64_payload_kb": 586.0,
                "bloat_ratio": "+33.3%",
                "dispatch_api_ms": 320.0,
                "success": True,
            },
        ):
            pass

    # 落盘
    store.save_trace(trace.to_dict())

    # 读取并验证
    saved_data = store.get_trace("trace_db_test")
    assert saved_data is not None
    assert saved_data["trace_id"] == "trace_db_test"
    assert saved_data["performance_metrics"] is not None
    perf = saved_data["performance_metrics"]
    assert perf["init_memory_mb"] >= 0.0
    assert perf["peak_memory_mb"] >= perf["init_memory_mb"]
    assert "final_memory_mb" in perf
    assert "delta_memory_mb" in perf

    # 验证 Spans payload 中的渲染与传输细分指标
    spans = saved_data["spans"]
    assert len(spans) == 2

    render_span = next(s for s in spans if s["stage_name"] == AnalysisStage.RENDER_REPORT.value)
    assert render_span["payload"]["template_render_ms"] == 45.2
    assert render_span["payload"]["html_size_kb"] == 128.5
    assert render_span["payload"]["t2i_render_ms"] == 1250.0
    assert render_span["payload"]["dimensions"] == "1200x4800"

    dispatch_span = next(s for s in spans if s["stage_name"] == AnalysisStage.DISPATCH_REPORT.value)
    assert dispatch_span["payload"]["transmission_mode"] == "base64"
    assert dispatch_span["payload"]["bloat_ratio"] == "+33.3%"
    assert dispatch_span["payload"]["dispatch_api_ms"] == 320.0


def test_trace_sqlite_store_migration_from_old_schema(tmp_path: Path):
    """测试旧版 SQLite 数据库平滑升级与缺少 performance_metrics/metrics_json 时的容错。"""
    import sqlite3
    db_path = tmp_path / "legacy_traces.db"

    # 1. 模拟旧版数据库表结构（无 performance_metrics 表）
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE analysis_traces (
                trace_id TEXT PRIMARY KEY,
                group_id TEXT NOT NULL,
                group_name TEXT DEFAULT '',
                platform TEXT DEFAULT '',
                trigger_type TEXT DEFAULT 'manual',
                status TEXT NOT NULL,
                started_at REAL NOT NULL,
                completed_at REAL,
                duration_ms REAL,
                error_stage TEXT,
                error_message TEXT,
                stack_trace TEXT,
                extra_json TEXT DEFAULT '{}'
            );
            """
        )
        conn.execute(
            "INSERT INTO analysis_traces (trace_id, group_id, status, started_at) VALUES ('old_trace_1', '1001', 'succeeded', 1000.0)"
        )

    # 2. 用新版本 TraceSQLiteStore 打开该数据库（触发自动迁移与表补齐）
    store = TraceSQLiteStore(db_path)
    old_trace = store.get_trace("old_trace_1")
    assert old_trace is not None
    assert old_trace["trace_id"] == "old_trace_1"
    assert old_trace["performance_metrics"] is None

    # 3. 模拟旧版本建了 performance_metrics 表但无 metrics_json 列的情况
    db_path_2 = tmp_path / "legacy_traces_no_col.db"
    with sqlite3.connect(str(db_path_2)) as conn:
        conn.executescript(
            """
            CREATE TABLE analysis_traces (
                trace_id TEXT PRIMARY KEY,
                group_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at REAL NOT NULL
            );
            CREATE TABLE performance_metrics (
                trace_id TEXT PRIMARY KEY,
                init_memory_mb REAL DEFAULT 0.0,
                peak_memory_mb REAL DEFAULT 0.0,
                final_memory_mb REAL DEFAULT 0.0,
                delta_memory_mb REAL DEFAULT 0.0
            );
            INSERT INTO analysis_traces (trace_id, group_id, status, started_at) VALUES ('old_trace_2', '1002', 'succeeded', 2000.0);
            INSERT INTO performance_metrics (trace_id, init_memory_mb, peak_memory_mb) VALUES ('old_trace_2', 100.0, 150.0);
            """
        )

    store_2 = TraceSQLiteStore(db_path_2)
    trace_migrated = store_2.get_trace("old_trace_2")
    assert trace_migrated is not None
    assert trace_migrated["performance_metrics"] is not None
    assert trace_migrated["performance_metrics"]["init_memory_mb"] == 100.0
    assert trace_migrated["performance_metrics"]["metrics_extra"] == {}


def test_trace_sqlite_store_corrupted_metrics_json_tolerance(tmp_path: Path):
    """测试 metrics_json 数据损坏（非法 JSON）时 get_trace() 安全容错。"""
    import sqlite3
    db_path = tmp_path / "corrupted_traces.db"
    store = TraceSQLiteStore(db_path)

    with store._get_connection() as conn:
        conn.execute(
            "INSERT INTO analysis_traces (trace_id, group_id, status, started_at) VALUES ('bad_json_trace', '1003', 'succeeded', 3000.0)"
        )
        conn.execute(
            "INSERT INTO performance_metrics (trace_id, init_memory_mb, metrics_json) VALUES ('bad_json_trace', 80.0, '{invalid-json-string}')"
        )

    trace = store.get_trace("bad_json_trace")
    assert trace is not None
    assert trace["performance_metrics"] is not None
    assert trace["performance_metrics"]["init_memory_mb"] == 80.0
    assert trace["performance_metrics"]["metrics_extra"] == {}


def test_enable_runtime_metrics_config_default():
    """测试 enable_runtime_metrics 默认开启 (True) 并与 Schema 一致。"""
    import json
    from src.infrastructure.config.config_manager import ConfigManager

    cfg = ConfigManager({})
    assert cfg.get_enable_runtime_metrics() is True

    schema_file = Path(__file__).parent.parent / "_conf_schema.json"
    with open(schema_file, encoding="utf-8") as f:
        schema = json.load(f)
    assert schema["basic"]["items"]["enable_runtime_metrics"]["default"] is True


def test_trace_context_disabled_metrics():
    """测试关闭遥测开关时 TraceContext 跳过 RSS 采样。"""
    try:
        TraceContext.set_metrics_enabled(False)
        assert TraceContext.is_metrics_enabled() is False

        with TraceContext(trace_id="no_metrics_trace") as trace:
            assert trace._init_memory_mb == 0.0
            assert trace._peak_memory_mb == 0.0

            with trace.span(AnalysisStage.FETCH_MESSAGES) as s:
                assert s["start_memory_mb"] == 0.0

            data = trace.to_dict()
            perf = data["performance_metrics"]
            assert perf["init_memory_mb"] == 0.0
            assert perf["peak_memory_mb"] == 0.0
            assert perf["final_memory_mb"] == 0.0
    finally:
        TraceContext.set_metrics_enabled(True)
        assert TraceContext.is_metrics_enabled() is True


def test_log_buffer_raw_trace_id_sanitization():
    """测试 PluginLogBuffer 在记录包含 [trace_id] 消息时 raw 字段不重复前缀。"""
    from src.infrastructure.logging.plugin_log_buffer import PluginLogBuffer

    buffer = PluginLogBuffer()
    entry = buffer.record_log(
        level="INFO",
        msg="[test_trace_123] 消息拉取完成",
        trace_id="test_trace_123",
        logger_name="analysis",
    )
    assert entry.message == "消息拉取完成"
    assert not entry.raw.endswith("[test_trace_123] [test_trace_123] 消息拉取完成")
    assert entry.raw.endswith("[analysis]: 消息拉取完成")


