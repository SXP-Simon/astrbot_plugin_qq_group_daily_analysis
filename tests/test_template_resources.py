"""主题资源的发布环境下载、本地复用与失败收尾。"""

from unittest.mock import AsyncMock

import asyncio

import aiohttp
import pytest
from aiohttp import web

from src.infrastructure.reporting import template_resources


@pytest.mark.asyncio
async def test_download_is_local_first_across_cdn_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(template_resources, "REPOSITORY_ASSETS", tmp_path / "empty-release")
    calls = []
    async def resource(request):
        calls.append(request.path)
        return web.Response(text='<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"/>')
    app = web.Application()
    app.router.add_get("/hack/globe.svg", resource)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    try:
        base = f"http://127.0.0.1:{runner.addresses[0][1]}"
        store = template_resources.TemplateResourceStore(tmp_path, base)
        async with aiohttp.ClientSession() as session:
            installed = await store.ensure("hack/globe.svg", session)
            assert installed == tmp_path / "typst/resources/hack/globe.svg"
        await runner.cleanup()
        store = template_resources.TemplateResourceStore(tmp_path, "http://127.0.0.1:1/unavailable", network_deadline=asyncio.get_running_loop().time() - 1)
        async with aiohttp.ClientSession() as session:
            assert await store.ensure("hack/globe.svg", session) == installed
        assert calls == ["/hack/globe.svg"]
        assert store.local_hits == 1 and store.downloads == 0
        assert next(item for item in store.status() if item["theme"] == "hack")["files"][0]["available"]
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"<html>not found</html>", b"x" * (8 * 1024 * 1024 + 1)], ids=["html-error", "oversized"])
async def test_invalid_download_leaves_no_resource_or_partial_file(tmp_path, monkeypatch, payload):
    monkeypatch.setattr(template_resources, "REPOSITORY_ASSETS", tmp_path / "empty-release")
    async def resource(request):
        return web.Response(body=payload)
    app = web.Application()
    app.router.add_get("/hack/globe.svg", resource)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    try:
        store = template_resources.TemplateResourceStore(tmp_path, f"http://127.0.0.1:{runner.addresses[0][1]}")
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ValueError):
                await store.ensure("hack/globe.svg", session)
        assert not list((tmp_path / "typst/resources/hack").iterdir())
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_unknown_resource_never_reaches_network(tmp_path):
    store = template_resources.TemplateResourceStore(tmp_path, "https://cdn.example")
    session = AsyncMock()
    for name in ("../secret", "/secret", "hack/report.typ", "unknown/picture.png"):
        with pytest.raises(ValueError, match="未知模板资源"):
            await store.ensure(name, session)
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_missing_vector_uses_blank_without_caching_placeholder(tmp_path, monkeypatch):
    store = template_resources.TemplateResourceStore(tmp_path, "https://cdn.example")
    monkeypatch.setattr(store, "ensure", AsyncMock(side_effect=TimeoutError()))
    await store.stage_vectors("hack", tmp_path)
    assert (tmp_path / "globe.svg").read_text(encoding="utf-8").startswith("<svg")
    assert store.failed == {"hack/globe.svg"}
    assert not store.directory.exists()


@pytest.mark.asyncio
async def test_render_uses_downloaded_raw_image_after_processed_cache_is_missing(tmp_path, monkeypatch):
    from io import BytesIO
    from PIL import Image
    from src.infrastructure.reporting.typst_resources import TypstAssets

    monkeypatch.setattr(template_resources, "REPOSITORY_ASSETS", tmp_path / "empty-release")
    payload = BytesIO()
    Image.new("RGB", (12, 12), "#39c5bb").save(payload, format="JPEG")
    async def image(request):
        return web.Response(body=payload.getvalue())
    app = web.Application()
    app.router.add_get("/scrapbook/assistant.jpg", image)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    base = f"http://127.0.0.1:{runner.addresses[0][1]}"
    try:
        for index in range(2):
            if index:
                await runner.cleanup()
                for cached in (tmp_path / "typst/assets").glob("*.png"):
                    cached.unlink()
            job = tmp_path / f"job-{index}"
            job.mkdir()
            store = template_resources.TemplateResourceStore(tmp_path, base)
            async with aiohttp.ClientSession() as session:
                assets = TypstAssets(tmp_path, job, session, resource_store=store)
                localized = await assets.localize(base + "/scrapbook/assistant.jpg")
                assert localized
                with Image.open(job / localized) as output:
                    assert output.size == (12, 12)
            assert store.downloads == (0 if index else 1)
            assert store.local_hits == index
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_exhausted_network_budget_skips_requests_but_keeps_local_files(tmp_path, monkeypatch):
    monkeypatch.setattr(template_resources, "REPOSITORY_ASSETS", tmp_path / "release")
    store = template_resources.TemplateResourceStore(tmp_path, "https://cdn.example", network_deadline=asyncio.get_running_loop().time() - 1)
    session = AsyncMock()
    with pytest.raises(TimeoutError, match="网络预算"):
        await store.ensure("hack/globe.svg", session)
    session.get.assert_not_called()
    local = tmp_path / "typst/resources/hack/globe.svg"
    local.parent.mkdir(parents=True)
    local.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    assert await store.ensure("hack/globe.svg", session) == local
    session.get.assert_not_called()
