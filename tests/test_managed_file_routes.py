"""文件管理接口的请求边界与分页。"""

import base64
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.infrastructure.webui.routes import managed_file_routes as routes


@pytest.fixture
def file_endpoint(tmp_path, monkeypatch):
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
    return endpoint, request


@pytest.mark.asyncio
async def test_routes_paginate_and_reject_stale_file(file_endpoint):
    endpoint, request = file_endpoint
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


@pytest.mark.asyncio
async def test_extension_filter_precedes_pagination_and_batch_delete_is_explicit(
    file_endpoint, tmp_path
):
    endpoint, request = file_endpoint
    directory = tmp_path / "reports"
    directory.mkdir()
    for name in ("keep.html", "one.jpg", "two.PNG", "changed.png"):
        (directory / name).write_text(name)
    request.query = {"partition": "reports", "extensions": "jpg,png", "page_size": "1"}
    response = (await endpoint.api_files())["data"]
    assert response["total"] == 3
    assert len(response["items"]) == 1
    selected = endpoint.store().files("reports")
    selected = [item for item in selected if item["name"] != "keep.html"]
    (directory / "changed.png").write_text("updated")
    request.json.return_value = {
        "partition": "reports",
        "files": [
            {"name": item["name"], "revision": item["revision"]} for item in selected
        ],
    }
    result = (await endpoint.api_delete_many())["data"]
    assert set(result["deleted"]) == {"one.jpg", "two.PNG"}
    assert result["failed"][0]["name"] == "changed.png"
    assert (directory / "keep.html").exists()
    assert (directory / "changed.png").exists()


@pytest.mark.asyncio
async def test_invalid_bulk_selection_does_not_partially_delete(
    file_endpoint, tmp_path
):
    endpoint, request = file_endpoint
    directory = tmp_path / "reports"
    directory.mkdir()
    (directory / "keep.html").write_text("keep")
    selected = endpoint.store().files("reports")[0]
    request.json.return_value = {
        "partition": "reports",
        "files": [
            {"name": selected["name"], "revision": selected["revision"]},
            {"name": "bad"},
        ],
    }
    assert (await endpoint.api_delete_many())["status_code"] == 400
    assert (directory / "keep.html").exists()


@pytest.mark.asyncio
async def test_template_groups_include_all_pages_and_filter_exact_package(
    file_endpoint, tmp_path
):
    endpoint, request = file_endpoint
    directory = tmp_path / "custom_t2i_templates" / "reporting_templates"
    for name in (
        "miku/report.typ",
        "miku/assets/art.png",
        "miku/template.json",
        "miku_extra/report.typ",
        "other/miku/report.typ",
        "loose.typ",
    ):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
    request.query = {
        "partition": "custom_templates",
        "directory": "miku",
        "extensions": "typ",
        "page_size": "1",
    }
    response = (await endpoint.api_files())["data"]
    assert response["total"] == 1
    assert [item["name"] for item in response["items"]] == ["miku/report.typ"]
    assert response["groups"] == [
        {"directory": ".", "count": 1, "size_bytes": 4},
        {"directory": "miku", "count": 3, "size_bytes": 12},
        {"directory": "miku_extra", "count": 1, "size_bytes": 4},
        {"directory": "other", "count": 1, "size_bytes": 4},
    ]
    request.query = {"partition": "custom_templates", "directory": "."}
    assert (await endpoint.api_files())["data"]["items"][0]["name"] == "loose.typ"
    request.query = {"partition": "custom_templates", "directory": "../miku"}
    assert (await endpoint.api_files())["data"]["total"] == 0
