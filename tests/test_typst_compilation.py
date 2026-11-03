"""使用真实字体与独立编译进程验证报告数据边界和失败回退。"""

import base64
import json
import os
import shutil
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from PIL import Image
from test_template_section_conditional_rendering import create_analysis_result

from src.domain.value_objects import GoldenQuote, QualityDimension, QualityReview, UserTitle
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting import typst_renderer
from src.infrastructure.reporting.dispatcher import ReportDispatcher
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

    async def offline_assets(self, source, opacity=1, *, oval=False):
        # 保留真实头像解码与落盘；装饰 CDN 不可用时应以空资源继续编译。
        return await localize(self, source, opacity, oval=oval) if source.startswith("data:") else ""

    monkeypatch.setattr(TypstAssets, "localize", offline_assets)
    try:
        yield config, generator, pixels.getvalue()
    finally:
        await generator.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ["HatsuneMiku", "simple", "hack", "maria"])
@pytest.mark.parametrize("case", ["complete", "empty", "summary_only", "plain_markup", "long_text", "anonymous"])
async def test_real_compilation_accepts_report_content(compiler, monkeypatch, theme, case):
    _, generator, _ = compiler
    worker = AsyncMock(wraps=typst_renderer.run_typst_worker)
    monkeypatch.setattr(typst_renderer, "run_typst_worker", worker)
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
    worker.assert_awaited_once()
    assert not list((generator.data_dir / "typst/jobs").iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True])
async def test_only_exhausted_recovery_uses_explicit_host_fallback(compiler, tmp_path, monkeypatch, fallback):
    config, generator, png = compiler
    root = tmp_path / "templates"
    (root / "HatsuneMiku").mkdir(parents=True)
    (root / "HatsuneMiku/report.typ").write_text("#let broken = (", encoding="utf-8")
    shutil.copyfile(typst_renderer.REPORT_TEMPLATES / "common.typ", root / "common.typ")
    (root / "recovery.typ").write_text("#let also_broken = (", encoding="utf-8")
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
    assert worker.await_count == 2
    assert host.await_count == prepare_html.await_count == int(fallback)
    assert bool(image) is fallback
    assert bool(html) is fallback
    assert not list((generator.data_dir / "typst/jobs").iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["theme", "common", "image", "timeout"])
async def test_real_failure_recovers_complete_report_and_dispatches_image(compiler, tmp_path, monkeypatch, fault):
    config, generator, _ = compiler
    root = tmp_path / "templates"
    shutil.copytree(typst_renderer.REPORT_TEMPLATES / "HatsuneMiku", root / "HatsuneMiku")
    for name in ("common.typ", "recovery.typ"):
        shutil.copyfile(typst_renderer.REPORT_TEMPLATES / name, root / name)
    if fault in ("theme", "common"):
        (root / ("HatsuneMiku/report.typ" if fault == "theme" else "common.typ")).write_text(
            "#let broken = (", encoding="utf-8",
        )
    monkeypatch.setattr(typst_renderer, "REPORT_TEMPLATES", root)
    snapshots = []
    real_worker = typst_renderer.run_typst_worker

    async def record_worker(job, fonts, timeout):
        snapshots.append(json.loads((job / "data.json").read_text(encoding="utf-8")))
        if len(snapshots) == 1:
            if fault == "image":
                for path in job.glob("*.png"):
                    path.write_bytes(b"broken image")
            if fault == "timeout":
                timeout = min(timeout, .05)
        await real_worker(job, fonts, timeout)

    worker = AsyncMock(side_effect=record_worker)
    monkeypatch.setattr(typst_renderer, "run_typst_worker", worker)
    trace = TraceContext(trace_id=f"recover-{fault}", group_id="test")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    config.config["basic"]["output_format"] = ["image"]
    config.config["basic"]["show_report_caption"] = False
    config.config["t2i_rendering"]["t2i_rendering_strategies"][0]["typst_width"] = 1280
    sender = MagicMock()
    sender.bot_manager.get_adapter.return_value = None
    sender.send_image_smart = AsyncMock(return_value=True)
    dispatcher = ReportDispatcher(config, generator, sender)
    dispatcher._dispatch_text = AsyncMock(side_effect=AssertionError("应发送恢复后的图片报告"))
    dispatcher._try_upload_image = AsyncMock()
    data = create_analysis_result()
    data["chat_quality_review"] = QualityReview(
        title="今日交流", subtitle="讨论记录", summary="所有结论都应保留。",
        dimensions=[QualityDimension(name="技术", percentage=100, comment="有具体问题。")],
    )
    assert await dispatcher.dispatch("test", data)
    assert worker.await_count == 2
    assert snapshots[0]["width"] == 1280 and snapshots[1]["width"] == 940
    assert {k: v for k, v in snapshots[0].items() if k != "width"} == {
        k: v for k, v in snapshots[1].items() if k != "width"
    }
    assert all(snapshots[1][key] for key in ("topics", "portraits", "quotes", "review"))
    sender.send_image_smart.assert_awaited_once()
    image = sender.send_image_smart.await_args.args[1]
    with Image.open(BytesIO(base64.b64decode(image.removeprefix("base64://")))) as output:
        assert output.format == "PNG" and output.width == 940
        output.verify()
    saved = list((generator.data_dir / "reports").glob(f"*_{trace.trace_id}.jpg"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == base64.b64decode(image.removeprefix("base64://"))
    assert trace.metadata["typst_recovery"]["mode"] == "basic"
    dispatcher._dispatch_text.assert_not_called()
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
