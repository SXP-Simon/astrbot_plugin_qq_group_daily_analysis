"""验证 QQ 官方原生概览图发送与完整文字恢复。"""

import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from test_template_section_conditional_rendering import create_analysis_result
from test_typst_compilation import managed_fonts as managed_fonts

from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.platform.adapters.qq_official_adapter import QQOfficialAdapter
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.infrastructure.reporting.generators import ReportGenerator
from src.shared.trace_context import TraceContext


def generator_at(data_dir):
    config = object.__new__(ConfigManager)
    config.config = {"t2i_rendering": {"t2i_rendering_strategies": [{"__template_key": "typst", "timeout": 30000}]}}
    return ReportGenerator(config, data_dir)


@pytest.mark.asyncio
async def test_native_overview_real_png_and_markdown_delivery(managed_fonts, monkeypatch):
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: None))
    generator = generator_at(managed_fonts)
    images = []
    messages = []

    async def upload_image(payload):
        with Image.open(BytesIO(payload)) as image:
            assert image.format == "PNG"
            assert image.size == (940, 423)
            assert image.convert("RGBA").getpixel((0, 0))[3] == 0
            assert image.convert("RGBA").getchannel("A").getextrema() == (0, 255)
        images.append(payload)
        return "qqbot-media://image/v1/summary_token"

    async def post_message(**kwargs):
        assert images, "必须先上传概览素材，才能在正文内引用"
        messages.append(kwargs)
        return {"id": "REPORT"}

    adapter = QQOfficialAdapter(SimpleNamespace(api=SimpleNamespace(post_group_message=post_message), platform=None))
    adapter.upload_markdown_image = upload_image
    adapter.send_image = AsyncMock(side_effect=AssertionError("不得拆成独立图片消息"))
    sender = SimpleNamespace(bot_manager=SimpleNamespace(get_adapter=lambda _: adapter))
    dispatcher = ReportDispatcher(generator.config_manager, generator, sender)
    dispatcher._html_render_func = AsyncMock(side_effect=AssertionError("Typst 不应调用 HTML 渲染"))
    assert await dispatcher._dispatch_text("GROUP", create_analysis_result(), "official")
    assert len(images) == 1
    assert len(messages) == 1
    assert "qqbot-media://image/v1/summary_token" in messages[0]["markdown"]["content"]
    assert messages[0]["markdown"]["force_verify_image_resource"] is True
    content = "\n".join(item["markdown"]["content"] for item in messages)
    assert "热门话题" in content
    assert "基础统计" not in content
    assert "base64" not in content
    assert "file://" not in content
    assert not list((managed_fonts / "typst/jobs").glob("qq-summary-*"))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["compile", "upload_none", "upload_error", "no_sender", "invalid_reference"])
async def test_native_failure_retains_all_statistics(tmp_path, monkeypatch, failure):
    generator = generator_at(tmp_path)
    render = AsyncMock(return_value=b"png")
    if failure == "compile":
        render.side_effect = RuntimeError("missing fonts")
    monkeypatch.setattr("src.infrastructure.reporting.markdown_report_generator.render_native_summary", render)
    sender = AsyncMock(return_value=None)
    if failure == "invalid_reference":
        sender.return_value = "file:///private/image.png"
    if failure == "upload_error":
        sender.side_effect = RuntimeError("QQ unavailable")
    body, fallback = await generator.generate_markdown_report(
        create_analysis_result(), mention_style="qq",
        summary_image_uploader=None if failure == "no_sender" else sender,
    )
    assert body == fallback
    assert "基础统计" in body
    assert "消息总数" in body
    assert "热门话题" in body
    if failure in {"compile", "no_sender"}:
        sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_native_cancellation_propagates_and_releases_slot(tmp_path, monkeypatch):
    generator = generator_at(tmp_path)
    generator._markdown_generator.render_semaphore = asyncio.Semaphore(1)
    started = asyncio.Event()

    async def render(*args):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr("src.infrastructure.reporting.markdown_report_generator.render_native_summary", render)
    sender = AsyncMock()
    task = asyncio.create_task(generator.generate_markdown_report(
        create_analysis_result(), mention_style="qq", summary_image_uploader=sender,
    ))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    sender.assert_not_awaited()
    assert not generator._markdown_generator.render_semaphore.locked()
