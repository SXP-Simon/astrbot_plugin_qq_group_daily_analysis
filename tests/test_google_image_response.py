"""Google 图片字段解析与公共图片签名校验的回归测试。"""

import base64
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.infrastructure.drawing.api_requests import common
from src.infrastructure.drawing.api_requests.context import DrawingRequestContext
from src.infrastructure.drawing.api_requests.google import call_google_api
from src.infrastructure.drawing.drawing_image_response import (
    DrawingImageResponseService,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nfinal image"
PNG_BASE64 = base64.b64encode(PNG_BYTES).decode()


@pytest.fixture
def response_service():
    """使用下载替身，确保响应解析测试不会发起网络请求。"""
    return DrawingImageResponseService(SimpleNamespace(), AsyncMock())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "inline_key,mime_key", [("inlineData", "mimeType"), ("inline_data", "mime_type")]
)
async def test_google_skips_thoughts_signatures_and_invalid_images(
    response_service, inline_key, mime_key
):
    """思考图片和签名即使含有图片头，也不能抢占后面的最终图片。"""
    thought_image = base64.b64encode(b"\x89PNG\r\n\x1a\nthought image").decode()
    parts = [
        {"thoughtSignature": thought_image},
        {"text": thought_image},
        {"thought": True, inline_key: {mime_key: "image/png", "data": thought_image}},
        {inline_key: {mime_key: "text/plain", "data": PNG_BASE64}},
        {inline_key: {mime_key: "image/png", "data": "%%%"}},
        {
            inline_key: {
                mime_key: "image/png",
                "data": base64.b64encode(b"not an image").decode(),
            }
        },
        {inline_key: {mime_key: "image/png", "data": PNG_BASE64}},
    ]
    data = {"candidates": [{"content": {"parts": parts}}]}
    assert await response_service.extract_image_from_response(data) == PNG_BYTES
    response_service.download_image.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidates",
    [
        None,
        [],
        "invalid",
        [None],
        [{"content": None}],
        [{"content": {"parts": [None, "invalid", {"inlineData": None}]}}],
        [
            {
                "content": {
                    "parts": [
                        {
                            "thought": True,
                            "inlineData": {"mimeType": "image/png", "data": PNG_BASE64},
                        }
                    ]
                }
            }
        ],
        [
            {
                "content": {
                    "parts": [{"thoughtSignature": PNG_BASE64}, {"text": PNG_BASE64}]
                }
            }
        ],
    ],
)
async def test_google_without_final_image_does_not_use_generic_fallback(
    response_service, candidates
):
    """无最终图片时不能从其他字段或下载地址兜底取图。"""
    data = {
        "candidates": candidates,
        "base64": PNG_BASE64,
        "url": "https://example.com/image.png",
    }
    assert await response_service.extract_image_from_response(data) is None
    response_service.download_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_google_request_keeps_injected_transport_and_shared_parser(
    response_service, monkeypatch
):
    """经过统一请求入口和真实解析器，不连接 Google 或重新建立专用请求入口。"""
    response = httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"thoughtSignature": "invalid"},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": PNG_BASE64,
                                }
                            },
                        ]
                    }
                }
            ]
        },
    )
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=response)
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(common.httpx, "AsyncClient", factory)
    hooks = MagicMock()
    hooks._get_provider_value.side_effect = lambda name, provider: provider.get(name)
    hooks._get_request_proxy.return_value = "http://configured-proxy:8080"
    context = DrawingRequestContext(
        hooks, AsyncMock(), response_service.extract_image_from_response
    )
    context.request_json.side_effect = partial(common.post_json_for_image, context)
    provider = {
        "api_url": "https://example.com/v1beta",
        "api_key": "test-key",
        "model": "test-model",
        "timeout": 60,
    }
    assert await call_google_api(context, "prompt", None, provider) == PNG_BYTES
    context.request_json.assert_awaited_once()
    assert (
        context.request_json.call_args.args[0]
        == "https://example.com/v1beta/models/test-model:generateContent"
    )
    assert factory.call_args.kwargs["proxy"] == "http://configured-proxy:8080"
    client.post.assert_awaited_once()
    client.__aexit__.assert_awaited_once()


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not an image",
        b"<html>error</html>",
        b'{"error":"failed"}',
        b"\x01\x02\x03\x04",
    ],
)
def test_base64_rejects_non_image_bytes(data):
    """合法 Base64 不代表合法图片，未知内容必须明确拒绝。"""
    with pytest.raises(ValueError):
        DrawingImageResponseService.decode_base64(base64.b64encode(data).decode())


@pytest.mark.parametrize(
    "data",
    [
        PNG_BYTES,
        b"\xff\xd8\xffjpeg",
        b"GIF87a",
        b"GIF89a",
        b"BMbitmap",
        b"II*\x00tiff",
        b"MM\x00*tiff",
        b"\x00\x00\x00\x0cjP  ",
        b"RIFFxxxxWEBP",
        b"\x00\x00\x00\x18ftypavif",
        b"\x00\x00\x00\x18ftypavis",
        b"\x00\x00\x00\x18ftypjp2 ",
    ],
)
def test_supported_signatures_still_pass(data):
    """保留已有格式支持，仅修复未匹配签名也放行的漏洞。"""
    DrawingImageResponseService.validate_image_bytes(data)


@pytest.mark.asyncio
async def test_generic_response_skips_invalid_base64_candidate(response_service):
    """非 Google 响应也会跳过非图片候选并继续寻找有效图片。"""
    data = {
        "data": [
            {"b64_json": base64.b64encode(b"not image").decode()},
            {"b64_json": PNG_BASE64},
        ]
    }
    assert await response_service.extract_image_from_response(data) == PNG_BYTES
