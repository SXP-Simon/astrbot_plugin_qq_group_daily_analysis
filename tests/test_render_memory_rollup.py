"""验证隔离编译内存汇总不混用宿主口径或累加串行峰值。"""

import pytest

from src.infrastructure.reporting.render_trace import publish_typst_memory, render_span
from src.shared.trace_context import TraceContext


@pytest.mark.asyncio
async def test_compile_memory_rolls_up_to_attempt_and_report():
    async with TraceContext(trace_id="memory-rollup"):
        async with render_span("RENDER_REPORT") as report:
            async with render_span("IMAGE_RENDER_ATTEMPT") as attempt:
                for stage, peak, delta in (("TYPST_COMPILE", 250, 220), ("TYPST_RECOVERY", 150, 135)):
                    async with render_span(stage) as child:
                        child["payload"].update(worker_peak_rss_mb=peak, worker_peak_delta_mb=delta, worker_rss_source="linux_proc_status")
                for parent in (report, attempt):
                    assert parent["payload"]["typst_peak_rss_mb"] == 250
                    assert parent["payload"]["typst_peak_delta_mb"] == 220
                    assert parent["payload"]["typst_rss_source"] == "linux_proc_status"
                    assert "worker_start_rss_mb" not in parent["payload"]


@pytest.mark.asyncio
async def test_late_timeout_metrics_are_idempotent_and_scoped_to_parent():
    async with TraceContext(trace_id="memory-partial"):
        async with render_span("RENDER_REPORT") as other:
            pass
        async with render_span("RENDER_REPORT") as report:
            async with render_span("IMAGE_RENDER_ATTEMPT") as attempt:
                with pytest.raises(TimeoutError):
                    async with render_span("TYPST_COMPILE") as child:
                        raise TimeoutError
                child["payload"].update(worker_peak_rss_mb=200, worker_peak_delta_mb=180, worker_rss_source="windows_working_set", worker_metrics_partial=True)
                publish_typst_memory(child)
                publish_typst_memory(child)
                assert attempt["payload"]["typst_peak_delta_mb"] == 180
            assert report["payload"]["typst_peak_rss_mb"] == 200
            assert report["payload"]["typst_metrics_partial"] is True
        assert "typst_peak_rss_mb" not in other["payload"]


@pytest.mark.asyncio
async def test_missing_or_invalid_worker_metrics_do_not_fabricate_parent_memory():
    async with TraceContext(trace_id="memory-unavailable"):
        async with render_span("RENDER_REPORT") as report:
            async with render_span("TYPST_COMPILE") as child:
                child["payload"].update(worker_peak_rss_mb=float("nan"), worker_peak_delta_mb=-1)
            assert "typst_peak_rss_mb" not in report["payload"]
            assert "typst_peak_delta_mb" not in report["payload"]
