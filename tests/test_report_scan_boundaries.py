"""历史报告扫描应保留目录边界、隐藏文件过滤和路径去重。"""

from unittest.mock import Mock

import pytest

from src.infrastructure.webui.routes.report_routes import ReportRoutes


def test_report_scan_filters_hidden_files_and_overlapping_roots(tmp_path):
    root, sub, hidden = tmp_path / "reports", tmp_path / "reports" / "12345", tmp_path / "reports" / ".private"
    sub.mkdir(parents=True)
    hidden.mkdir()
    (sub / "report_12345_20261001.html").write_text("report", encoding="utf-8")
    (hidden / "report_99999_20261001.html").write_text("private", encoding="utf-8")
    store = Mock(get_report_trace_map=Mock(return_value={}))
    routes = ReportRoutes(store, None)
    reports = routes._scan_report_history([root, sub], {})
    assert [item["filename"] for item in reports] == ["report_12345_20261001.html"]
    store.register_report_artifact.assert_called_once()


def test_report_scan_excludes_external_symlink(tmp_path):
    root = tmp_path / "reports"
    root.mkdir()
    external = tmp_path / "report_99999_20261001.html"
    external.write_text("external", encoding="utf-8")
    try:
        (root / external.name).symlink_to(external)
    except OSError:
        pytest.skip("当前系统不支持创建测试符号链接")
    store = Mock(get_report_trace_map=Mock(return_value={}))
    assert ReportRoutes(store, None)._scan_report_history([root], {}) == []
    store.register_report_artifact.assert_not_called()
