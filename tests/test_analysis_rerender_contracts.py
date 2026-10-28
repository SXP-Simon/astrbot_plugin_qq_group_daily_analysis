"""历史存取与重绘产物契约回归测试。"""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.analysis_recovery_service import AnalysisRecoveryService
from src.application.services.analysis_serializer import AnalysisResultSerializer
from src.domain.value_objects import GroupStatistics, SummaryTopic


@pytest.fixture
def analysis():
    return {
        "statistics": GroupStatistics(10, 40, 2, "12:00", [], 0),
        "topics": [SummaryTopic("话题", ["成员"], "详情", ["123"])],
        "user_titles": [],
        "user_analysis": {"123": {"message_count": 10}},
        "chat_quality_review": None,
    }


@pytest.fixture
def recovery(tmp_path, monkeypatch, analysis):
    monkeypatch.setattr(
        "src.application.services.analysis_recovery_service.StarTools.get_data_dir",
        lambda _: tmp_path,
    )
    generator = MagicMock(
        generate_html_report=AsyncMock(return_value=(None, None)),
        generate_image_report=AsyncMock(return_value=(None, None)),
    )
    service = AnalysisRecoveryService(
        MagicMock(),
        MagicMock(),
        MagicMock(get_analysis=AsyncMock(return_value=analysis)),
        generator,
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    return service, generator


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["html", "image"])
@pytest.mark.parametrize("output", [None, "missing", "empty", "directory"])
async def test_rerender_rejects_missing_or_empty_artifact(
    recovery, tmp_path, fmt, output
):
    service, generator = recovery
    source = tmp_path / "source"
    if output == "empty":
        source.touch()
    elif output == "directory":
        source.mkdir()
    getattr(generator, f"generate_{fmt}_report").return_value = (
        str(source) if output else None,
        None,
    )
    result = await service.rerender_report(
        "123", "2026-10-29", "test", render_format=fmt
    )
    assert result["success"] is False
    assert result["reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["html", "image", "base64"])
async def test_rerender_returns_existing_file(recovery, tmp_path, fmt):
    service, generator = recovery
    source = tmp_path / "source"
    source.write_bytes(b"report content")
    value = (
        "base64://" + base64.b64encode(source.read_bytes()).decode()
        if fmt == "base64"
        else str(source)
    )
    report_format = "image" if fmt == "base64" else fmt
    getattr(generator, f"generate_{report_format}_report").return_value = (value, None)
    result = await service.rerender_report(
        "../123",
        "2026-10-29",
        "../test",
        render_format=report_format,
        trace_id="../trace",
    )
    assert result["success"] is True
    dest = Path(result["report_path"])
    assert dest.parent == tmp_path / "reports"
    assert dest.read_bytes() == source.read_bytes()
    assert result["from_checkpoint"] is False


@pytest.mark.asyncio
async def test_rerender_skips_legacy_summary_and_uses_checkpoint(recovery, analysis):
    service, generator = recovery
    service.history_manager.get_analysis.return_value = {"message_count": 7}
    service.checkpoint_store = MagicMock(
        get_checkpoint=MagicMock(
            return_value=AnalysisResultSerializer.serialize(analysis)
        )
    )
    generator.generate_image_report.return_value = ("base64://YWJj", None)
    result = await service.rerender_report("123", "2026-10-29", "test")
    assert result["success"] is True
    assert result["from_checkpoint"] is True
    service.checkpoint_store.get_checkpoint.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["base64://!invalid!", "base64://"])
async def test_rerender_rejects_invalid_base64(recovery, value):
    service, generator = recovery
    generator.generate_image_report.return_value = (value, None)
    assert (await service.rerender_report("123", "2026-10-29", "test"))[
        "success"
    ] is False
