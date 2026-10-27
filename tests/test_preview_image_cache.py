"""发送预览图的真实转码、缓存失效及路径兼容性。"""

import asyncio
import os
import logging
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from PIL import Image

from src.infrastructure.platform.template_preview import image_cache
from src.infrastructure.platform.template_preview.image_cache import PreviewImageCache


@pytest.mark.asyncio
@pytest.mark.parametrize("as_uri", [False, True])
async def test_local_webp_is_real_jpeg_and_reused(tmp_path, monkeypatch, as_uri):
    source = tmp_path / "中文 空格#图.webp"
    Image.new("RGBA", (32, 20), (255, 0, 0, 0)).save(source)
    cache = PreviewImageCache(tmp_path / "cache")
    reference = source.as_uri() if as_uri else str(source)
    first = Path(await cache.get_jpeg(reference))
    with Image.open(first) as converted:
        assert converted.format == "JPEG"
        assert converted.size == (32, 20)
        assert converted.mode == "RGB"
        assert converted.getpixel((10, 10)) == (255, 255, 255)
    assert source.exists()
    monkeypatch.setattr(cache, "_write_jpeg", lambda *_: pytest.fail("不应重复转码"))
    assert await cache.get_jpeg(reference) == str(first)


@pytest.mark.asyncio
async def test_source_update_and_concurrent_reads(tmp_path, monkeypatch):
    source = tmp_path / "demo.webp"
    Image.new("RGB", (20, 20), "red").save(source)
    cache = PreviewImageCache(tmp_path / "cache")
    writes = 0
    original_write = cache._write_jpeg

    def write(*args):
        nonlocal writes
        writes += 1
        original_write(*args)

    monkeypatch.setattr(cache, "_write_jpeg", write)
    results = await asyncio.gather(*(cache.get_jpeg(str(source)) for _ in range(5)))
    assert len(set(results)) == 1 and writes == 1
    Image.new("RGB", (21, 20), "blue").save(source)
    updated = await cache.get_jpeg(str(source))
    assert updated != results[0] and writes == 2
    with Image.open(updated) as image:
        assert image.size == (21, 20)


@pytest.mark.asyncio
async def test_remote_reuse_expiration_and_changed_cdn(tmp_path):
    calls = []
    raw = BytesIO()
    Image.new("RGB", (15, 12), "green").save(raw, format="WEBP")

    async def handler(request):
        calls.append(request.path)
        return web.Response(body=raw.getvalue(), content_type="image/webp")

    app = web.Application()
    app.router.add_get("/{name}", handler)
    cache = PreviewImageCache(tmp_path / "cache")
    async with TestServer(app) as server:
        source = str(server.make_url("/a.webp"))
        first = Path(await cache.get_jpeg(source))
        assert await cache.get_jpeg(source) == str(first)
        assert calls == ["/a.webp"]
        os.utime(first, (0, 0))
        assert await cache.get_jpeg(source) == str(first)
        assert calls == ["/a.webp", "/a.webp"]
        second = await cache.get_jpeg(str(server.make_url("/b.webp")))
        assert second != str(first)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["http_error", "html", "oversize", "pixels"])
async def test_bad_source_does_not_publish_cache(tmp_path, kind):
    cache = PreviewImageCache(tmp_path / "cache")
    cache.MAX_SOURCE_BYTES = 64
    raw = BytesIO()
    Image.new("RGB", (20, 20), "red").save(raw, format="PNG")
    if kind == "pixels":
        cache.MAX_SOURCE_BYTES = 1024
        cache.MAX_PIXELS = 1

    async def handler(_request):
        if kind == "http_error":
            return web.Response(status=403)
        if kind == "html":
            return web.Response(text="<html>CDN error</html>")
        return web.Response(body=raw.getvalue())

    app = web.Application()
    app.router.add_get("/image", handler)
    async with TestServer(app) as server:
        with pytest.raises(Exception):
            await cache.get_jpeg(str(server.make_url("/image")))
    assert not list(cache.directory.glob("*.jpg"))
    assert not list(cache.directory.glob("*.tmp"))


@pytest.mark.asyncio
async def test_cache_evicts_oldest_and_atomic_failure_cleans_up(tmp_path, monkeypatch):
    cache = PreviewImageCache(tmp_path / "cache")
    cache.MAX_ENTRIES = 2
    for i in range(3):
        source = tmp_path / f"{i}.png"
        Image.new("RGB", (12, 12), (i * 60, 0, 0)).save(source)
        await cache.get_jpeg(str(source))
    assert len(list(cache.directory.glob("*.jpg"))) == 2
    source = tmp_path / "last.png"
    Image.new("RGB", (12, 12), "red").save(source)

    def fail_replace(*_):
        raise OSError("写入失败")

    monkeypatch.setattr(
        image_cache, "os", SimpleNamespace(name=os.name, replace=fail_replace)
    )
    with pytest.raises(OSError):
        await cache.get_jpeg(str(source))
    assert len(list(cache.directory.glob("*.jpg"))) == 2
    assert not list(cache.directory.glob("*.tmp"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("file:///C:/%E4%B8%AD%E6%96%87%20a%23.webp", "C:/中文 a#.webp"),
        ("file://server/share/%E4%B8%AD%E6%96%87.webp", "//server/share/中文.webp"),
        ("file://localhost/C:/demo.webp", "C:/demo.webp"),
    ],
)
async def test_windows_file_uri_decoding_without_deprecated_module(
    tmp_path, monkeypatch, uri, expected
):
    source = tmp_path / "actual.webp"
    Image.new("RGB", (10, 10), "red").save(source)
    cache = PreviewImageCache(tmp_path / "cache")
    seen = []

    def local_path(value):
        seen.append(value)
        return source

    monkeypatch.setattr(image_cache, "Path", local_path)
    monkeypatch.setattr(
        image_cache, "os", SimpleNamespace(name="nt", replace=os.replace)
    )
    await cache.get_jpeg(uri)
    assert seen == [expected]


@pytest.mark.asyncio
async def test_cache_diagnostics_show_progress_without_resource_credentials(
    tmp_path, caplog
):
    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    raw = BytesIO()
    Image.new("RGB", (10, 10), "red").save(raw, format="PNG")

    async def handler(_request):
        return web.Response(body=raw.getvalue(), content_type="image/png")

    app = web.Application()
    app.router.add_get("/private-path", handler)
    cache = PreviewImageCache(tmp_path / "cache")
    async with TestServer(app) as server:
        source = str(server.make_url("/private-path?token=private-token")).replace(
            "http://", "http://secret-user:secret-password@"
        )
        await cache.get_jpeg(source)
        await cache.get_jpeg(source)
    messages = "\n".join(record.getMessage() for record in caplog.records)
    for expected in [
        "source_type=HTTP",
        "status=200",
        "JPEG 准备完成",
        "JPEG 缓存命中",
        "图片读取完成",
        "wait_ms=",
        "read_ms=",
        "convert_ms=",
    ]:
        assert expected in messages
    for sensitive in [
        "private-path",
        "private-token",
        "secret-user",
        "secret-password",
    ]:
        assert sensitive not in messages
    assert not [record for record in caplog.records if record.levelno == logging.INFO]


@pytest.mark.asyncio
async def test_palette_transparency_is_composited_on_white(tmp_path):
    source = tmp_path / "palette.png"
    image = Image.new("P", (12, 12), 0)
    image.putpalette([255, 0, 0] + [0, 0, 0] * 255)
    image.save(source, transparency=0)
    cache = PreviewImageCache(tmp_path / "cache")
    target = await cache.get_jpeg(str(source))
    with Image.open(target) as converted:
        assert converted.format == "JPEG" and converted.mode == "RGB"
        assert converted.getpixel((6, 6)) == (255, 255, 255)
