"""发布环境的 CDN 下载、缓存与受管理字体落盘。"""

import asyncio
import base64
from io import BytesIO
from unittest.mock import MagicMock

import aiohttp
from aiohttp import web
from PIL import Image
import pytest

from src.infrastructure.reporting import typst_fonts, typst_resources


def test_oval_avatar_keeps_normal_avatar_and_cache_separate(tmp_path):
    async def check():
        payload = BytesIO()
        Image.new("RGBA", (12, 12), (57, 197, 187, 255)).save(payload, format="PNG")
        source = "data:image/png;base64," + base64.b64encode(payload.getvalue()).decode()
        job = tmp_path / "job"
        job.mkdir()
        async with aiohttp.ClientSession() as session:
            assets = typst_resources.TypstAssets(tmp_path, job, session)
            normal = await assets.localize(source)
            oval = await assets.localize(source, oval=True)
            assert normal != oval
            assert await assets.localize(source, oval=True) == oval
            with Image.open(job / normal) as image:
                assert image.size == (12, 12) and image.getpixel((0, 0))[3] == 255
            with Image.open(job / oval) as image:
                assert image.width / image.height == 5 / 6
                assert image.getpixel((0, 0))[3] == 0
                assert image.getpixel((image.width // 2, image.height // 2))[3] == 255
    asyncio.run(check())


def test_cdn_cache_works_without_development_assets(tmp_path, monkeypatch):
    async def check():
        payload = BytesIO()
        Image.new("RGBA", (12, 12), (57, 197, 187, 200)).save(payload, format="PNG")
        calls = []
        async def resource(request):
            calls.append(request.path)
            return web.Response(body=payload.getvalue(), content_type="image/png")
        app = web.Application()
        app.router.add_get("/role.png", resource)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        url = f"http://127.0.0.1:{runner.addresses[0][1]}/role.png"
        try:
            async with aiohttp.ClientSession() as session:
                job = tmp_path / "job-one"
                job.mkdir()
                assets = typst_resources.TypstAssets(tmp_path, job, session)
                image = job / await assets.localize(url, .25)
                assert Image.open(image).getpixel((0,0))[3] == 50
            await runner.cleanup()
            import os
            for file in (tmp_path / "typst/assets").glob("*.png"):
                os.utime(file, (1, 1))
            async with aiohttp.ClientSession() as session:
                network = MagicMock(side_effect=AssertionError("已有本地图片不应联网刷新"))
                monkeypatch.setattr(session, "get", network)
                job = tmp_path / "job-two"
                job.mkdir()
                assets = typst_resources.TypstAssets(tmp_path, job, session)
                image = job / await assets.localize(url, .25)
                assert Image.open(image).getpixel((0,0))[3] == 50
                assert await assets.localize(url, .25) == image.name
                network.assert_not_called()
            assert calls == ["/role.png"]
        finally:
            await runner.cleanup()
    asyncio.run(check())


def test_bad_font_response_leaves_no_partial_files(tmp_path, monkeypatch):
    monkeypatch.setattr(typst_fonts, "FONT_SOURCES", {"Noto.ttf": "font.ttf"})
    async def check():
        app = web.Application()
        async def not_a_font(request):
            return web.Response(text="<html>CDN error</html>")
        app.router.add_get("/font.ttf", not_a_font)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        try:
            with pytest.raises(ValueError):
                await typst_resources.download_typst_fonts(tmp_path, f"http://127.0.0.1:{runner.addresses[0][1]}")
            assert list((tmp_path / "typst/fonts").iterdir()) == []
            assert typst_resources.typst_font_status(tmp_path)["missing"] == ["Noto.ttf"]
        finally:
            await runner.cleanup()
    asyncio.run(check())


@pytest.mark.parametrize("status", [200, 503])
def test_bad_optional_image_is_replaced_with_empty_resource(tmp_path, status):
    async def check():
        app = web.Application()
        async def broken_image(request):
            return web.Response(status=status, text="<html>CDN error</html>")
        app.router.add_get("/role.png", broken_image)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        job = tmp_path / "job"
        job.mkdir()
        try:
            async with aiohttp.ClientSession() as session:
                assets = typst_resources.TypstAssets(tmp_path, job, session)
                url = f"http://127.0.0.1:{runner.addresses[0][1]}/role.png"
                assert await assets.localize(url) == ""
                assert not list(job.iterdir())
                assert not list((tmp_path / "typst/assets").glob("*.png"))
        finally:
            await runner.cleanup()
    asyncio.run(check())


@pytest.mark.asyncio
@pytest.mark.parametrize("decoder_fails", [False, True])
async def test_cancelled_image_waits_for_decoder_before_releasing_job(tmp_path, monkeypatch, decoder_fails):
    import threading

    started, finish = threading.Event(), threading.Event()
    original = typst_resources.TypstAssets._save_image
    def process(*args, **kwargs):
        started.set()
        finish.wait(5)
        if decoder_fails:
            raise ValueError("取消清理时图片解码失败")
        original(*args, **kwargs)
    monkeypatch.setattr(typst_resources.TypstAssets, "_save_image", staticmethod(process))
    payload = BytesIO()
    Image.new("RGB", (12, 12), "white").save(payload, format="PNG")
    source = "data:image/png;base64," + base64.b64encode(payload.getvalue()).decode()
    job = tmp_path / "job"
    job.mkdir()
    async with aiohttp.ClientSession() as session:
        assets = typst_resources.TypstAssets(tmp_path, job, session)
        running = asyncio.create_task(assets.localize(source))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            running.cancel()
            await asyncio.sleep(.01)
            assert not running.done()
        finally:
            finish.set()
        with pytest.raises(asyncio.CancelledError):
            await running
        assert bool(list(job.glob("*.png"))) is not decoder_fails
        assert not list((tmp_path / "typst/assets").glob("*.part"))


@pytest.fixture
def oversized_avatar_uri():
    """构造只有小体积载荷、但声明巨大像素面的 PNG，不分配大图。"""
    import struct
    import zlib

    payload = BytesIO()
    Image.new("RGB", (1, 1), "white").save(payload, format="PNG")
    png = bytearray(payload.getvalue())
    png[16:24] = struct.pack(">II", 40000, 40000)
    png[29:33] = struct.pack(">I", zlib.crc32(png[12:29]))
    return "data:image/png;base64," + base64.b64encode(png).decode()


@pytest.mark.asyncio
async def test_oversized_image_falls_back_and_download_validation_rejects(tmp_path, oversized_avatar_uri):
    from src.infrastructure.reporting.template_resources import TemplateResourceStore

    job = tmp_path / "job"
    job.mkdir()
    async with aiohttp.ClientSession() as session:
        assets = typst_resources.TypstAssets(tmp_path, job, session)
        assert await assets.localize(oversized_avatar_uri) == ""
        assert not list(job.iterdir())
        assert not list((tmp_path / "typst/assets").iterdir())
    downloaded = tmp_path / "oversized.png"
    downloaded.write_bytes(base64.b64decode(oversized_avatar_uri.split(",", 1)[1]))
    with pytest.raises(ValueError, match="像素预算"):
        TemplateResourceStore._validate(downloaded, "scrapbook/assistant.jpg")


@pytest.mark.asyncio
async def test_theme_font_download_skips_other_themes_and_reuses_shared_files(tmp_path, monkeypatch):
    required = typst_fonts.THEME_FONTS["HatsuneMiku"]
    directory = tmp_path / "typst/fonts"
    directory.mkdir(parents=True)
    payload = b"\x00\x01\x00\x00" + bytes(1024)
    for name in required:
        if name != "Outfit.ttf":
            (directory / name).write_bytes(payload)
    calls = []
    async def font(request):
        calls.append(request.path)
        return web.Response(body=payload)
    app = web.Application()
    app.router.add_get("/outfit.ttf", font)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    monkeypatch.setattr(typst_fonts, "FONT_SOURCES", {**typst_fonts.FONT_SOURCES, "Outfit.ttf": "outfit.ttf"})
    try:
        cdn = f"http://127.0.0.1:{runner.addresses[0][1]}"
        status = await typst_resources.download_typst_fonts(tmp_path, cdn, "HatsuneMiku")
        selected = next(group for group in status["groups"] if group["theme"] == "HatsuneMiku")
        assert selected["ready"] and not selected["missing"]
        assert not status["ready"] and "Cinzel.ttf" in status["missing"]
        await typst_resources.download_typst_fonts(tmp_path, cdn, "HatsuneMiku")
        assert calls == ["/outfit.ttf"]
        with pytest.raises(ValueError, match="未知"):
            await typst_resources.download_typst_fonts(tmp_path, cdn, "../../outside")
    finally:
        await runner.cleanup()
