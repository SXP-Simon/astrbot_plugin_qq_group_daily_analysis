"""验证官方素材直传、同条图文消息和配额释放边界。"""

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.platform.adapters import qq_markdown_images as module
from src.infrastructure.platform.adapters.qq_official_adapter import QQOfficialAdapter

PNG = b"\x89PNG\r\n\x1a\n" + b"test"
REFERENCE = "qqbot-media://image/v1/local_test"


@pytest.fixture
def upload_api(monkeypatch):
    calls = []
    etag = "a" * 32

    class Response:
        status = 200
        headers = {"ETag": f'"{etag}"'}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def raise_for_status(self):
            pass

    class Session:
        def __init__(self, **kwargs):
            assert "headers" not in kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def put(self, url, **kwargs):
            calls.append(("PUT", url, kwargs))
            assert kwargs["headers"] == {"Content-Type": "image/png"}
            assert kwargs["allow_redirects"] is False
            return Response()

    async def request(route, **kwargs):
        calls.append((route.method, route.url, kwargs))
        if "/v2/media-images" in route.url:
            assert route.url.startswith("https://api.bot.qq.com/")
        if route.url.endswith("/prepare"):
            return {"upload_id": "upload-test", "presigned_url": "https://cos.example.test/upload?signed=secret"}
        if route.url.endswith("/complete"):
            assert kwargs["json"]["md5"] == etag
            return {"image_id": "own-image", "url": REFERENCE, "ttl": 7776000}
        if route.method == "DELETE":
            return {}
        if route.url.endswith("/messages"):
            return {"id": "REPORT"}
        raise AssertionError(route.url)

    monkeypatch.setattr(module.aiohttp, "ClientSession", Session)
    return SimpleNamespace(request=AsyncMock(side_effect=request)), calls, Response


@pytest.mark.asyncio
async def test_prepare_put_complete_and_owned_cleanup(upload_api):
    http, calls, _ = upload_api
    store = module.QQMarkdownImages(http)
    assert await store.upload(PNG) == REFERENCE
    prepare = calls[0][2]["json"]
    assert prepare["file_size"] == len(PNG)
    assert prepare["md5"] == hashlib.md5(PNG).hexdigest()
    assert prepare["sha1"] == hashlib.sha1(PNG).hexdigest()
    assert calls[1][2]["data"] == PNG
    await store.release("无关正文")
    assert len(calls) == 3
    await store.release(f"![概览]({REFERENCE})\n\n正文")
    assert calls[-1][0] == "DELETE"
    assert calls[-1][1].endswith("/own-image/delete")
    assert not store.pending


@pytest.mark.asyncio
async def test_same_markdown_uses_botpy_and_releases_material(upload_api):
    from botpy.api import BotAPI

    http, calls, _ = upload_api
    adapter = QQOfficialAdapter(SimpleNamespace(api=BotAPI(http), platform=None))
    adapter.send_image = AsyncMock(side_effect=AssertionError("不得独立发送图片"))
    reference = await adapter.upload_markdown_image(PNG)
    body = f"![概览 #940px #423px]({reference})\n\n## 热门话题\n正文"
    assert await adapter.send_text_report("GROUP", body, "完整统计与正文")
    messages = [call for call in calls if call[1].endswith("/messages")]
    assert len(messages) == 1
    payload = messages[0][2]["json"]
    assert payload["msg_type"] == 2
    assert payload["markdown"]["content"] == body
    assert payload["markdown"]["force_verify_image_resource"] is True
    assert calls[-1][0] == "DELETE"
    adapter.send_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_markdown_retains_full_text_and_releases_material(upload_api, monkeypatch):
    from botpy.api import BotAPI

    http, calls, _ = upload_api
    adapter = QQOfficialAdapter(SimpleNamespace(api=BotAPI(http), platform=None))
    reference = await adapter.upload_markdown_image(PNG)
    monkeypatch.setattr(adapter, "_send_markdown_chunk", AsyncMock(side_effect=RuntimeError("图片转存失败")))
    adapter.send_text = AsyncMock(return_value=True)
    assert await adapter.send_text_report("GROUP", f"![概览]({reference})\n正文", "完整统计与正文")
    adapter.send_text.assert_awaited_once_with("GROUP", "完整统计与正文")
    assert calls[-1][0] == "DELETE"


@pytest.mark.asyncio
async def test_missing_etag_does_not_complete_upload(upload_api):
    http, calls, response = upload_api
    response.headers = {}
    with pytest.raises(ValueError, match="ETag"):
        await module.QQMarkdownImages(http).upload(PNG)
    assert len(calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("image", [b"not png", b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024**2)], ids=["not-png", "too-large"])
async def test_invalid_image_does_not_call_platform(image):
    http = SimpleNamespace(request=AsyncMock())
    with pytest.raises(ValueError):
        await module.QQMarkdownImages(http).upload(image)
    http.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_complete_reference_is_not_used(upload_api):
    http, _, _ = upload_api
    http.request = AsyncMock(side_effect=[
        {"upload_id": "upload", "presigned_url": "https://cos.example.test/upload"},
        {"image_id": "own", "url": "https://private.example.test/signed"},
    ])
    with pytest.raises(ValueError, match="引用"):
        await module.QQMarkdownImages(http).upload(PNG)
