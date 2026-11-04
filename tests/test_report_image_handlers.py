"""手动报告保存与追踪记录必须指向真实的完整图片。"""

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from test_report_image import long_png as long_png

from src.application.handlers.analysis_command_handler import AnalysisCommandHandler
from src.shared.trace_context import TraceContext


def test_manual_history_keeps_long_png_and_trace_file_metadata(tmp_path, monkeypatch, long_png):
    handler = object.__new__(AnalysisCommandHandler)
    handler.plugin_data_dir = tmp_path
    trace = TraceContext(trace_id="manual-image", group_id="GROUP")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(trace, "persist_snapshot", MagicMock())
    saved = handler._save_report_to_history("base64://" + base64.b64encode(long_png).decode(), "GROUP")
    assert saved is not None
    assert saved.suffix == ".png"
    assert saved.read_bytes() == long_png
    metadata = trace.metadata["report_files"][0]
    assert Path(metadata["path"]) == saved.resolve()
    assert metadata["size_bytes"] == len(long_png)
    trace.persist_snapshot.assert_called_once()


def test_invalid_manual_image_does_not_register_phantom_artifact(tmp_path, monkeypatch):
    handler = object.__new__(AnalysisCommandHandler)
    handler.plugin_data_dir = tmp_path
    trace = TraceContext(trace_id="invalid-image", group_id="GROUP")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    assert handler._save_report_to_history("base64://!invalid!", "GROUP") is None
    assert not trace.metadata.get("report_files")
