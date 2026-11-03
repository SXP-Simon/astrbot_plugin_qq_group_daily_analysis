"""真实排版验证阴影尺寸优化不改变盒子几何与相对单位解析。"""

import json
import shutil
from pathlib import Path

import pytest
import typst


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
