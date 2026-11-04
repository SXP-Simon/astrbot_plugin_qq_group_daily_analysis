"""隔离编译的 RSS 必须来自当前工作进程，而非 fork/exec 前的宿主。"""

import sys
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.infrastructure.reporting import typst_worker as worker
from src.infrastructure.reporting.typst_process import _parse_worker_metrics


def test_metrics_keep_last_complete_frame_after_process_was_interrupted():
    stdout = b'{"worker_phase":"font_setup"}\n{"worker_phase":"raster","layout_ms":15}\n{"worker_phase":'
    assert _parse_worker_metrics(stdout) == {"worker_phase": "raster", "layout_ms": 15}


def test_linux_peak_ignores_inherited_resource_high_water_mark(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    inherited = Mock(return_value=SimpleNamespace(ru_maxrss=2 * 1024 * 1024))
    monkeypatch.setitem(sys.modules, "resource", SimpleNamespace(getrusage=inherited, RUSAGE_SELF=0))
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: "VmHWM:\t102400 kB\nVmRSS:\t25600 kB\n")
    metrics = {}
    worker._collect_peak(metrics)
    assert metrics["worker_peak_rss_mb"] == 100
    inherited.assert_not_called()


def test_linux_peak_growth_uses_worker_startup_rss(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    values = iter(["VmHWM: 10240 kB\nVmRSS: 10240 kB\n", "VmHWM: 102400 kB\nVmRSS: 25600 kB\n"])
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: next(values))
    metrics = {}
    worker._collect_peak(metrics, baseline=True)
    worker._collect_peak(metrics)
    assert metrics == {"worker_start_rss_mb": 10, "worker_peak_rss_mb": 100, "worker_peak_delta_mb": 90, "worker_rss_source": "linux_proc_status"}


@pytest.mark.parametrize("error", [PermissionError(), ValueError(), KeyError()])
def test_unavailable_linux_metrics_never_abort_report_or_fall_back_to_inherited_peak(monkeypatch, error):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=error))
    metrics = {}
    worker._collect_peak(metrics)
    assert metrics == {}


@pytest.mark.parametrize("source", ["linux_proc_status", "windows_working_set", "unknown"])
def test_process_boundary_preserves_only_valid_memory_metrics(source):
    raw = {"worker_start_rss_mb": 10, "worker_peak_rss_mb": 100, "worker_peak_delta_mb": 90, "worker_rss_source": source, "unexpected": 999}
    parsed = _parse_worker_metrics(json.dumps(raw).encode())
    assert parsed["worker_start_rss_mb"] == 10
    assert parsed["worker_peak_delta_mb"] == 90
    assert "unexpected" not in parsed
    assert parsed.get("worker_rss_source") == (source if source != "unknown" else None)
