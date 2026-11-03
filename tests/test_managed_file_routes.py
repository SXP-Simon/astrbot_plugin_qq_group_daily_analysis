"""文件管理接口的请求边界与分页。"""

import base64
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.infrastructure.webui.routes import managed_file_routes as routes


@pytest.mark.asyncio
async def test_routes_paginate_and_reject_stale_file(tmp_path, monkeypatch):
    endpoint = routes.ManagedFileRoutes()
    request = MagicMock()
    request.json = AsyncMock()
    monkeypatch.setattr(routes, "request", request)
    monkeypatch.setattr(routes.StarTools, "get_data_dir", lambda _: tmp_path)
    monkeypatch.setattr(routes, "json_response", lambda body: body)
    monkeypatch.setattr(
        routes,
        "error_response",
        lambda message, status_code: {"message": message, "status_code": status_code},
    )
    request.json.return_value = {
        "partition": "custom_templates",
        "name": "demo/a.typ",
        "operation": "create",
        "content_base64": base64.b64encode(b"Hi").decode(),
    }
    assert (await endpoint.api_mutate())["status"] == "ok"
    request.query = {
        "partition": "custom_templates",
        "search": "a.typ",
        "page_size": "1",
    }
    assert (await endpoint.api_files())["data"]["total"] == 1
    request.json.return_value = {
        "partition": "custom_templates",
        "name": "demo/a.typ",
        "operation": "replace",
        "revision": "stale",
        "content_base64": "SGk=",
    }
    assert (await endpoint.api_mutate())["status_code"] == 409
    request.json.return_value["content_base64"] = "!bad"
    assert (await endpoint.api_mutate())["status_code"] == 400
