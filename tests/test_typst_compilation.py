"""使用真实字体与独立编译进程验证报告数据边界和失败回退。"""

import base64
import json
import os
import shutil
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from PIL import Image
from test_template_section_conditional_rendering import create_analysis_result

from src.domain.value_objects import GoldenQuote, QualityDimension, QualityReview, UserTitle
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting import typst_renderer
from src.infrastructure.reporting.generators import ReportGenerator
from src.infrastructure.reporting.typst_resources import TypstAssets
from src.shared.trace_context import TraceContext


@pytest.fixture(scope="module")
def managed_fonts(tmp_path_factory):
    """复制已下载字体一次；CI 必须提供目录，本地未配置时明确跳过编译组。"""
    configured = os.environ.get("TYPST_TEST_FONTS")
    if not configured:
        pytest.skip("设置 TYPST_TEST_FONTS 为已下载的字体目录以运行真实编译；CI 固定启用")
    source = Path(configured)
    if not source.is_dir():
        pytest.fail(f"真实编译字体目录不存在：{source}")
    data_dir = tmp_path_factory.mktemp("typst-compilation")
    shutil.copytree(source, data_dir / "typst/fonts")
    return data_dir


@pytest_asyncio.fixture
async def compiler(managed_fonts, monkeypatch):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    config = object.__new__(ConfigManager)
    config.config = {
        "basic": {"report_template": "HatsuneMiku", "profile_display_mode": "mbti"},
        "t2i_rendering": {"t2i_rendering_strategies": [
            {"__template_key": "typst", "priority": 1, "timeout": 30000},
        ]},
    }
    generator = ReportGenerator(config, managed_fonts)
    pixels = BytesIO()
    Image.new("RGB", (12, 12), "#39c5bb").save(pixels, format="PNG")
    avatar = "data:image/png;base64," + base64.b64encode(pixels.getvalue()).decode()
    generator._avatar_service.get_user_avatar = AsyncMock(return_value=avatar)
    localize = TypstAssets.localize

    async def offline_assets(self, source, opacity=1):
        # 保留真实头像解码与落盘；装饰 CDN 不可用时应以空资源继续编译。
        return await localize(self, source, opacity) if source.startswith("data:") else ""

    monkeypatch.setattr(TypstAssets, "localize", offline_assets)
    try:
        yield config, generator, pixels.getvalue()
    finally:
        await generator.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ["HatsuneMiku", "simple", "hack"])
@pytest.mark.parametrize("case", ["complete", "empty", "summary_only", "plain_markup", "long_text", "anonymous"])
async def test_real_compilation_accepts_report_content(compiler, theme, case):
    _, generator, _ = compiler
    data = create_analysis_result(empty=case == "empty")
    data["statistics"].activity_visualization.hourly_activity = {
        hour: 0 if case == "empty" else hour % 5 for hour in range(24)
    }
    if case != "empty":
        data["user_titles"].append(UserTitle(
            user_id="234567", name="李四", title="技术观察员", mbti="INTJ", reason="耐心解释问题，也会整理讨论结论。",
        ))
        data["statistics"].golden_quotes.append(GoldenQuote(
            user_id="234567", sender="李四", content="先把问题说清楚。", reason="让讨论有了可以验证的方向。",
        ))
        data["chat_quality_review"] = QualityReview(
            title="今日交流", subtitle="讨论记录", summary="讨论有回应，也留下了清楚的结论。",
            dimensions=[] if case == "summary_only" else [
                QualityDimension(name="技术", percentage=60, comment="有具体的问题。"),
                QualityDimension(name="日常", percentage=40, comment="大家都有回应。"),
            ],
        )
    if case == "plain_markup":
        literal = '#panic("must stay text") [括号] {body} <tag> $1 \\ / "引号"'
        data["topics"][0].topic = literal
        data["topics"][0].detail = literal
        data["statistics"].golden_quotes[0].content = literal
    if case == "long_text":
        data["topics"][0].detail = "大家认真讨论具体的问题，并逐步整理可以验证的结论。" * 30
        data["user_titles"][0].name = "认真整理讨论记录的群友名字比较长"
        data["user_titles"][0].reason = "既能把问题拆开说明，也愿意耐心回应其他成员。" * 5
    host = AsyncMock(side_effect=AssertionError("原生编译不得调用宿主"))
    image, html = await generator.generate_image_report(
        data, "test", host, template_theme=theme, hide_user_names=case == "anonymous",
    )
    assert image and image.startswith("base64://") and html is None
    with Image.open(BytesIO(base64.b64decode(image.removeprefix("base64://")))) as output:
        assert output.format == "PNG"
        output.verify()
    host.assert_not_called()
    assert not list((generator.data_dir / "typst/jobs").iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True])
async def test_real_syntax_error_only_uses_explicit_fallback(compiler, tmp_path, monkeypatch, fallback):
    config, generator, png = compiler
    root = tmp_path / "templates"
    (root / "HatsuneMiku").mkdir(parents=True)
    (root / "HatsuneMiku/report.typ").write_text("#let broken = (", encoding="utf-8")
    shutil.copyfile(typst_renderer.REPORT_TEMPLATES / "common.typ", root / "common.typ")
    monkeypatch.setattr(typst_renderer, "REPORT_TEMPLATES", root)
    worker = AsyncMock(wraps=typst_renderer.run_typst_worker)
    monkeypatch.setattr(typst_renderer, "run_typst_worker", worker)
    if fallback:
        config.config["t2i_rendering"]["t2i_rendering_strategies"].append(
            {"__template_key": "strategy", "priority": 2},
        )
    host = AsyncMock(return_value=png)
    prepare_html = AsyncMock(wraps=generator._prepare_render_data)
    monkeypatch.setattr(generator, "_prepare_render_data", prepare_html)
    image, html = await generator.generate_image_report(create_analysis_result(), "test", host)
    assert worker.await_count == 1
    assert host.await_count == prepare_html.await_count == int(fallback)
    assert bool(image) is fallback
    assert bool(html) is fallback
    assert not list((generator.data_dir / "typst/jobs").iterdir())


@pytest.mark.asyncio
async def test_worker_rejects_oversized_report_before_png(compiler, tmp_path):
    _, generator, _ = compiler
    (tmp_path / "data.json").write_text(json.dumps({"width": 940, "ppi": 144}), encoding="utf-8")
    (tmp_path / "main.typ").write_text(
        '#set page(width:470pt,height:auto,margin:0pt)\n'
        '#rect(width:1pt,height:20000pt)\n'
        '#metadata((height:20000))<report-size>', encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="像素预算"):
        await typst_renderer.run_typst_worker(tmp_path, generator.data_dir / "typst/fonts", 30)
    assert not (tmp_path / "report.png").exists()


@pytest.mark.asyncio
async def test_compile_error_keeps_first_source_location(compiler, tmp_path):
    _, generator, _ = compiler
    (tmp_path / "data.json").write_text(json.dumps({"width": 940, "ppi": 144}), encoding="utf-8")
    (tmp_path / "main.typ").write_text(
        "".join(f"#let broken{i} = (\n" for i in range(30)), encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match=r"main\.typ:1:"):
        await typst_renderer.run_typst_worker(tmp_path, generator.data_dir / "typst/fonts", 30)
