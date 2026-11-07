"""发布环境的 CDN 下载、缓存与受管理字体落盘。"""

import asyncio
import base64
import os
from io import BytesIO
from unittest.mock import MagicMock

import aiohttp
from aiohttp import web
from PIL import Image
import pytest

from src.infrastructure.reporting import typst_fonts, typst_resources


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["Outfit.ttf", "cjkFonts-AllSeto-Title-v1.11.ttf"])
async def test_font_file_download_is_limited_to_the_selected_preset(tmp_path, monkeypatch, filename):
    monkeypatch.setattr(typst_fonts, "REPOSITORY_TITLE_FONT", tmp_path / "absent.ttf")
    calls = []

    async def download(session, url, target, on_progress=None):
        calls.append(target.name)
        target.write_bytes(b"\x00\x01\x00\x00" + bytes(1024))

    monkeypatch.setattr(typst_fonts, "_download_font", download)
    status = await typst_fonts.download_typst_fonts(tmp_path, "https://cdn.test", "HatsuneMiku", name=filename)
    assert calls == [filename]
    assert status["files"] == [filename]
    presets = {item["name"]: item for item in status["presets"]}
    assert set(presets) == set(typst_fonts.FONT_SOURCES)
    assert presets["LXGWWenKai.ttf"] == {
        "name": "LXGWWenKai.ttf",
        "download_url": "https://raw.githubusercontent.com/lxgw/LxgwWenKai/v1.522/fonts/TTF/LXGWWenKai-Regular.ttf",
        "upstream_url": "https://github.com/lxgw/LxgwWenKai/blob/v1.522/fonts/TTF/LXGWWenKai-Regular.ttf",
        "cdn_path": None,
    }
    assert presets["Outfit.ttf"]["cdn_path"] == typst_fonts.FONT_SOURCES["Outfit.ttf"]
    for name in ("../outside.ttf", "Cinzel.ttf"):
        with pytest.raises(ValueError, match="字体"):
            await typst_fonts.download_typst_fonts(tmp_path, "https://cdn.test", "HatsuneMiku", name=name)
    assert calls == [filename]


@pytest.mark.asyncio
async def test_github_source_preserves_version_and_reports_http_and_timeout(tmp_path, monkeypatch):
    calls = []

    async def download(session, url, target, on_progress=None):
        calls.append(url)
        if len(calls) == 1:
            raise aiohttp.ClientResponseError(MagicMock(), (), status=403)
        raise TimeoutError()

    monkeypatch.setattr(typst_fonts, "_download_font", download)
    with pytest.raises(ValueError, match=r"Outfit.ttf.*HTTP 403"):
        await typst_fonts.download_typst_fonts(tmp_path, "https://cdn.test", name="Outfit.ttf", source="github")
    assert calls[0] == "https://raw.githubusercontent.com/google/fonts/main/ofl/outfit/Outfit[wght].ttf"
    with pytest.raises(ValueError, match=r"LXGWWenKai-Medium.ttf.*20 秒"):
        await typst_fonts.download_typst_fonts(tmp_path, "https://cdn.test", name="LXGWWenKai-Medium.ttf", source="github")
    assert calls[1] == typst_fonts.FONT_SOURCES["LXGWWenKai-Medium.ttf"]
    assert "/v1.522/" in calls[1]


@pytest.mark.asyncio
async def test_replacing_managed_original_invalidates_derived_image(
    tmp_path, monkeypatch
):
    from src.infrastructure.reporting import template_resources
    from src.infrastructure.reporting.template_asset_catalog import RESOURCE_FILES

    name = next(name for name in RESOURCE_FILES if name.endswith(".png"))
    original = tmp_path / "typst/resources" / name
    original.parent.mkdir(parents=True)
    monkeypatch.setattr(
        template_resources, "REPOSITORY_ASSETS", tmp_path / "no-repository"
    )
    store = template_resources.TemplateResourceStore(
        tmp_path, "https://cdn.test/assets"
    )
    async with aiohttp.ClientSession() as session:
        pixels = []
        for index, color in enumerate(("red", "blue")):
            Image.new("RGB", (12, 12), color).save(original)
            os.utime(original, ns=(1700000000000000000, 1700000000000000000))
            job = tmp_path / f"job-{index}"
            job.mkdir()
            assets = typst_resources.TypstAssets(
                tmp_path, job, session, resource_store=store
            )
            localized = await assets.localize(f"https://cdn.test/assets/{name}")
            with Image.open(job / localized) as image:
                pixels.append(image.getpixel((0, 0)))
        assert pixels[0] != pixels[1]


def test_oval_avatar_keeps_normal_avatar_and_cache_separate(tmp_path):
    async def check():
        payload = BytesIO()
        Image.new("RGBA", (12, 12), (57, 197, 187, 255)).save(payload, format="PNG")
        source = (
            "data:image/png;base64," + base64.b64encode(payload.getvalue()).decode()
        )
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
                image = job / await assets.localize(url, 0.25)
                assert Image.open(image).getpixel((0, 0))[3] == 50
            await runner.cleanup()
            import os

            for file in (tmp_path / "typst/assets").glob("*.png"):
                os.utime(file, (1, 1))
            async with aiohttp.ClientSession() as session:
                network = MagicMock(
                    side_effect=AssertionError("已有本地图片不应联网刷新")
                )
                monkeypatch.setattr(session, "get", network)
                job = tmp_path / "job-two"
                job.mkdir()
                assets = typst_resources.TypstAssets(tmp_path, job, session)
                image = job / await assets.localize(url, 0.25)
                assert Image.open(image).getpixel((0, 0))[3] == 50
                assert await assets.localize(url, 0.25) == image.name
                network.assert_not_called()
            assert calls == ["/role.png"]
        finally:
            await runner.cleanup()

    asyncio.run(check())


def test_bad_font_response_leaves_no_partial_files(tmp_path, monkeypatch):
    monkeypatch.setattr(typst_fonts, "FONT_SOURCES", {"Noto.ttf": "gh/test/fonts@v1/font.ttf"})

    async def check():
        app = web.Application()

        async def not_a_font(request):
            return web.Response(text="<html>CDN error</html>")

        app.router.add_get("/gh/test/fonts@v1/font.ttf", not_a_font)
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        try:
            with pytest.raises(ValueError):
                await typst_resources.download_typst_fonts(
                    tmp_path, f"http://127.0.0.1:{runner.addresses[0][1]}"
                )
            assert list((tmp_path / "typst/fonts").iterdir()) == []
            assert typst_resources.typst_font_status(tmp_path)["missing"] == [
                "Noto.ttf"
            ]
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
async def test_cancelled_image_waits_for_decoder_before_releasing_job(
    tmp_path, monkeypatch, decoder_fails
):
    import threading

    started, finish = threading.Event(), threading.Event()
    original = typst_resources.TypstAssets._save_image

    def process(*args, **kwargs):
        started.set()
        finish.wait(5)
        if decoder_fails:
            raise ValueError("取消清理时图片解码失败")
        original(*args, **kwargs)

    monkeypatch.setattr(
        typst_resources.TypstAssets, "_save_image", staticmethod(process)
    )
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
            await asyncio.sleep(0.01)
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
async def test_oversized_image_falls_back_and_download_validation_rejects(
    tmp_path, oversized_avatar_uri
):
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
        TemplateResourceStore.validate(downloaded, "scrapbook/assistant.jpg")


@pytest.mark.asyncio
async def test_theme_font_download_skips_other_themes_and_reuses_shared_files(
    tmp_path, monkeypatch
):
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
    app.router.add_get("/gh/test/fonts@v1/outfit.ttf", font)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    monkeypatch.setattr(
        typst_fonts,
        "FONT_SOURCES",
        {**typst_fonts.FONT_SOURCES, "Outfit.ttf": "gh/test/fonts@v1/outfit.ttf"},
    )
    try:
        cdn = f"http://127.0.0.1:{runner.addresses[0][1]}"
        status = await typst_resources.download_typst_fonts(
            tmp_path, cdn, "HatsuneMiku"
        )
        selected = next(
            group for group in status["groups"] if group["theme"] == "HatsuneMiku"
        )
        assert selected["ready"] and not selected["missing"]
        assert not status["ready"] and "Cinzel.ttf" in status["missing"]
        await typst_resources.download_typst_fonts(tmp_path, cdn, "HatsuneMiku")
        assert calls == ["/gh/test/fonts@v1/outfit.ttf"]
        with pytest.raises(ValueError, match="未知"):
            await typst_resources.download_typst_fonts(tmp_path, cdn, "../../outside")
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_miku_title_subset_reuses_repository_and_existing_cache(tmp_path, monkeypatch):
    """源码补齐只复制真实标题子集，不下载完整版；已有用户文件保持原样。"""
    from unittest.mock import AsyncMock

    download = AsyncMock(side_effect=AssertionError("本地标题字体不应联网"))
    monkeypatch.setattr(typst_fonts, "_download_font", download)
    progress = []
    status = await typst_fonts.download_typst_fonts(
        tmp_path, "https://cdn.test", "HatsuneMiku", name=typst_fonts.MIKU_TITLE_FONT,
        on_progress=progress.append,
    )
    target = tmp_path / "typst/fonts" / typst_fonts.MIKU_TITLE_FONT
    assert target.read_bytes() == typst_fonts.REPOSITORY_TITLE_FONT.read_bytes()
    assert 0 < target.stat().st_size < 32 * 1024
    assert progress[-1]["received"] == target.stat().st_size
    assert progress[-1]["url"].startswith("file:")
    assert "cjkFonts_allseto_v1.11.ttf" not in status["missing"]
    target.write_bytes(b"user-font")
    await typst_fonts.download_typst_fonts(tmp_path, "https://cdn.test", name=target.name)
    assert target.read_bytes() == b"user-font"
    assert not list(target.parent.glob("*.part"))
    download.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["cdn", "github"])
async def test_miku_subset_release_download_uses_small_resource(tmp_path, monkeypatch, source):
    """发布包无 assets 时下载同一份子集，原子保存并校验真实 TTF 响应。"""
    payload = typst_fonts.REPOSITORY_TITLE_FONT.read_bytes()
    monkeypatch.setattr(typst_fonts, "REPOSITORY_TITLE_FONT", tmp_path / "no-assets.ttf")
    calls = []
    real_download = typst_fonts._download_font
    app = web.Application()
    async def serve(request):
        return web.Response(body=payload)
    app.router.add_get("/font.ttf", serve)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    async def capture(session, url, target, on_progress=None):
        calls.append(url)
        await real_download(session, f"http://127.0.0.1:{runner.addresses[0][1]}/font.ttf", target, on_progress)
    monkeypatch.setattr(typst_fonts, "_download_font", capture)
    try:
        status = await typst_fonts.download_typst_fonts(tmp_path, "https://cdn.test/", name=typst_fonts.MIKU_TITLE_FONT, source=source)
    finally:
        await runner.cleanup()
    preset = next(item for item in status["presets"] if item["name"] == typst_fonts.MIKU_TITLE_FONT)
    assert calls == [preset["download_url"] if source == "github" else "https://cdn.test/" + preset["cdn_path"]]
    assert (tmp_path / "typst/fonts" / typst_fonts.MIKU_TITLE_FONT).read_bytes() == payload
    assert "moeru-ai" not in calls[0]
