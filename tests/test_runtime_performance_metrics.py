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
