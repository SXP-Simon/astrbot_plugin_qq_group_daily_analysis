"""报告在扫描与排序之间消失或不可读时不应阻断其他历史报告。"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.infrastructure.webui.routes.report_routes import ReportRoutes


@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError])
def test_report_scan_skips_file_that_fails_metadata_read(tmp_path, monkeypatch, error):
    root = tmp_path / "reports"
    root.mkdir()
    unstable = root / "report_12345_20261001.html"
    valid = root / "report_12345_20261002.html"
    for file in (unstable, valid):
        file.write_text("report", encoding="utf-8")
    real_stat = Path.stat
    reads = 0

    def stat(path, *args, **kwargs):
        nonlocal reads
        if path == unstable:
            reads += 1
            if reads > 1:
                raise error("模拟扫描后文件不可读")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    store = Mock(get_report_trace_map=Mock(return_value={}))
    reports = ReportRoutes(store, None)._scan_report_history([root], {})
    assert [item["filename"] for item in reports] == [valid.name]
    assert store.register_report_artifact.call_args.kwargs["filename"] == valid.name
