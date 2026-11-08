"""文件预览压缩与报告读取的传输回归。"""

import base64
import gzip
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.webui import web_compat
from src.infrastructure.webui.routes import report_routes


@pytest.mark.parametrize("accept", ["gzip", "br, gzip;q=0.5", "GZIP; q=1"])
def test_large_file_response_roundtrips_gzip(monkeypatch, accept):
    monkeypatch.setattr(web_compat, "_real_request", SimpleNamespace(headers={"accept-encoding": accept}))
    payload = {"data": {"text": "群聊报告与图片资源" * 10000}}
    response = web_compat.json_response(payload, compress=True)
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Accept-Encoding"
    assert json.loads(gzip.decompress(response.body)) == payload
    assert len(response.body) < len(json.dumps(payload).encode()) / 10


@pytest.mark.parametrize("accept", ["", "br", "gzip;q=0", "gzip;q=invalid"])
def test_compression_respects_client_and_ordinary_responses(monkeypatch, accept):
    monkeypatch.setattr(web_compat, "_real_request", SimpleNamespace(headers={"accept-encoding": accept}))
    native = MagicMock(return_value={"native": True})
    monkeypatch.setattr(web_compat, "_real_json_response", native)
    data = {"text": "x" * 70000}
    assert web_compat.json_response(data, compress=True) == {"native": True}
    native.assert_called_once()


def test_small_or_ordinary_json_keeps_native_response(monkeypatch):
    monkeypatch.setattr(web_compat, "_real_request", SimpleNamespace(headers={"accept-encoding": "gzip"}))
    native = MagicMock(return_value={"native": True})
    monkeypatch.setattr(web_compat, "_real_json_response", native)
    assert web_compat.json_response({"small": True}, compress=True) == {"native": True}
    assert web_compat.json_response({"text": "x" * 70000}) == {"native": True}
    assert native.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["html", "htm", "png"])
async def test_report_get_does_not_wait_for_body_or_duplicate_html(tmp_path, monkeypatch, extension):
    path = tmp_path / f"example.{extension}"
    raw = "<html>群聊示例</html>".encode() if extension != "png" else b"\x89PNG\r\n\x1a\n"
    path.write_bytes(raw)
    body = AsyncMock(side_effect=AssertionError("GET 不应读取请求体"))
    monkeypatch.setattr(report_routes, "request", SimpleNamespace(query={"filename": path.name}, json=body))
    monkeypatch.setattr(report_routes, "json_response", lambda data, **kwargs: data)
    routes = report_routes.ReportRoutes(MagicMock(), analysis_service=None, report_output_dir=tmp_path)
    response = await routes.api_get_report_content()
    result = response["data"]
    body.assert_not_called()
    assert result["size_bytes"] == len(raw)
    if extension != "png":
        assert result["html_content"] == raw.decode()
        assert "data_url" not in result
    else:
        assert base64.b64decode(result["data_url"].split(",", 1)[1]) == raw


def test_file_response_revalidates_browser_cache_after_replacement(monkeypatch):
    headers = {"accept-encoding": "gzip"}
    monkeypatch.setattr(web_compat, "_real_request", SimpleNamespace(headers=headers))
    data = {"text": "abc" * 30000}
    first = web_compat.json_response(data, compress=True)
    assert first.headers["cache-control"] == "private, no-cache"
    headers["if-none-match"] = first.headers["etag"]
    cached = web_compat.json_response(data, compress=True)
    assert cached.status_code == 304
    assert cached.body == b""
    changed = web_compat.json_response({"text": "def" * 30000}, compress=True)
    assert changed.status_code == 200
    assert changed.headers["etag"] != headers["if-none-match"]
