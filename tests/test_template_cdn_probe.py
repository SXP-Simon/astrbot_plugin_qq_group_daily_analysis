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
    "resource",
    [r for r in cdn_probe.PROBE_RESOURCES if r.kind == "gh"],
    ids=lambda r: r.id,
)
@pytest.mark.parametrize("damage", ["truncated", "html"])
async def test_probe_rejects_incomplete_or_replaced_files(resource, damage):
    body = (Path(__file__).resolve().parents[1] / "assets" / resource.path).read_bytes()
    body = (
        body[: len(body) // 2]
        if damage == "truncated"
        else b"<html>Please verify</html>"
    )
    mime = {
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
        "jpeg": "image/jpeg",
        "woff2": "font/woff2",
    }[resource.format]

    async def serve(_request):
        return web.Response(body=body, content_type=mime)

    app = web.Application()
    app.router.add_get("/resource", serve)
    async with TestServer(app) as server, aiohttp.ClientSession() as session:
        result = await cdn_probe._probe_resource(
            session, resource, str(server.make_url("/resource"))
        )
    assert not result["success"]
    assert result["status_code"] == 200
    assert result["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "ok",
        "npm_404",
        "html_200",
        "empty",
        "wrong_mime",
        "oversized",
        "timeout",
        "redirect",
        "redirect_loop",
    ],
)
async def test_probe_downloads_and_validates_both_resources(scenario, monkeypatch):
    assets = Path(__file__).resolve().parents[1] / "assets"
    formats = {
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
        "jpeg": "image/jpeg",
        "woff2": "font/woff2",
    }
    gh_resources = {
        resource.path: resource
        for resource in cdn_probe.PROBE_RESOURCES
        if resource.kind == "gh"
    }
    requested_paths = []
    requested_raw_paths = []

    async def serve(request):
        requested_paths.append(request.path)
        requested_raw_paths.append(request.raw_path)
        if request.path.startswith("/gh/"):
            path = request.path.split("/assets/", 1)[1]
            resource = gh_resources[path]
            return web.Response(
                body=(assets / path).read_bytes(), content_type=formats[resource.format]
            )
        if scenario == "npm_404":
            raise web.HTTPNotFound
        if scenario == "html_200":
            return web.Response(
                text="<html>Please verify</html>", content_type="text/html"
            )
        if scenario == "empty":
            return web.Response(body=b"", content_type="text/css")
        if scenario == "oversized":
            return web.Response(
                body=b"x" * (cdn_probe.MAX_PROBE_BYTES + 1), content_type="text/css"
            )
        if scenario == "timeout":
            await asyncio.sleep(0.75)
        if scenario == "redirect_loop" or (
            scenario == "redirect" and request.path != "/redirected.css"
        ):
            raise web.HTTPFound("/redirected.css")
        return web.Response(
            body=b"/*! normalize.css v8.0.1 | MIT License */\nhtml { line-height: 1.15; }",
            content_type="text/html" if scenario == "wrong_mime" else "text/css",
        )

    if scenario == "timeout":
        monkeypatch.setattr(cdn_probe, "PROBE_TIMEOUT_SECONDS", 0.25)
        selected = (cdn_probe.PROBE_RESOURCES[0], cdn_probe.PROBE_RESOURCES[-1])
        monkeypatch.setattr(cdn_probe, "PROBE_RESOURCES", selected)
        gh_resources = {selected[0].path: selected[0]}
    app = web.Application()
    app.router.add_get("/{path:.*}", serve)
    async with TestServer(app) as server:
        root = str(server.make_url("/"))
        result = await cdn_probe.probe_template_cdn(" " + root + " ")

    assert result["base_url"] == root.rstrip("/")
    assert result["usable"] is (scenario in ("ok", "redirect"))
    github, npm = result["checks"][:-1], result["checks"][-1]
    assert len(github) == len(gh_resources)
    assert all(check["success"] and check["status_code"] == 200 for check in github)
    for check in github:
        path = check["url"].split("/assets/", 1)[1]
        assert check["bytes_received"] == (assets / path).stat().st_size
        assert any(path in requested for requested in requested_paths)
    assert npm["success"] is result["usable"]
    assert all(check["elapsed_ms"] >= 0 for check in result["checks"])
    assert (
        "/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/maria/rose_red.png"
        in requested_paths
    )
    assert "/npm/normalize.css@8.0.1/normalize.css" in requested_paths
    if scenario != "timeout":
        assert any("%E7%96%91%E6%83%91" in path for path in requested_raw_paths)
        assert not any("%25E7" in path for path in requested_raw_paths)
    if not result["usable"]:
        assert npm["error"]


@pytest.mark.asyncio
async def test_probe_network_errors_are_independent_results():
    with patch.object(
        aiohttp.ClientSession,
        "get",
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
