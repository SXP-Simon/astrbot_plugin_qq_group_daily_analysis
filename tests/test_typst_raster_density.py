"""导出密度独立于固定版心，长图在分配像素面前受预算约束。"""

import json
from unittest.mock import Mock

import pytest
from PIL import Image
from test_typst_compilation import managed_fonts as managed_fonts

from src.infrastructure.reporting import typst_worker
from src.infrastructure.reporting.typst_process import run_typst_worker
from src.shared.trace_context import TraceContext


@pytest.mark.parametrize("height,expected", [(300, 216), (10000, 180), (14000, 144)])
def test_long_reports_lower_density_without_changing_layout(height, expected):
    compiler = Mock()
    compiler.query.return_value = json.dumps({"height": height})
    assert typst_worker._check_canvas(compiler, custom=False, raster_ppi=216) == expected
    compiler.compile.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("ppi,width,height", [(144, 940, 200), (180, 1175, 250), (216, 1410, 300)])
async def test_real_png_density_and_metrics_match_fixed_page(managed_fonts, tmp_path, monkeypatch, ppi, width, height):
    trace = TraceContext(trace_id=f"density-{ppi}")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(TraceContext, "is_metrics_enabled", staticmethod(lambda: True))
    (tmp_path / "main.typ").write_text(
        '#set page(width:470pt,height:100pt,margin:10pt)\n'
        '#set text(font:"Noto Sans SC",size:10pt)\n中文清晰度测试 ABC\n', encoding="utf-8",
    )
    (tmp_path / typst_worker.CUSTOM_TEMPLATE_MARKER).touch()
    metrics = await run_typst_worker(tmp_path, managed_fonts / "typst/fonts", 30, ppi)
    assert metrics["raster_ppi"] == ppi
    with Image.open(tmp_path / "report.png") as image:
        assert image.format == "PNG" and image.size == (width, height)
        image.verify()
