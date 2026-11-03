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
from src.shared.trace_context import TraceContext


def png_bytes():
    stream = BytesIO()
    Image.new("RGB", (12, 12), "#39c5bb").save(stream, format="PNG")
    return stream.getvalue()


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


def test_typst_never_prepares_html_and_sanitizes_snapshot(native, monkeypatch):
    directory = native.data_dir / "typst/fonts"
    directory.mkdir(parents=True)
    (directory / "test.ttf").write_bytes(b"font")
    captured = {}
    async def worker(job, fonts, timeout):
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
        image, html = await native.generate_image_report(result, "123456", host, hide_user_names=True)
        assert image.startswith("base64://") and html is None
        assert base64.b64decode(image.removeprefix("base64://")) == png_bytes()
        exported = json.dumps(captured, ensure_ascii=False)
        assert "123456" not in exported and "张三" not in exported
        assert '#read' in exported and '<script>' in exported
        assert [dim["color"] for dim in captured["review"]["dimensions"]] == ["#12aBcF", "#abc", "#607d8b"]
        assert not list((native.data_dir / "typst/jobs").iterdir())
        host.assert_not_called()
        native._prepare_render_data.assert_not_called()
        await native.close()
    asyncio.run(check())


@pytest.mark.parametrize("cancel", [False, True])
def test_worker_is_dead_before_timeout_or_cancel_returns(tmp_path, monkeypatch, cancel):
    async def check():
        stopped = asyncio.Event()
        class Process:
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


