import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from src.infrastructure.reporting import cdn_probe
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


def test_probe_files_cover_current_template_path_shapes():
    root = Path(__file__).resolve().parents[1]
    template_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "src/infrastructure/reporting/templates").rglob("*.html")
    )
    prefixes = {
        "t2i_miku_assets_mirror": "HatsuneMiku",
        "t2i_atri_font_mirror": "ATRI",
        "t2i_deepseek_maid_assets_mirror": "deepseek_maid",
        "t2i_maria_assets_mirror": "maria",
        "maria_cdn_base": "maria",
    }
    referenced = set()
    for variable, prefix in prefixes.items():
        expression = (
            r"(?:\{\{\s*"
            + variable
            + r"\s*\}\}|"
            + variable
            + r"\s*~\s*['\"])/([^'\"\s<>\)]+)"
        )
        referenced.update(
            prefix + "/" + match for match in re.findall(expression, template_text)
        )
    assert referenced
    probe_paths = {
        resource.path for resource in cdn_probe.PROBE_RESOURCES if resource.kind == "gh"
    }
    for path in probe_paths:
        assert (root / "assets" / path).is_file()
        if not path.endswith("-demo.jpg"):
            assert path in referenced
    # 同时覆盖文件类型、目录深度及中文文件名；模板新增形态时提示维护检测清单。
    shapes = {
        (Path(path).suffix, len(Path(path).parts), not path.isascii())
        for path in referenced
    }
    covered = {
        (Path(path).suffix, len(Path(path).parts), not path.isascii())
        for path in probe_paths
    }
    assert shapes <= covered
    assert any(path.endswith("-demo.jpg") for path in probe_paths)
    assert "t2i_npm_mirror" not in template_text, (
        "新增 npm 依赖后，请替换兼容性样本并更新用途说明"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "ok",
        "204",
        "403",
        "404",
        "405",
        "501",
        "503",
        "timeout",
        "redirect",
        "redirect_loop",
    ],
)
async def test_probe_checks_headers_without_downloading(scenario, monkeypatch):
    requested_paths = []
    requested_raw_paths = []
    requested_methods = []

    async def serve(request):
        requested_paths.append(request.path)
        requested_raw_paths.append(request.raw_path)
        requested_methods.append(request.method)
        if not request.path.startswith("/gh/"):
            if scenario.isdigit():
                return web.Response(status=int(scenario))
            if scenario == "timeout":
                await asyncio.sleep(0.75)
            if scenario == "redirect_loop" or (
                scenario == "redirect" and request.path != "/redirected.css"
            ):
                raise web.HTTPFound("/redirected.css")
        # 只声明一个大文件的响应头，不提供正文；客户端必须不尝试下载它。
        return web.Response(
            headers={
                "Content-Length": "100000000",
                "Content-Type": "application/octet-stream",
            }
        )

    if scenario == "timeout":
        monkeypatch.setattr(cdn_probe, "PROBE_TIMEOUT_SECONDS", 0.25)
        monkeypatch.setattr(
            cdn_probe,
            "PROBE_RESOURCES",
            (cdn_probe.PROBE_RESOURCES[0], cdn_probe.PROBE_RESOURCES[-1]),
        )
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", serve)
    async with TestServer(app) as server:
        root = str(server.make_url("/"))
        with (
            patch.object(
                aiohttp.ClientSession, "get", side_effect=AssertionError("禁止使用 GET")
            ),
            patch.object(
                aiohttp.ClientResponse,
                "read",
                side_effect=AssertionError("禁止读取正文"),
            ),
            patch.object(
                aiohttp.StreamReader,
                "iter_chunked",
                side_effect=AssertionError("禁止读取正文流"),
            ),
        ):
            result = await cdn_probe.probe_template_cdn(" " + root + " ")

    assert result["base_url"] == root.rstrip("/")
    assert result["usable"] is (scenario in ("ok", "204", "redirect"))
    github, npm = result["checks"][:-1], result["checks"][-1]
    assert len(github) == len(cdn_probe.PROBE_RESOURCES) - 1
    assert all(check["success"] and check["status_code"] == 200 for check in github)
    assert set(requested_methods) == {"HEAD"}
    assert all("bytes_received" not in check for check in result["checks"])
    for check in github:
        assert check["url"].split("/assets/", 1)[1] in "\n".join(requested_paths)
    assert npm["success"] is result["usable"]
    assert all(check["elapsed_ms"] >= 0 for check in result["checks"])
    assert "/npm/normalize.css@8.0.1/normalize.css" in requested_paths
    if scenario != "timeout":
        assert any("%E7%96%91%E6%83%91" in path for path in requested_raw_paths)
        assert not any("%25E7" in path for path in requested_raw_paths)
    if scenario.isdigit():
        assert npm["status_code"] == int(scenario)
    if scenario in ("405", "501"):
        assert "不支持 HEAD" in npm["error"]
    if not result["usable"]:
        assert npm["error"]


@pytest.mark.asyncio
async def test_probe_network_errors_are_independent_results():
    with patch.object(
        aiohttp.ClientSession,
        "head",
        side_effect=aiohttp.ClientConnectionError("offline"),
    ):
        result = await cdn_probe.probe_template_cdn("https://example.invalid")
    assert not result["usable"]
    assert all(
        not item["success"] and item["status_code"] is None for item in result["checks"]
    )
    assert all("无法连接" in item["error"] for item in result["checks"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.com/gh/repo",
        "https://example.com:bad",
        "https://example.com?",
        "file:///tmp",
    ],
)
async def test_invalid_probe_address_never_falls_back_or_connects(base_url):
    with patch.object(aiohttp, "ClientSession") as session:
        with pytest.raises(ValueError):
            await cdn_probe.probe_template_cdn(base_url)
        session.assert_not_called()


@pytest.mark.asyncio
async def test_probe_route_uses_unsaved_input_without_writing_config():
    cfg_mgr = MagicMock()
    routes = ConfigRoutes(analysis_service=MagicMock(config_manager=cfg_mgr))
    result = {"base_url": "https://example.com", "usable": False, "checks": []}
    with (
        patch("src.infrastructure.webui.routes.config_routes.request") as request,
        patch(
            "src.infrastructure.webui.routes.config_routes.probe_template_cdn",
            new_callable=AsyncMock,
        ) as probe,
    ):
        request.json = AsyncMock(return_value={"base_url": "https://example.com/"})
        probe.return_value = result
        response = await routes.api_test_template_cdn()
        assert response is not None
        probe.assert_awaited_once_with("https://example.com/")
        cfg_mgr.save_config.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, 123, "x" * 2049])
async def test_probe_route_rejects_invalid_input(value):
    with patch("src.infrastructure.webui.routes.config_routes.request") as request:
        request.json = AsyncMock(return_value={"base_url": value})
        response = await ConfigRoutes(None).api_test_template_cdn()
    status = (
        response["status_code"] if isinstance(response, dict) else response.status_code
    )
    assert status == 400
