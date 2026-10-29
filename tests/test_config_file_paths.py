"""配置参考图读取和保存边界的回归测试。"""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.infrastructure.webui.routes import config_routes as route_module
from src.infrastructure.webui.routes.config_routes import ConfigRoutes


@pytest.fixture
def file_roots(tmp_path, monkeypatch):
    data = tmp_path / "plugin-data"
    plugin = tmp_path / "plugin"
    data.mkdir()
    plugin.mkdir()
    from astrbot.api.star import StarTools

    monkeypatch.setattr(StarTools, "get_data_dir", lambda _: data)
    monkeypatch.setattr(
        route_module,
        "__file__",
        str(plugin / "src/infrastructure/webui/routes/config_routes.py"),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        route_module, "time", SimpleNamespace(time=lambda: 1234567890.0)
    )
    return data, plugin


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["relative", "backslash", "absolute"])
async def test_config_file_preview_rejects_path_escape(
    file_roots, tmp_path, monkeypatch, kind
):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"private content")
    path = {
        "relative": "../outside.png",
        "backslash": "..\\outside.png",
        "absolute": str(outside),
    }[kind]
    monkeypatch.setattr(route_module, "request", MagicMock(query={"path": path}))
    result = await ConfigRoutes(None).api_get_config_file_content()
    assert result["status_code"] == 400
    assert base64.b64encode(outside.read_bytes()).decode() not in str(result)


@pytest.mark.asyncio
async def test_config_file_preview_reads_inside_resource_directory(
    file_roots, monkeypatch
):
    image = file_roots[0] / "files" / "character" / "reference.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"allowed image")
    monkeypatch.setattr(
        route_module,
        "request",
        MagicMock(query={"path": "files/character/reference.png"}),
    )
    result = await ConfigRoutes(None).api_get_config_file_content()
    assert result["status_code"] == 200
    assert base64.b64encode(image.read_bytes()).decode() in str(result)


@pytest.mark.asyncio
async def test_config_file_preview_does_not_follow_escaping_symlink(
    file_roots, tmp_path, monkeypatch
):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside private content")
    link = file_roots[0] / "files" / "link.png"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("当前系统不允许创建符号链接")
    monkeypatch.setattr(
        route_module, "request", MagicMock(query={"path": "files/link.png"})
    )
    result = await ConfigRoutes(None).api_get_config_file_content()
    assert result["status_code"] == 404
