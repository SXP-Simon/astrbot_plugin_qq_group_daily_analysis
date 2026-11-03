"""主题资源接口只允许固定文件和插件受管理目录。"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.infrastructure.webui.routes import template_resource_routes as routes
from src.infrastructure.reporting import template_resources


@pytest.fixture
def resource_routes(tmp_path, monkeypatch):
    request = MagicMock()
    request.json = AsyncMock()
    monkeypatch.setattr(routes, "request", request)
    monkeypatch.setattr(routes.StarTools, "get_data_dir", lambda name: tmp_path)
    monkeypatch.setattr(routes, "json_response", lambda body: body)
    monkeypatch.setattr(routes, "error_response", lambda message, status_code: {"message": message, "status_code": status_code})
    monkeypatch.setattr(template_resources, "REPOSITORY_ASSETS", tmp_path / "release")
    return routes.TemplateResourceRoutes(), request


@pytest.mark.asyncio
async def test_resource_status_is_local_only(resource_routes, monkeypatch, tmp_path):
    endpoint, _ = resource_routes
    monkeypatch.setattr(routes.aiohttp, "ClientSession", MagicMock(side_effect=AssertionError("状态查询不应联网")))
    response = await endpoint.api_get_resources()
    assert response["data"]["directory"] == str(tmp_path / "typst/resources")
    assert len(response["data"]["groups"]) == 12
    assert all(not file["available"] for group in response["data"]["groups"] for file in group["files"])


@pytest.mark.asyncio
async def test_download_uses_selected_cdn_and_managed_directory(resource_routes, monkeypatch, tmp_path):
    endpoint, request = resource_routes
    request.json.return_value = {"name": "hack/globe.svg", "cdn_base_url": "https://fastly.jsdelivr.net/", "path": "/ignored"}
    captured = []
    async def ensure(self, name, session):
        captured.append((self.directory, self.base_url, name))
        return tmp_path / "globe.svg"
    monkeypatch.setattr(routes.TemplateResourceStore, "ensure", ensure)
    result = await endpoint.api_download_resource()
    assert result["data"] == {"name": "hack/globe.svg", "available": True}
    assert captured == [(tmp_path / "typst/resources", "https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets", "hack/globe.svg")]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[], {"name": "../secret"}, {"name": "hack/report.typ"}, {"name": "hack/globe.svg", "cdn_base_url": "https://cdn.example/path"}])
async def test_download_rejects_unknown_paths_before_network(resource_routes, monkeypatch, body):
    endpoint, request = resource_routes
    request.json.return_value = body
    network = MagicMock(side_effect=AssertionError("非法请求不应联网"))
    monkeypatch.setattr(routes.aiohttp, "ClientSession", network)
    assert (await endpoint.api_download_resource())["status_code"] == 400
    network.assert_not_called()


@pytest.mark.asyncio
async def test_download_failure_is_retryable(resource_routes, monkeypatch):
    endpoint, request = resource_routes
    request.json.return_value = {"name": "hack/globe.svg", "cdn_base_url": "https://cdn.jsdelivr.net"}
    monkeypatch.setattr(routes.TemplateResourceStore, "ensure", AsyncMock(side_effect=TimeoutError()))
    result = await endpoint.api_download_resource()
    assert result["status_code"] == 502
    assert "已下载文件会保留" in result["message"]
