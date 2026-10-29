"""漫画参考图加载的输入边界与文件路径回归。"""

import threading
from pathlib import Path

import pytest

from src.application.services.comic_application_service import ComicApplicationService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reference",
    [
        "data:image/png;base64,!!!",
        "data:image/png;base64,",
        "data:image/png;base64",
        "data:image/png;base64,aW1hZ2U=!!!",
        "base64://!!!",
        "base64://",
        "base64://aW1hZ2U=!!!",
    ],
)
async def test_reference_rejects_empty_or_malformed_base64(reference):
    service = object.__new__(ComicApplicationService)
    assert await service._fetch_reference_image(reference) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reference,mime",
    [
        ("data:image/webp;base64,aW1hZ2U=", "image/webp"),
        ("base64://aW1hZ2U=", "image/png"),
    ],
)
async def test_reference_preserves_valid_base64(reference, mime):
    service = object.__new__(ComicApplicationService)
    assert await service._fetch_reference_image(reference) == (b"image", mime)


@pytest.mark.asyncio
async def test_local_reference_scan_and_read_runs_outside_event_loop(tmp_path, monkeypatch):
    service = object.__new__(ComicApplicationService)
    service.plugin_data_dir = tmp_path
    directory = tmp_path / "files" / "uploaded"
    directory.mkdir(parents=True)
    (directory / "reference.png").write_bytes(b"image")
    event_loop_thread = threading.get_ident()
    real_read_bytes, real_rglob = Path.read_bytes, Path.rglob

    def read_bytes(path):
        assert threading.get_ident() != event_loop_thread
        return real_read_bytes(path)

    def rglob(path, pattern):
        assert threading.get_ident() != event_loop_thread
        return real_rglob(path, pattern)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "rglob", rglob)
    assert await service._fetch_reference_image("reference.png") == (b"image", "image/png")


@pytest.mark.asyncio
async def test_local_reference_preserves_absolute_path(tmp_path, monkeypatch):
    data, working, external = (tmp_path / name for name in ("data", "working", "external"))
    for directory in (data, working, external):
        directory.mkdir()
    reference = external / "reference.png"
    reference.write_bytes(b"external-image")
    monkeypatch.chdir(working)
    service = object.__new__(ComicApplicationService)
    service.plugin_data_dir = data
    assert await service._fetch_reference_image(str(reference)) == (b"external-image", "image/png")
