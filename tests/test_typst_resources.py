"""发布环境的 CDN 下载、缓存与受管理字体落盘。"""

import asyncio
from io import BytesIO

import aiohttp
from aiohttp import web
from PIL import Image
import pytest

from src.infrastructure.reporting import typst_resources


def test_cdn_cache_works_without_development_assets(tmp_path):
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
            async with aiohttp.ClientSession() as session:
                job = tmp_path / "job-two"
                job.mkdir()
                assets = typst_resources.TypstAssets(tmp_path, job, session)
                image = job / await assets.localize(url, .25)
                assert Image.open(image).getpixel((0,0))[3] == 50
            assert calls == ["/role.png"]
        finally:
            await runner.cleanup()
    asyncio.run(check())


def test_bad_font_response_leaves_no_partial_files(tmp_path, monkeypatch):
    monkeypatch.setattr(typst_resources, "FONT_SOURCES", {"Noto.ttf": "font.ttf"})
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
