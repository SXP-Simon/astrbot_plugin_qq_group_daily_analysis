"""独立渲染的匿名处理与编译进程回收行为。"""

import asyncio
import base64
import json
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from test_template_section_conditional_rendering import create_analysis_result

from src.domain.value_objects import QualityDimension, QualityReview
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.reporting.generators import ReportGenerator
from src.infrastructure.reporting.typst_renderer import run_typst_worker
from src.infrastructure.reporting.typst_resources import TypstAssets
from src.infrastructure.reporting.typst_process import TypstWorkerError, TypstWorkerTimeoutError
from src.shared.trace_context import TraceContext


def png_bytes():
    stream = BytesIO()
    Image.new("RGB", (12, 12), "#39c5bb").save(stream, format="PNG")
    return stream.getvalue()


@pytest.mark.asyncio
async def test_failed_worker_preserves_validated_metrics(tmp_path, monkeypatch):
    trace = TraceContext(trace_id="failed-worker-metrics")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(TraceContext, "_enable_metrics", True)

    class Process:
        returncode = 1

        async def communicate(self):
            return b'{"layout_ms":17,"worker_peak_rss_mb":103,"unexpected":999}', b"invalid template"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=Process()))
    with pytest.raises(TypstWorkerError) as error:
        await run_typst_worker(tmp_path, tmp_path / "fonts", 1)
    assert error.value.metrics == {"layout_ms": 17, "worker_peak_rss_mb": 103}


@pytest.fixture
def native(tmp_path, monkeypatch):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    config = object.__new__(ConfigManager)
    config.config = {"basic": {"report_template": "HatsuneMiku", "profile_display_mode": "mbti"},
                     "t2i_rendering": {"t2i_rendering_strategies": [{"__template_key": "typst", "timeout": 30000}]}}
    generator = ReportGenerator(config, tmp_path)
    generator._avatar_service.get_user_avatar = AsyncMock(return_value="")
    monkeypatch.setattr(TypstAssets, "localize", AsyncMock(return_value=""))
    return generator


@pytest.mark.parametrize("theme", ["HatsuneMiku", "BlueArchive"])
def test_typst_never_prepares_html_and_sanitizes_snapshot(native, monkeypatch, theme):
    directory = native.data_dir / "typst/fonts"
    directory.mkdir(parents=True)
    (directory / "test.ttf").write_bytes(b"font")
    captured = {}
    async def worker(job, fonts, timeout, raster_ppi=144):
        captured.update(json.loads((job / "data.json").read_text(encoding="utf-8")))
        (job / "report.png").write_bytes(png_bytes())
        assert fonts == directory
    monkeypatch.setattr("src.infrastructure.reporting.typst_renderer.run_typst_worker", worker)
    native._prepare_render_data = AsyncMock(side_effect=AssertionError("不应准备 HTML"))
    host = AsyncMock(side_effect=AssertionError("不应调用宿主"))
    result = create_analysis_result()
    result["user_analysis"] = {"123456": {"nickname": "张三"}}
    result["topics"][0].detail = "[123456] 张三 #read(\"/secret\") <script>"
    result["chat_quality_review"] = QualityReview(
        title="评价", subtitle="", summary="内容",
        dimensions=[QualityDimension(name="自定义颜色", percentage=40, comment="", color="#12aBcF"),
                    QualityDimension(name="短色值", percentage=30, comment="", color="#abc"),
                    QualityDimension(name="异常颜色", percentage=30, comment="", color='red); panic("invalid")')],
    )
    async def check():
        image, html = await native.generate_image_report(result, "123456", host, hide_user_names=True, template_theme=theme)
        assert image.startswith("base64://") and html is None
        assert base64.b64decode(image.removeprefix("base64://")) == png_bytes()
        exported = json.dumps(captured, ensure_ascii=False)
        assert "123456" not in exported and "张三" not in exported
        assert '#read' in exported and '<script>' in exported
        assert [dim["color"] for dim in captured["review"]["dimensions"]] == ["#12aBcF", "#abc", "#607d8b"]
        assert not list((native.data_dir / "typst/jobs").iterdir())
        host.assert_not_called()
        native._prepare_render_data.assert_not_called()
        if theme == "BlueArchive":
            sources = {call.args[0] for call in TypstAssets.localize.await_args_list}
            assert any(source.endswith("/BlueArchive/arona.png") for source in sources)
            assert any(source.endswith("/BlueArchive/arona-review.png") for source in sources)
        await native.close()
    asyncio.run(check())


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["Mainland", "Overseas"])
async def test_native_fonts_and_trace_do_not_inherit_html_environment(native, monkeypatch, environment):
    from src.infrastructure.reporting import typst_data

    monkeypatch.setattr(typst_data, "resolve_report_language", lambda _: None)
    native.config_manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]["environment"] = environment
    fonts = native.data_dir / "typst/fonts"
    fonts.mkdir(parents=True)
    (fonts / "test.ttf").write_bytes(b"font")
    trace = TraceContext(trace_id=f"native-environment-{environment}")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    captured = {}

    async def worker(job, font_dir, timeout, raster_ppi=144):
        captured.update(json.loads((job / "data.json").read_text(encoding="utf-8")))
        (job / "report.png").write_bytes(png_bytes())

    monkeypatch.setattr("src.infrastructure.reporting.typst_renderer.run_typst_worker", worker)
    try:
        with trace.span("RENDER_REPORT") as parent:
            assert (await native.generate_image_report(create_analysis_result(), "test", None))[0]
        attempt = next(span for span in trace._spans if span["stage_name"] == "IMAGE_RENDER_ATTEMPT")
        record = parent["payload"]["render_attempts"][0]
        assert captured["font_language"] == captured["language"] == "zh-Hans"
        for payload in (parent["payload"], attempt["payload"], record):
            assert "resource_environment" not in payload
            assert payload["execution_location"] == "本地隔离进程"
            assert "本地优先" in payload["asset_policy"]
        assert record["font_mode"] == "local"
    finally:
        await native.close()


@pytest.mark.parametrize("cancel", [False, True])
def test_worker_is_dead_before_timeout_or_cancel_returns(tmp_path, monkeypatch, cancel):
    async def check():
        stopped = asyncio.Event()
        class Process:
            pid = 0
            returncode = None
            async def communicate(self):
                await stopped.wait()
                return None, b""
            def kill(self):
                self.returncode = -9
                stopped.set()
        process = Process()
        monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
        task = asyncio.create_task(run_typst_worker(tmp_path, tmp_path / "fonts", 1 if cancel else .01))
        if cancel:
            await asyncio.sleep(.01)
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
            await task
        assert process.returncode == -9 and stopped.is_set()
    asyncio.run(check())


@pytest.mark.asyncio
async def test_cancellation_does_not_start_recovery(native, monkeypatch):
    directory = native.data_dir / "typst/fonts"
    directory.mkdir(parents=True)
    (directory / "test.ttf").write_bytes(b"font")
    worker = AsyncMock(side_effect=asyncio.CancelledError())
    monkeypatch.setattr("src.infrastructure.reporting.typst_renderer.run_typst_worker", worker)
    try:
        with pytest.raises(asyncio.CancelledError):
            await native.generate_image_report(create_analysis_result(), "test", None)
        worker.assert_awaited_once()
        assert not list((native.data_dir / "typst/jobs").iterdir())
    finally:
        await native.close()


@pytest.mark.asyncio
async def test_theme_has_full_compile_budget_and_recovery_uses_separate_limit(native, monkeypatch):
    native.config_manager.config["t2i_rendering"]["t2i_rendering_strategies"][0].update(timeout=2000, raster_ppi=216)
    fonts = native.data_dir / "typst/fonts"
    fonts.mkdir(parents=True)
    (fonts / "test.ttf").write_bytes(b"font")
    trace = TraceContext(trace_id="timeout-recovers-image")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    calls = []

    async def worker(job, directory, timeout, raster_ppi=144):
        calls.append((timeout, raster_ppi))
        if len(calls) == 1:
            from src.infrastructure.reporting.render_trace import render_span
            async with render_span("IMAGE_RENDER_QUEUE", {"scope": "native_compile"}):
                async with asyncio.timeout(timeout):
                    await asyncio.Event().wait()
        async with asyncio.timeout(timeout):
            # 模拟冷启动与排版，恢复重新使用完整编译时限，不再沿用主题耗尽后的余额。
            await asyncio.sleep(.5)
            assert "恢复版独立" in (job / "main.typ").read_text(encoding="utf-8")
            (job / "report.png").write_bytes(png_bytes())
        return {"raster_ppi": raster_ppi}

    monkeypatch.setattr("src.infrastructure.reporting.typst_renderer.run_typst_worker", worker)
    try:
        image, html = await native.generate_image_report(create_analysis_result(), "test", None)
        assert image and image.startswith("base64://") and html is None
        assert [call[1] for call in calls] == [216, 144]
        assert [call[0] for call in calls] == [2, 2]
        spans = {span["stage_name"]: span for span in trace._spans}
        assert spans["TYPST_COMPILE"]["status"] == "warning"
        assert "主题编译超过" in spans["TYPST_COMPILE"]["payload"]["failure_reason"]
        assert spans["TYPST_RECOVERY"]["status"] == "success"
        assert spans["TYPST_RECOVERY"]["payload"]["original_raster_ppi"] == 216
        from src.domain.value_objects.task_event import TaskEvent
        trace.finish(TaskEvent.SUCCEED)
        assert trace.status == "warning"
    finally:
        await native.close()


@pytest.mark.asyncio
async def test_real_timeout_keeps_last_metrics_and_terminates_process(tmp_path, monkeypatch):
    import sys
    from src.infrastructure.reporting import typst_process

    trace = TraceContext(trace_id="timeout-partial-metrics")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(TraceContext, "_enable_metrics", True)
    real_spawn = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        program = 'import sys,time,json; block=bytearray(16*1024*1024); print(json.dumps({"worker_phase":"raster","font_setup_ms":12,"layout_ms":25,"raster_ppi":216,"worker_start_rss_mb":8}),flush=True); time.sleep(60)'
        process = await real_spawn(sys.executable, "-u", "-c", program, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(TypstWorkerTimeoutError, match="栅格导出.*216 PPI") as caught:
        await typst_process.run_typst_worker(tmp_path, tmp_path / "fonts", 2, 216)
    assert processes[0].returncode is not None
    assert caught.value.metrics["layout_ms"] == 25
    assert caught.value.metrics["worker_metrics_partial"] is True
    assert caught.value.metrics["worker_phase"] == "raster"




@pytest.mark.asyncio
async def test_custom_typst_keeps_relative_modules_and_isolated_root(native, tmp_path, monkeypatch):
    """自定义主模板和子目录导入一起进入隔离任务目录。"""
    from src.infrastructure.reporting.typst_renderer import TypstReportRenderer

    fonts = native.data_dir / "typst/fonts"
    fonts.mkdir(parents=True)
    (fonts / "test.ttf").write_bytes(b"font")
    custom = tmp_path / "custom/native"
    (custom / "parts").mkdir(parents=True)
    (custom / "report.typ").write_text('#import "parts/card.typ": card', encoding="utf-8")
    (custom / "data.json").write_text("invalid", encoding="utf-8")
    (custom / "main.typ").write_text("invalid", encoding="utf-8")
    (custom / "parts/card.typ").write_text('#let card = [hello]', encoding="utf-8")
    monkeypatch.setattr(native.config_manager, "get_custom_report_template_dir", lambda _: custom)
    async def worker(job, font_dir, timeout, raster_ppi=144):
        assert (job / "main.typ").read_text(encoding="utf-8") == '#import "parts/card.typ": card'
        assert (job / "parts/card.typ").is_file()
        assert json.loads((job / "data.json").read_text(encoding="utf-8"))["message_count"] >= 0
        (job / "report.png").write_bytes(png_bytes())
    monkeypatch.setattr("src.infrastructure.reporting.typst_renderer.run_typst_worker", worker)
    try:
        renderer = TypstReportRenderer(native.config_manager, native.data_dir, native._avatar_service, {})
        result = await renderer.render(create_analysis_result(), "native", {})
        assert result == png_bytes()
    finally:
        await native.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["avatar", "nickname"])
async def test_optional_network_timeout_preserves_report_text(native, monkeypatch, boundary):
    fonts = native.data_dir / "typst/fonts"
    fonts.mkdir(parents=True)
    (fonts / "test.ttf").write_bytes(b"font")
    native.config_manager.config["t2i_rendering"]["t2i_rendering_strategies"][0]["timeout"] = 1000
    async def unavailable(*args):
        await asyncio.Event().wait()
        return ""
    if boundary == "avatar":
        native._avatar_service.get_user_avatar.side_effect = unavailable
    captured = {}
    async def worker(job, font_dir, timeout, raster_ppi=144):
        captured.update(json.loads((job / "data.json").read_text(encoding="utf-8")))
        assert list(job.glob("*.svg")), "网络预算过期后仍需使用本地图标"
        (job / "report.png").write_bytes(png_bytes())
    monkeypatch.setattr("src.infrastructure.reporting.typst_renderer.run_typst_worker", worker)
    data = create_analysis_result()
    data["topics"][0].detail = "要保留的完整正文 [999999] #text(不能执行)"
    image, html = await native.generate_image_report(data, "optional-network", None, nickname_getter=unavailable if boundary == "nickname" else None)
    assert image and html is None
    assert "要保留的完整正文" in json.dumps(captured, ensure_ascii=False)
    assert not list((native.data_dir / "typst/jobs").iterdir())
    await native.close()


@pytest.mark.asyncio
async def test_cancel_during_avatar_preparation_does_not_recover_or_send(native, monkeypatch):
    fonts = native.data_dir / "typst/fonts"
    fonts.mkdir(parents=True)
    (fonts / "test.ttf").write_bytes(b"font")
    entered = asyncio.Event()
    async def wait_for_avatar(*args):
        entered.set()
        await asyncio.Event().wait()
        return ""
    native._avatar_service.get_user_avatar.side_effect = wait_for_avatar
    worker = AsyncMock()
    monkeypatch.setattr("src.infrastructure.reporting.typst_renderer.run_typst_worker", worker)
    running = asyncio.create_task(native.generate_image_report(create_analysis_result(), "cancel-input", None))
    try:
        await entered.wait()
        running.cancel()
        with pytest.raises(asyncio.CancelledError):
            await running
        worker.assert_not_called()
        assert not list((native.data_dir / "typst/jobs").iterdir())
    finally:
        await native.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_native_trace_tracks_stages_and_cancel(native, monkeypatch, cancel):
    native.config_manager.config["basic"]["report_language"] = "zh-Hans"
    from src.domain.value_objects.task_event import TaskEvent
    trace = TraceContext(trace_id=f"native-stages-{cancel}", group_id="test")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    fonts = native.data_dir / "typst/fonts"
    fonts.mkdir(parents=True)
    (fonts / "test.ttf").write_bytes(b"font")
    async def worker(job, font_dir, timeout, raster_ppi=144):
        if cancel:
            raise asyncio.CancelledError()
        (job / "report.png").write_bytes(png_bytes())
        return {"worker_peak_rss_mb": 120.5, "layout_ms": 12.0}
    monkeypatch.setattr("src.infrastructure.reporting.typst_renderer.run_typst_worker", worker)
    try:
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                await native.generate_image_report(create_analysis_result(), "test", None)
        else:
            assert (await native.generate_image_report(create_analysis_result(), "test", None))[0]
        trace.finish(TaskEvent.CANCEL if cancel else TaskEvent.SUCCEED)
        spans = trace.to_dict()["spans"]
        assert [span["stage_name"] for span in spans] == ["IMAGE_RENDER_QUEUE", "IMAGE_RENDER_ATTEMPT", "TYPST_VALIDATE", "TYPST_DATA", "TYPST_RESOURCES", "TYPST_COMPILE"] + ([] if cancel else ["TYPST_ENCODE"])
        compile_span = next(span for span in spans if span["stage_name"] == "TYPST_COMPILE")
        assert compile_span["status"] == ("cancelled" if cancel else "success")
        assert compile_span["payload"]["parent_span_id"] == spans[1]["span_id"]
        if not cancel:
            assert compile_span["payload"]["worker_peak_rss_mb"] == 120.5
        assert trace.status == ("aborted" if cancel else "warning")
        resources = next(span for span in spans if span["stage_name"] == "TYPST_RESOURCES")
        assert resources["payload"]["title_font"] in ("Noto Sans SC", "Noto Sans TC")
        assert "全瀨體尚未下载" in resources["payload"]["warning"]
    finally:
        await native.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_worker_telemetry_follows_existing_switch(tmp_path, monkeypatch, enabled):
    trace = TraceContext(trace_id="worker-metrics", group_id="test")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(TraceContext, "_enable_metrics", enabled)
    class Process:
        returncode = 0
        async def communicate(self):
            return b'{"worker_peak_rss_mb":120.5,"layout_ms":12,"raster_ms":-1,"font_setup_ms":true}', b""
    create = AsyncMock(return_value=Process())
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    metrics = await run_typst_worker(tmp_path, tmp_path / "fonts", 1)
    assert ("--metrics" in create.call_args.args) is enabled
    assert metrics == ({"worker_peak_rss_mb":120.5, "layout_ms":12.0} if enabled else None)
