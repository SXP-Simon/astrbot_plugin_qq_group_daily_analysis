"""二进制分块上传的完整性、取消与并发覆盖保护。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.persistence.managed_files import ManagedFiles
from src.infrastructure.webui import download_control
from src.infrastructure.webui.routes import managed_upload_routes
from src.infrastructure.webui.routes.managed_file_routes import ManagedFileRoutes


@pytest.fixture
def upload_routes(tmp_path, monkeypatch):
    files = ManagedFileRoutes()
    store = ManagedFiles(tmp_path)
    monkeypatch.setattr(files, "store", lambda: store)
    control = download_control.DownloadControl()
    route = managed_upload_routes.ManagedUploadRoutes(files, control)
    req = SimpleNamespace(query={}, files=AsyncMock(), json=AsyncMock())
    for module in (managed_upload_routes, download_control):
        monkeypatch.setattr(module, "request", req)
        monkeypatch.setattr(module, "json_response", lambda value: value)
        monkeypatch.setattr(
            module,
            "error_response",
            lambda message, status_code: {
                "message": message,
                "status_code": status_code,
            },
        )
    req.query = {
        "download_id": str(uuid.uuid4()),
        "partition": "typst_fonts",
        "name": "test.ttf",
        "operation": "create",
        "revision": "",
        "offset": "0",
        "total": "1049600",
    }
    req.files.return_value = {
        "file": SimpleNamespace(
            read=AsyncMock(return_value=b"\x00\x01\x00\x00" + bytes(1024 * 1024 - 4))
        )
    }
    return route, req, store


@pytest.mark.asyncio
async def test_chunk_upload_only_publishes_complete_valid_font(upload_routes):
    route, req, store = upload_routes
    req.json.return_value = {**req.query, "total": int(req.query["total"])}
    await route.api_start()
    target = store.path("typst_fonts", "test.ttf")
    first = await route.api_upload(req.query["download_id"], req.query["offset"])
    assert first["data"] == {"received": 1048576, "total": 1049600, "complete": False}
    assert not target.exists()
    req.query["offset"] = "1048576"
    req.files.return_value["file"].read.return_value = bytes(1024)
    second = await route.api_upload(req.query["download_id"], req.query["offset"])
    assert second["data"]["complete"]
    assert target.stat().st_size == 1049600
    assert not route._sessions
    assert not list(target.parent.parent.glob("uploads/*.part"))


@pytest.mark.asyncio
@pytest.mark.parametrize("inflight", [False, True])
async def test_upload_cancel_cleans_chunks_and_rejects_late_writes(
    upload_routes, inflight
):
    route, req, store = upload_routes
    req.json.return_value = {**req.query, "total": int(req.query["total"])}
    await route.api_start()
    await route.api_upload(req.query["download_id"], req.query["offset"])
    req.query["offset"] = "1048576"
    started = asyncio.Event()

    async def read(size):
        started.set()
        await asyncio.Event().wait()

    task = None
    if inflight:
        req.files.return_value["file"].read.side_effect = read
        task = asyncio.create_task(
            route.api_upload(req.query["download_id"], req.query["offset"])
        )
        await asyncio.wait_for(started.wait(), 2)
    req.json.return_value = {"download_id": req.query["download_id"]}
    result = await route.api_cancel()
    assert result["data"]["cancelled"]
    if task:
        assert (await asyncio.wait_for(task, 2))["status_code"] == 409
    assert (await route.api_upload(req.query["download_id"], req.query["offset"]))[
        "status_code"
    ] == 409
    assert not store.path("typst_fonts", "test.ttf").exists()
    assert not route._sessions
    assert not list(
        store.partition("typst_fonts").directory.parent.glob("uploads/*.part")
    )


@pytest.mark.asyncio
async def test_upload_replacement_checks_revision_at_commit(upload_routes):
    route, req, store = upload_routes
    store.mutate(
        "typst_fonts", "test.ttf", "create", payload=b"\x00\x01\x00\x00original"
    )
    req.query.update(operation="replace", revision="stale", total="1048576")
    req.json.return_value = {**req.query, "total": int(req.query["total"])}
    await route.api_start()
    result = await route.api_upload(req.query["download_id"], req.query["offset"])
    assert result["status_code"] == 409
    assert store.path("typst_fonts", "test.ttf").read_bytes().endswith(b"original")
    assert not route._sessions


@pytest.mark.asyncio
async def test_duplicate_request_cannot_discard_active_upload(upload_routes):
    route, req, store = upload_routes
    req.json.return_value = {**req.query, "total": int(req.query["total"])}
    await route.api_start()
    started, resume = asyncio.Event(), asyncio.Event()
    payload = req.files.return_value["file"].read.return_value

    async def read(size):
        started.set()
        await resume.wait()
        return payload

    req.files.return_value["file"].read.side_effect = read
    task = asyncio.create_task(
        route.api_upload(req.query["download_id"], req.query["offset"])
    )
    await asyncio.wait_for(started.wait(), 2)
    assert (await route.api_upload(req.query["download_id"], req.query["offset"]))[
        "status_code"
    ] == 400
    assert req.query["download_id"] in route._sessions
    resume.set()
    assert (await task)["data"]["received"] == len(payload)
    assert not store.path("typst_fonts", "test.ttf").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields",
    [
        {"name": "../escape.ttf"},
        {"total": "33554433"},
        {"total": "0"},
        {"partition": "typst_jobs"},
        {"download_id": "../bad"},
    ],
)
async def test_invalid_upload_rejected_before_reading_file(upload_routes, fields):
    route, req, _ = upload_routes
    req.query.update(fields)
    req.json.return_value = {**req.query, "total": int(req.query["total"])}
    result = await route.api_start()
    assert result["status_code"] == 400
    req.files.assert_not_awaited()
