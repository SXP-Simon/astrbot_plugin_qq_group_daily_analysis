"""下载取消必须关闭实际连接、清理临时文件，并隔离页面请求。"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from aiohttp import web
import pytest

from src.infrastructure.reporting import typst_fonts, template_resources
from src.infrastructure.webui import download_control


@pytest.fixture
def control(monkeypatch):
    request = MagicMock()
    request.json = AsyncMock()
    monkeypatch.setattr(download_control, "request", request)
    monkeypatch.setattr(download_control, "json_response", lambda value: value)
    monkeypatch.setattr(
        download_control,
        "error_response",
        lambda message, status_code: {"message": message, "status_code": status_code},
    )
    return download_control.DownloadControl(), request


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["font", "resource"])
async def test_cancel_closes_stream_and_removes_partial_file(
    control, tmp_path, monkeypatch, kind
):
    manager, request = control
    release = asyncio.Event()
    connected = asyncio.Event()

    async def stream(request):
        response = web.StreamResponse()
        await response.prepare(request)
        await response.write(b"\x00\x01\x00\x00" + bytes(65536))
        connected.set()
        await release.wait()
        return response

    app = web.Application()
    app.router.add_get("/{path:.*}", stream)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    download_id = str(uuid.uuid4())
    request.json.return_value = {"download_id": download_id}
    monkeypatch.setattr(template_resources, "REPOSITORY_ASSETS", tmp_path / "release")
    base = f"http://127.0.0.1:{runner.addresses[0][1]}"
    target = (
        tmp_path / "font.ttf"
        if kind == "font"
        else tmp_path / "typst/resources/hack/globe.svg"
    )
    completed = tmp_path / "completed.ttf"
    completed.write_bytes(b"completed")

    async def download():
        try:
            async with manager.track(download_id), aiohttp.ClientSession() as session:
                if kind == "font":
                    await typst_fonts._download_font(session, base, target)
                else:
                    await template_resources.TemplateResourceStore(
                        tmp_path, base
                    ).ensure("hack/globe.svg", session)
        except download_control.DownloadCancelled:
            return "cancelled"

    task = asyncio.create_task(download())
    try:
        await asyncio.wait_for(connected.wait(), 5)
        assert (await manager.api_cancel())["data"]["cancelled"] is True
        assert await task == "cancelled"
        assert not target.exists()
        assert not list(tmp_path.rglob("*.part"))
        assert completed.read_bytes() == b"completed"
        assert not manager._active
    finally:
        release.set()
        await runner.cleanup()


@pytest.mark.asyncio
async def test_cancel_before_start_is_idempotent_and_does_not_cancel_other_download(
    control,
):
    manager, request = control
    cancelled_id, other_id = str(uuid.uuid4()), str(uuid.uuid4())
    entered = asyncio.Event()
    release = asyncio.Event()

    async def unrelated():
        async with manager.track(other_id):
            entered.set()
            await release.wait()

    task = asyncio.create_task(unrelated())
    await entered.wait()
    request.json.return_value = {"download_id": cancelled_id}
    try:
        await manager.api_cancel()
        await manager.api_cancel()
        with pytest.raises(download_control.DownloadCancelled):
            async with manager.track(cancelled_id):
                pytest.fail("先到的取消必须阻止后到的下载")
        assert not task.done()
    finally:
        release.set()
        await task


@pytest.mark.asyncio
async def test_external_shutdown_still_propagates_cancellation(control):
    manager, _ = control
    entered = asyncio.Event()

    async def download():
        async with manager.track(str(uuid.uuid4())):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(download())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not manager._active
