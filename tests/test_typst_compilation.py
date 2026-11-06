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
import typst
from PIL import Image, ImageChops, ImageDraw, ImageStat
from test_template_section_conditional_rendering import create_analysis_result
from test_typst_resources import oversized_avatar_uri as oversized_avatar_uri

from src.domain.value_objects import GoldenQuote, QualityDimension, QualityReview, UserTitle
from src.domain.value_objects.task_event import TaskEvent
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting import typst_renderer
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.infrastructure.reporting.generators import ReportGenerator
from src.infrastructure.reporting.typst_resources import TypstAssets
from src.infrastructure.reporting.display_names import normalize_display_name
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


def test_miku_control_character_nickname_matches_clean_single_line_layout(tmp_path, managed_fonts):
    """真实编译截图中的昵称，发言人及行内头像均应与干净文本一致。"""
    templates = Path(__file__).parents[1] / "src/infrastructure/reporting/templates"
    shutil.copyfile(templates / "HatsuneMiku/miku.typ", tmp_path / "miku.typ")
    shutil.copyfile(templates / "common.typ", tmp_path / "common.typ")
    Image.new("RGB", (18, 18), "#39c5bb").save(tmp_path / "avatar.png")
    (tmp_path / "main.typ").write_text(
        '#import "miku.typ": copy, runs\n'
        '#let t=(u:1pt,fonts:("Noto Sans SC",))\n'
        '#set page(width:440pt,height:auto,margin:10pt)\n'
        '#let name=json("name.json")\n'
        '#copy(t,name,size:13.6)\n#parbreak()\n'
        '#copy(t,runs(t,((text:"展现了令人绝倒的清奇脑回路，",avatar:""),'
        '(text:name,avatar:"avatar.png"),(text:" 一本正经地回应。",avatar:""))),size:14.4)\n',
        encoding="utf-8",
    )
    raw = "\n\x0e\x12本间心铃\n\t\n\x07纱A\x1a\x11\x10\x00"
    outputs = []
    for name in (raw, normalize_display_name(raw), "本间心铃 纱A"):
        (tmp_path / "name.json").write_text(json.dumps(name), encoding="utf-8")
        compiler = typst.Compiler(
            str(tmp_path / "main.typ"), root=str(tmp_path),
            font_paths=[str(managed_fonts / "typst/fonts")], ignore_system_fonts=True,
        )
        with Image.open(BytesIO(compiler.compile(format="png", ppi=144))) as image:
            outputs.append(image.convert("RGB"))
    for label, image in zip(("before", "after", "expected"), outputs):
        image.save(tmp_path / f"nickname-{label}.png")
    assert outputs[0].height > outputs[1].height
    assert outputs[1].size == outputs[2].size
    assert ImageChops.difference(outputs[1], outputs[2]).getbbox() is None


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
@pytest.mark.parametrize("theme", ["HatsuneMiku", "simple", "hack", "maria", "ATRI", "deepseek_maid", "art_nouveau", "scrapbook", "format", "spring_festival", "retro_futurism", "BlueArchive"])
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
        data["chat_quality_review"].dimensions[0].color = literal
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


@pytest.mark.parametrize("pose,expected", [
    ("open", (0, 0, 0)), ("sleep", (255, 255, 255)),
    ("basin", (255, 0, 0)), ("missing", (255, 255, 255)),
])
def test_maid_composes_cached_layers_without_floating_eyes(tmp_path, pose, expected):
    """用本地图层验证睁眼、闭眼、铁盆裁切及主体缺失时的整体留白。

    Args:
        tmp_path: 本次编译的隔离根目录。
        pose: 角色状态或主体图片缺失的场景。
        expected: 眼部采样点应有的颜色。
    """
    import typst

    templates = Path(__file__).parents[1] / "src/infrastructure/reporting/templates"
    shutil.copyfile(templates / "common.typ", tmp_path / "common.typ")
    shutil.copyfile(templates / "deepseek_maid/maid.typ", tmp_path / "maid.typ")
    decorations = []
    for source in typst_renderer.THEME_DECORATIONS["deepseek_maid"]:
        name = Path(source).name
        layer = Image.new("RGBA", (1536, 1024), "blue" if name == "front.png" else (0, 0, 0, 0))
        if name in ("eye-0.png", "closed-eye-0.png"):
            ImageDraw.Draw(layer).rectangle((350, 390, 390, 430), fill="black" if name == "eye-0.png" else "white")
        if name == "basin-v3.png":
            layer = Image.new("RGBA", (1122, 1402), "red")
        layer.save(tmp_path / name)
        decorations.append("" if pose == "missing" and name == "front.png" else name)
    (tmp_path / "data.json").write_text(json.dumps({"decorations": decorations}), encoding="utf-8")
    (tmp_path / "main.typ").write_text(
        '#import "maid.typ":character\n'
        '#set page(width:710pt,height:1024pt,margin:0pt)\n'
        f'#character((u:1pt),json("data.json"),mood:"{pose}",'
        f'basin:{str(pose == "basin").lower()},width:710,height:1024)',
        encoding="utf-8",
    )
    compiler = typst.Compiler(str(tmp_path / "main.typ"), root=str(tmp_path), ignore_system_fonts=True)
    with Image.open(BytesIO(compiler.compile(format="png", ppi=72))) as image:
        assert image.size == (710, 1024)
        assert image.convert("RGB").getpixel((250, 400)) == expected


@pytest.mark.parametrize("theme,module", [("art_nouveau", "nouveau"), ("maria", "maria"), ("format", "format"), ("spring_festival", "spring"), ("retro_futurism", "retro"), ("hack", "hack")])
def test_oblique_does_not_shift_the_whole_paragraph(tmp_path, managed_fonts, theme, module):
    """验证长段落的中文斜体逐字倾斜，首行不会被推向卡片外侧。

    Args:
        tmp_path: 本次编译的隔离根目录。
        managed_fonts: 已准备的插件受管理字体目录。
        theme: 要验证的主题目录。
        module: 主题导出的排版模块。
    """
    import typst

    templates = Path(__file__).parents[1] / "src/infrastructure/reporting/templates"
    shutil.copyfile(templates / "common.typ", tmp_path / "common.typ")
    shutil.copyfile(templates / theme / f"{module}.typ", tmp_path / f"{module}.typ")
    outputs = []
    for oblique in (False, True):
        extra = f",oblique:{str(oblique).lower()}" if theme not in {"format", "spring_festival", "retro_futurism", "hack"} else ""
        (tmp_path / "main.typ").write_text(
            f'#import "{module}.typ":copy\n'
            '#set page(width:200pt,height:auto,margin:10pt)\n'
            '#let t=(u:1pt,body:("Noto Serif SC",),fonts:("Noto Sans SC",))\n'
            f'#copy(t,{json.dumps("总能把讨论带往有趣的方向，愿意认真回应每一位群友。" * 5, ensure_ascii=False)},'
            f'size:14,lh:1.55,fill:rgb("111111"),italic:{str(oblique).lower()}{extra})',
            encoding="utf-8",
        )
        compiler = typst.Compiler(
            str(tmp_path / "main.typ"), root=str(tmp_path),
            font_paths=[str(managed_fonts / "typst/fonts")], ignore_system_fonts=True,
        )
        with Image.open(BytesIO(compiler.compile(format="png", ppi=72))) as image:
            outputs.append(image.convert("RGB"))
    assert outputs[0].size == outputs[1].size
    assert ImageChops.difference(*outputs).getbbox() is not None
    first_line = outputs[1].crop((10, 10, 190, 32)).convert("L").point(lambda value: 255 if value < 100 else 0)
    bounds = first_line.getbbox()
    assert bounds is not None and bounds[0] < 5


def test_retro_avatars_keep_css_grayscale_contrast_and_transparency(tmp_path):
    """验证本地头像的灰度、对比度及透明区，不依赖网络素材。

    Args:
        tmp_path: 本次编译的隔离根目录。
    """
    import typst

    templates = Path(__file__).parents[1] / "src/infrastructure/reporting/templates"
    shutil.copyfile(templates / "retro_futurism/retro.typ", tmp_path / "retro.typ")
    pixels = Image.new("RGBA", (40, 40), (57, 197, 187, 255))
    ImageDraw.Draw(pixels).rectangle((20, 0, 39, 39), fill=(0, 0, 0, 0))
    pixels.save(tmp_path / "avatar.png")
    (tmp_path / "main.typ").write_text(
        '#import "retro.typ":avatar\n'
        '#set page(width:80pt,height:40pt,margin:0pt,fill:white)\n'
        '#grid(columns:(40pt,40pt),gutter:0pt,'
        'avatar((u:1pt),"avatar.png",size:40),'
        'avatar((u:1pt),"avatar.png",size:40,round:true,contrast:1))',
        encoding="utf-8",
    )
    compiler = typst.Compiler(str(tmp_path / "main.typ"), root=str(tmp_path), ignore_system_fonts=True)
    with Image.open(BytesIO(compiler.compile(format="png", ppi=72))) as output:
        output = output.convert("RGB")
        for point, expected in [((10, 20), 170), ((50, 20), 167)]:
            assert all(abs(channel - expected) <= 1 for channel in output.getpixel(point))
        assert output.getpixel((30, 20)) == (238, 238, 238)
        assert output.getpixel((70, 20)) == (255, 255, 255)


def test_atri_section_dots_remain_beneath_the_translucent_gradient(tmp_path):
    """验证分区花点被上层渐变柔化，避免遗漏纹理或把花点画得过深。

    Args:
        tmp_path: 本次编译的隔离根目录。
    """
    import typst

    templates = Path(__file__).parents[1] / "src/infrastructure/reporting/templates"
    shutil.copyfile(templates / "common.typ", tmp_path / "common.typ")
    shutil.copyfile(templates / "ATRI/atri.typ", tmp_path / "atri.typ")
    (tmp_path / "main.typ").write_text(
        '#import "atri.typ":glass\n'
        '#set page(width:300pt,height:auto,margin:0pt,fill:white)\n'
        '#glass((u:1pt),padx:0,pady:0,stroke:2,'
        'dots:rgb("82dcb9").transparentize(65%),'
        'fill:gradient.linear(rgb("c8f5e6").transparentize(10%),'
        'rgb("dcfaf0").transparentize(15%),angle:90deg,space:rgb),'
        'block(width:100%,height:100pt)[])',
        encoding="utf-8",
    )
    compiler = typst.Compiler(str(tmp_path / "main.typ"), root=str(tmp_path), ignore_system_fonts=True)
    with Image.open(BytesIO(compiler.compile(format="png", ppi=72))) as image:
        image = image.convert("RGB")
        assert 3 <= image.getpixel((20, 14))[0] - image.getpixel((14, 14))[0] <= 12


def test_atri_glass_blurs_the_cached_background(tmp_path, managed_fonts):
    """验证 SVG 使用任务内缓存图片，日期卡中的背景确实被模糊。

    Args:
        tmp_path: 本次编译的隔离根目录。
        managed_fonts: 已准备的插件受管理字体目录。
    """
    import typst

    templates = Path(__file__).parents[1] / "src/infrastructure/reporting/templates"
    shutil.copyfile(templates / "common.typ", tmp_path / "common.typ")
    shutil.copyfile(templates / "ATRI/atri.typ", tmp_path / "atri.typ")
    # 高频条纹能区分真实模糊与简单的半透明遮罩，不绑定具体海景像素。
    background = Image.new("RGB", (834, 213), "white")
    drawing = ImageDraw.Draw(background)
    for x in range(0, 834, 12):
        drawing.rectangle((x, 0, x + 5, 212), fill="black")
    background.save(tmp_path / "cached-scene.png")
    (tmp_path / "main.typ").write_text(
        '#import "atri.typ":header\n'
        '#set page(width:834pt,height:auto,margin:0pt)\n'
        '#set text(font:"LXGW WenKai",lang:"zh",region:"CN",cjk-latin-spacing:none)\n'
        '#header((u:1pt,font:("LXGW WenKai",),mono:("LXGW WenKai Mono",)), '
        '(date:"2026年11月03日",generated_at:"2026-11-03 12:00:00",decorations:("cached-scene.png",)))',
        encoding="utf-8",
    )
    compiler = typst.Compiler(
        str(tmp_path / "main.typ"), root=str(tmp_path),
        font_paths=[str(managed_fonts / "typst/fonts")], ignore_system_fonts=True,
    )
    with Image.open(BytesIO(compiler.compile(format="png", ppi=72))) as image:
        clear = sum(ImageStat.Stat(image.crop((450, 105, 468, 115)).convert("RGB")).stddev)
        frosted = sum(ImageStat.Stat(image.crop((590, 105, 608, 115)).convert("RGB")).stddev)
        assert clear > 30
        assert frosted < clear * .3


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True])
async def test_only_exhausted_recovery_uses_explicit_host_fallback(compiler, tmp_path, monkeypatch, fallback):
    config, generator, png = compiler
    trace = TraceContext(trace_id=f"exhausted-{fallback}", group_id="test")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
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
    trace.finish(TaskEvent.SUCCEED if fallback else TaskEvent.FAIL)
    assert trace.status == ("warning" if fallback else "failed")
    native_spans = [span for span in trace.to_dict()["spans"] if span["stage_name"] in ("TYPST_COMPILE", "TYPST_RECOVERY")]
    assert len(native_spans) == 2
    assert all(span["status"] == ("warning" if fallback else "failed") for span in native_spans)
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

    async def record_worker(job, fonts, timeout, raster_ppi=144):
        snapshots.append(json.loads((job / "data.json").read_text(encoding="utf-8")))
        if len(snapshots) == 1:
            if fault == "image":
                for path in job.glob("*.png"):
                    path.write_bytes(b"broken image")
            if fault == "timeout":
                timeout = min(timeout, .05)
        return await real_worker(job, fonts, timeout, raster_ppi)

    worker = AsyncMock(side_effect=record_worker)
    monkeypatch.setattr(typst_renderer, "run_typst_worker", worker)
    trace = TraceContext(trace_id=f"recover-{fault}", group_id="test")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    config.config["basic"]["output_format"] = ["image"]
    config.config["basic"]["show_report_caption"] = False
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
    assert snapshots[0] == snapshots[1]
    assert "width" not in snapshots[0] and "ppi" not in snapshots[0]
    assert all(snapshots[1][key] for key in ("topics", "portraits", "quotes", "review"))
    sender.send_image_smart.assert_awaited_once()
    image = sender.send_image_smart.await_args.args[1]
    with Image.open(BytesIO(base64.b64decode(image.removeprefix("base64://")))) as output:
        assert output.format == "PNG" and output.width == 940
        output.verify()
    saved = list((generator.data_dir / "reports").glob(f"*_{trace.trace_id}.png"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == base64.b64decode(image.removeprefix("base64://"))
    assert trace.metadata["typst_recovery"]["mode"] == "basic"
    spans = {span["stage_name"]: span for span in trace.to_dict()["spans"]}
    attempt = spans["IMAGE_RENDER_ATTEMPT"]
    assert attempt["payload"]["parent_span_id"] == spans["RENDER_REPORT"]["span_id"]
    assert all(span["payload"]["parent_span_id"] == attempt["span_id"] for stage, span in spans.items() if stage.startswith("TYPST_"))
    assert spans["TYPST_COMPILE"]["status"] == "warning"
    assert "error" not in spans["TYPST_COMPILE"]["payload"]
    assert spans["TYPST_RECOVERY"]["status"] == "success"
    assert spans["TYPST_RECOVERY"]["payload"]["worker_peak_rss_mb"] > 0
    memory = spans["TYPST_RECOVERY"]["payload"]
    assert memory["worker_rss_source"] in ("linux_proc_status", "windows_working_set", "posix_getrusage")
    if memory["worker_rss_source"] != "posix_getrusage":
        assert memory["worker_start_rss_mb"] > 0
        assert abs(memory["worker_peak_delta_mb"] + memory["worker_start_rss_mb"] - memory["worker_peak_rss_mb"]) <= 0.02
    assert spans["TYPST_ENCODE"]["payload"]["image_bytes"] > 0
    trace.finish(TaskEvent.SUCCEED)
    assert trace.status == "warning"
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


@pytest.mark.asyncio
async def test_huge_avatar_still_generates_native_report_without_recovery(compiler, monkeypatch, oversized_avatar_uri):
    _, generator, _ = compiler
    generator._avatar_service.get_user_avatar.return_value = oversized_avatar_uri
    worker = AsyncMock(wraps=typst_renderer.run_typst_worker)
    monkeypatch.setattr(typst_renderer, "run_typst_worker", worker)
    image, html = await generator.generate_image_report(create_analysis_result(), "safe-image", None)
    assert image and image.startswith("base64://") and html is None
    worker.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("case,attempts", [("valid", 1), ("huge_canvas", 2), ("pages", 2)])
async def test_custom_canvas_is_measured_before_rasterization(compiler, tmp_path, monkeypatch, case, attempts):
    """错误自定义画布在分配巨幅PNG前恢复，正常模板无需尺寸元数据。"""
    config, generator, _ = compiler
    custom = tmp_path / "custom/native_geometry"
    custom.mkdir(parents=True)
    width, height = (50000, 50000) if case == "huge_canvas" else (470, 100)
    source = f'#set page(width:{width}pt,height:{height}pt,margin:0pt)\n#set text(font:"Noto Sans SC")\n自定义报告\n'
    if case == "huge_canvas":
        source += '#metadata((height:1))<report-size>\n'
    if case == "pages":
        source += '#pagebreak()\n第二页\n'
    (custom / "report.typ").write_text(source, encoding="utf-8")
    monkeypatch.setattr(config, "get_custom_report_template_dir", lambda name: custom)
    worker = AsyncMock(wraps=typst_renderer.run_typst_worker)
    monkeypatch.setattr(typst_renderer, "run_typst_worker", worker)
    image, html = await generator.generate_image_report(create_analysis_result(), "custom-canvas", None, template_theme="native_geometry")
    assert image and image.startswith("base64://") and html is None
    worker.assert_awaited()
    assert worker.await_count == attempts
    with Image.open(BytesIO(base64.b64decode(image.removeprefix("base64://")))) as output:
        assert output.width == 940


@pytest.mark.asyncio
async def test_high_density_survives_generator_and_history_copy(compiler, tmp_path):
    from src.infrastructure.reporting.report_image import save_report_image

    config, generator, _ = compiler
    config.config["t2i_rendering"]["t2i_rendering_strategies"][0]["raster_ppi"] = 216
    source, html = await generator.generate_image_report(create_analysis_result(), "density", None, template_theme="simple")
    assert source and html is None
    output = save_report_image(source, tmp_path / "report.jpg")
    payload = base64.b64decode(source.removeprefix("base64://"))
    assert output.suffix == ".png" and output.read_bytes() == payload
    with Image.open(output) as image:
        assert image.format == "PNG" and image.width == 1410


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["zh-Hans", "zh-Hant", "en", "ja"])
async def test_miku_title_uses_allseto_only_for_chinese_and_keeps_font_fallback(compiler, tmp_path, monkeypatch, language):
    config, generator, _ = compiler
    font = generator.data_dir / "typst/fonts/cjkFonts_allseto_v1.11.ttf"
    assert font.is_file(), "真实 Miku 编译需要按需字体清单中的全瀨體"
    config.config["basic"]["report_language"] = language
    real_worker = typst_renderer.run_typst_worker
    results = []

    async def compare(job, fonts, timeout, raster_ppi=144):
        data = json.loads((job / "data.json").read_text(encoding="utf-8"))
        assert data["miku_allseto"] is True and data["language"] == language
        metrics = await real_worker(job, fonts, timeout, raster_ppi)
        original = (job / "report.png").read_bytes()
        clone = tmp_path / "fallback"
        shutil.copytree(job, clone)
        data["miku_allseto"] = False
        (clone / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        await real_worker(clone, fonts, timeout, raster_ppi)
        results.extend([original, (clone / "report.png").read_bytes()])
        return metrics

    monkeypatch.setattr(typst_renderer, "run_typst_worker", compare)
    source, html = await generator.generate_image_report(create_analysis_result(), "allseto", None, template_theme="HatsuneMiku")
    assert source and html is None and len(results) == 2
    assert base64.b64decode(source.removeprefix("base64://")) == results[0]
    with Image.open(BytesIO(results[0])) as actual, Image.open(BytesIO(results[1])) as fallback:
        if language.startswith("zh"):
            assert 19 <= fallback.height - actual.height <= 21
            assert actual.crop((50, 75, 500, 130)).tobytes() != fallback.crop((50, 75, 500, 130)).tobytes()
        else:
            assert actual.size == fallback.size and actual.tobytes() == fallback.tobytes()
