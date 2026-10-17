"""漫画模板示例图路由与宿主 Page Bridge 契约回归。"""

from __future__ import annotations

import base64
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.webui import web_compat
from src.infrastructure.webui.openapi_spec import generate_openapi_spec
from src.infrastructure.webui.plugin_page_bridge import PluginPageWebUIBridge
from src.infrastructure.webui.routes import template_routes
from src.infrastructure.webui.routes.template_routes import TemplateRoutes
from src.shared import trace_context
from src.shared.constants import PLUGIN_NAME


@pytest.fixture
def preview_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TemplateRoutes, Path]:
    """用隔离资源目录和兼容传输层创建模板路由。"""
    monkeypatch.setattr(template_routes, "COMIC_PREVIEW_DIRECTORY", tmp_path)
    monkeypatch.setattr(
        template_routes,
        "COMIC_STORYBOARD_PROMPTS",
        {"classic": "原版提示词", "noir_detective": "侦探提示词"},
    )
    monkeypatch.setattr(
        template_routes,
        "COMIC_PROMPT_PREVIEWS",
        {"noir_detective": "noir_detective.webp"},
    )
    monkeypatch.setattr(web_compat, "_real_json_response", None)
    monkeypatch.setattr(web_compat, "_real_error_response", None)
    request = MagicMock()
    request.query = {"template_name": "noir_detective"}
    monkeypatch.setattr(template_routes, "request", request)
    return TemplateRoutes(analysis_service=None), tmp_path


@pytest.mark.asyncio
async def test_comic_preview_preserves_standard_and_host_bridge_payload(
    preview_routes: tuple[TemplateRoutes, Path], monkeypatch: pytest.MonkeyPatch
):
    """标准响应含成功包装，宿主解包后保留可直接显示的 data_url。"""
    routes, directory = preview_routes
    content = b"RIFF\x04\x00\x00\x00WEBP"
    path = directory / "noir_detective.webp"
    path.write_bytes(content)
    main_thread_id = threading.get_ident()
    read_thread_ids: list[int] = []
    original_read = Path.read_bytes

    def read_preview(file_path: Path) -> bytes:
        """记录读取线程，以确保图像读取不会阻塞事件循环。"""
        read_thread_ids.append(threading.get_ident())
        return original_read(file_path)

    monkeypatch.setattr(Path, "read_bytes", read_preview)
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["status_code"] == 200
    standard_body = response["data"]
    assert standard_body["status"] == "ok"
    # 对齐宿主 response.data?.data ?? response.data 的解包行为。
    bridge_payload = standard_body.get("data", standard_body)
    assert bridge_payload == {
        "data_url": "data:image/webp;base64,"
        + base64.b64encode(content).decode("ascii")
    }
    assert read_thread_ids and all(
        thread_id != main_thread_id for thread_id in read_thread_ids
    )


@pytest.mark.asyncio
async def test_comic_preview_thumbnail_uses_separate_small_resource(
    preview_routes: tuple[TemplateRoutes, Path], monkeypatch: pytest.MonkeyPatch
):
    """画廊只加载独立缩略图，不把完整示例图传入初始页面。"""
    routes, directory = preview_routes
    (directory / "noir_detective.webp").write_bytes("完整示例".encode())
    thumbnail = b"RIFFthumbWEBP"
    (directory / "noir_detective-thumb.webp").write_bytes(thumbnail)
    monkeypatch.setattr(
        template_routes.request,
        "query",
        {"template_name": "noir_detective", "variant": "thumbnail"},
    )
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["data"]["data"]["data_url"] == (
        "data:image/webp;base64," + base64.b64encode(thumbnail).decode("ascii")
    )


@pytest.mark.asyncio
async def test_comic_preview_classic_has_no_image(
    preview_routes: tuple[TemplateRoutes, Path], monkeypatch: pytest.MonkeyPatch
):
    """已知的原版模板无示例图时是合法的空预览。"""
    routes, _ = preview_routes
    monkeypatch.setattr(template_routes.request, "query", {"template_name": "classic"})
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["status_code"] == 200
    assert response["data"] == {"status": "ok", "data": {"data_url": None}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "template_name",
    ["", "custom", "missing", "../noir_detective", "..\\noir_detective", "/etc/passwd"],
)
async def test_comic_preview_rejects_unknown_id_and_path_traversal(
    preview_routes: tuple[TemplateRoutes, Path],
    monkeypatch: pytest.MonkeyPatch,
    template_name: str,
):
    """白名单外的模板值不会被作为文件路径读取。"""
    routes, _ = preview_routes
    monkeypatch.setattr(
        template_routes.request, "query", {"template_name": template_name}
    )
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["status_code"] == 400


@pytest.mark.asyncio
async def test_comic_preview_rejects_invalid_variant(
    preview_routes: tuple[TemplateRoutes, Path], monkeypatch: pytest.MonkeyPatch
):
    """尺寸选项仅允许两种固定资源，拒绝路径和其他任意值。"""
    routes, _ = preview_routes
    monkeypatch.setattr(
        template_routes.request,
        "query",
        {"template_name": "noir_detective", "variant": "../../secret"},
    )
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["status_code"] == 400


@pytest.mark.asyncio
async def test_comic_preview_reports_missing_resource(
    preview_routes: tuple[TemplateRoutes, Path],
):
    """已登记的图片文件缺失时返回明确提示。"""
    routes, _ = preview_routes
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["status_code"] == 404
    assert response["message"] == "该漫画模板没有预览图"


@pytest.mark.asyncio
async def test_comic_preview_rejects_escaped_mapping(
    preview_routes: tuple[TemplateRoutes, Path], monkeypatch: pytest.MonkeyPatch
):
    """即使目录映射异常，也不读取固定资源目录外的文件。"""
    routes, directory = preview_routes
    escaped_file = directory.parent / "outside.webp"
    escaped_file.write_bytes("不允许读取".encode())
    monkeypatch.setattr(
        template_routes, "COMIC_PROMPT_PREVIEWS", {"noir_detective": "../outside.webp"}
    )
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["status_code"] == 404


@pytest.mark.asyncio
async def test_comic_preview_rejects_symlink_resource(
    preview_routes: tuple[TemplateRoutes, Path], monkeypatch: pytest.MonkeyPatch
):
    """符号链接资源不会被当作内置图像返回。"""
    routes, _ = preview_routes
    monkeypatch.setattr(Path, "is_symlink", lambda _path: True)
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["status_code"] == 404


@pytest.mark.asyncio
async def test_comic_preview_reports_read_error_without_internal_path(
    preview_routes: tuple[TemplateRoutes, Path], monkeypatch: pytest.MonkeyPatch
):
    """读取失败对用户明确报错，内部路径只进入日志。"""
    routes, _ = preview_routes

    def fail_read(_path: Path) -> bytes:
        """模拟无法读取打包资源。"""
        raise OSError("内部路径不可读")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    response = await routes.api_get_comic_template_preview()
    assert isinstance(response, dict)
    assert response["status_code"] == 500
    assert response["message"] == "读取漫画模板预览图失败。"


@pytest.mark.asyncio
async def test_comic_preview_bridge_forwarder():
    """兼容代理方法调用同一个漫画预览处理器。"""
    bridge = object.__new__(PluginPageWebUIBridge)
    bridge.template_routes = MagicMock()
    expected = {"data_url": "data:image/webp;base64,example"}
    bridge.template_routes.api_get_comic_template_preview = AsyncMock(
        return_value=expected
    )
    assert await bridge.api_get_comic_template_preview() == expected
    bridge.template_routes.api_get_comic_template_preview.assert_awaited_once()


def test_comic_preview_registration_and_openapi_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    """AstrBot 注册只读路由，契约声明模板标识、尺寸选项和空图语义。"""
    monkeypatch.setattr(trace_context, "_global_active_task_manager", None)
    bridge = PluginPageWebUIBridge(MagicMock(), MagicMock(), MagicMock())
    with monkeypatch.context() as context:
        from src.infrastructure.logging.plugin_log_buffer import global_log_buffer

        context.setattr(global_log_buffer, "register_listener", lambda _listener: None)
        bridge.register_routes()
    registrations = bridge.context.register_web_api.call_args_list
    registration = next(
        call.args
        for call in registrations
        if call.args[0] == f"/{PLUGIN_NAME}/comic/templates/preview"
    )
    assert registration[1] == bridge.template_routes.api_get_comic_template_preview
    assert registration[2] == ["GET"]
    operation = generate_openapi_spec()["paths"]["/comic/templates/preview"]["get"]
    assert operation["parameters"][0]["required"] is True
    assert operation["parameters"][1]["schema"]["enum"] == ["thumbnail", "full"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    data_schema = response_schema["properties"]["data"]
    assert data_schema["required"] == ["data_url"]
    assert data_schema["properties"]["data_url"]["nullable"] is True
