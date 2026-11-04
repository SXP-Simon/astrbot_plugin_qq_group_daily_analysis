"""验证长 Base64 不进入路径探测，且报告格式与持久化文件一致。"""

import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image, PngImagePlugin

from src.infrastructure.reporting.report_image import save_report_image
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.shared.trace_context import TraceContext


@pytest.fixture
def long_png():
    image = Image.new("RGB", (16, 16), "white")
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("sample", "x" * 10000)
    buffer = BytesIO()
    image.save(buffer, format="PNG", pnginfo=metadata)
    return buffer.getvalue()


@pytest.mark.parametrize("kind", ["base64", "data_uri", "local"])
@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
def test_report_copy_uses_real_format_without_treating_uri_as_path(tmp_path, monkeypatch, long_png, kind, image_format):
    if image_format == "PNG":
        data = long_png
    else:
        buffer = BytesIO()
        Image.new("RGB", (16, 16), "white").save(buffer, format="JPEG")
        data = buffer.getvalue()
    source = tmp_path / "source.wrong"
    source.write_bytes(data)
    value = str(source) if kind == "local" else ("base64://" if kind == "base64" else "data:image/jpeg;base64,") + base64.b64encode(data).decode()
    real_exists = Path.exists

    def reject_encoded_path(path):
        assert not str(path).startswith(("base64:", "data:image"))
        return real_exists(path)

    monkeypatch.setattr(Path, "exists", reject_encoded_path)
    saved = save_report_image(value, tmp_path / "report.jpg")
    assert saved.suffix == (".png" if image_format == "PNG" else ".jpg")
    assert saved.read_bytes() == data
    with Image.open(saved) as image:
        assert image.format == image_format


@pytest.mark.parametrize("source", ["base64://", "base64://not base64!", "data:image/png,plain", "https://example.test/image.png"])
def test_invalid_source_does_not_create_phantom_report(tmp_path, source):
    with pytest.raises(ValueError):
        save_report_image(source, tmp_path / "report.jpg")
    assert list(tmp_path.iterdir()) == []


def test_existing_report_can_be_used_without_copying_onto_itself(tmp_path, long_png):
    source = tmp_path / "report.png"
    source.write_bytes(long_png)
    assert save_report_image(str(source), source) == source


@pytest.mark.asyncio
async def test_scheduled_delivery_saves_png_and_registers_only_existing_artifact(tmp_path, monkeypatch, long_png):
    uri = "base64://" + base64.b64encode(long_png).decode()
    config = MagicMock()
    config.get_t2i_rendering_strategy_config.return_value = [{"render_service": "typst"}]
    config.get_show_report_caption.return_value = False
    sender = MagicMock()
    sender.send_image_smart = AsyncMock(return_value=True)
    generator = SimpleNamespace(data_dir=tmp_path, generate_image_report=AsyncMock(return_value=(uri, None)))
    dispatcher = ReportDispatcher(config, generator, sender)
    dispatcher._try_upload_image = AsyncMock()
    trace = TraceContext(trace_id="scheduled-image", group_id="GROUP")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(trace, "persist_snapshot_async", AsyncMock())
    assert await dispatcher._dispatch_image("GROUP", {}, "test")
    sender.send_image_smart.assert_awaited_once_with("GROUP", uri, "", "test")
    report = trace.metadata["report_files"][0]
    assert report["filename"].endswith(".png")
    assert Path(report["path"]).read_bytes() == long_png
    assert report["size_bytes"] == len(long_png)
