"""真实排版验证阴影尺寸优化不改变盒子几何与相对单位解析。"""

import json
import shutil
from io import BytesIO
from math import ceil
from pathlib import Path

import pytest
import typst
from PIL import Image
from test_typst_compilation import managed_fonts


@pytest.mark.parametrize("body,width,height", [
    ('block(width:90pt,height:40pt)[fixed]', 90, 40),
    ('box(width:90pt,height:40pt)[fixed]', 90, 40),
    ('block(width:90pt)[some variable height content]', 90, 19.66),
    ('block(width:100%)[some variable height content]', 180, 6.58),
    ('block(width:100%,height:40pt)[fixed height]', 180, 40),
    ('box(width:50%+10pt,height:20pt)[fraction]', 100, 20),
    ('box(width:8em,height:3em)[em]', 80, 30),
    ('box()[intrinsic]', 34.03, 6.58),
    ('block(width:50%+10pt)[fraction]', 100, 6.58),
])
def test_shadow_keeps_existing_layout_dimensions(tmp_path, body, width, height):
    source = Path(__file__).parents[1] / "src/infrastructure/reporting/templates/common.typ"
    shutil.copyfile(source, tmp_path / "common.typ")
    (tmp_path / "main.typ").write_text(
        '#import "common.typ":shadow\n'
        '#set page(width:180pt,height:auto,margin:0pt)\n'
        '#set text(font:"Libertinus Serif",size:10pt)\n'
        '#let t=(u:1pt)\n'
        f'#let body={body}\n'
        '#context{let m=measure(shadow(t,body),width:180pt);'
        '[#metadata((width:m.width/1pt,height:m.height/1pt))<size>]}',
        encoding="utf-8",
    )
    compiler = typst.Compiler(
        str(tmp_path / "main.typ"), root=str(tmp_path), ignore_system_fonts=True,
    )
    size = json.loads(compiler.query("<size>", field="value", one=True))
    assert size["width"] == pytest.approx(width)
    assert size["height"] == pytest.approx(height)


@pytest.mark.parametrize("ppi", [72, 144, 288])
def test_recovery_end_marker_matches_actual_png_height(tmp_path, managed_fonts, ppi):
    source = Path(__file__).parents[1] / "src/infrastructure/reporting/templates/recovery.typ"
    shutil.copyfile(source, tmp_path / "main.typ")
    (tmp_path / "data.json").write_text(json.dumps({
        "width": 940, "ppi": ppi, "language": "zh-Hans", "font_language": "zh-Hans", "date": "2026-11-03",
        "generated_at": "2026-11-03 12:00:00", "message_count": 42, "participant_count": 8,
        "characters": 512, "emoji_count": 3, "peak": "12:00-13:00", "hours": [2] * 24,
        "topics": [{"title": "排版检查", "detail": [{"text": "讨论内容需要自动换行。" * 80, "avatar": ""}],
                    "contributors": [{"text": "群友", "avatar": ""}]}],
        "portraits": [], "quotes": [], "review": None, "tokens": [100, 50, 50], "decorations": [],
    }, ensure_ascii=False), encoding="utf-8")
    fonts = typst.Fonts(include_system_fonts=False, font_paths=[str(managed_fonts / "typst/fonts")])
    compiler = typst.Compiler(
        str(tmp_path / "main.typ"), root=str(tmp_path), font_paths=fonts, ignore_system_fonts=True,
    )
    measured = json.loads(compiler.query("<report-size>", field="value", one=True))
    with Image.open(BytesIO(compiler.compile(format="png", ppi=ppi))) as output:
        assert output.width == 940
        assert output.height == ceil(measured["height"] * ppi / 72)
