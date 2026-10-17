"""词云 Web API 与宿主上传契约、群覆盖和手动 HTML 附送回归。"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.datastructures import UploadFile

from src.application.handlers.analysis_command_handler import AnalysisCommandHandler
from src.domain.value_objects.wordcloud import WordCloudData, WordFrequency
from src.infrastructure.config.config_manager import ConfigManager
from src.infrastructure.webui import web_compat
from src.infrastructure.webui.routes import config_routes
from src.infrastructure.webui.routes.config_routes import ConfigRoutes
from src.infrastructure.webui.routes.wordcloud_routes import WordCloudRoutes


class UploadedFileMapping:
    """模拟宿主 PluginMultiDict 的公开 items() 接口。"""

    def __init__(self, upload: UploadFile) -> None:
        self.upload = upload

    def items(self) -> list[tuple[str, UploadFile]]:
        return [("file", self.upload)]


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [True, False])
async def test_font_upload_accepts_async_host_files_and_legacy_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, asynchronous: bool
):
    content = b"wOF2" + bytes(60)
    upload = UploadFile(io.BytesIO(content), filename="自定义文楷.woff2")
    host = SimpleNamespace(
        files=AsyncMock(return_value=UploadedFileMapping(upload))
        if asynchronous
        else {"file": upload}
    )
    monkeypatch.setattr(web_compat._RequestProxy, "_get_target", lambda _self: host)
    route = WordCloudRoutes(SimpleNamespace(data_dir=tmp_path))
    response = await route.api_upload_font()
    assert response["status_code"] == 200
    filename = hashlib.sha256(content).hexdigest() + ".woff2"
    assert response["data"]["data"]["id"] == "uploaded:" + filename
    assert (tmp_path / "wordcloud_fonts" / filename).read_bytes() == content
    assert (tmp_path / "wordcloud_fonts" / (filename + ".label")).read_text(
        encoding="utf-8"
    ) == "自定义文楷.woff2"
    if asynchronous:
        host.files.assert_awaited_once()


@pytest.mark.asyncio
async def test_font_upload_rejects_content_with_wrong_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    upload = UploadFile(io.BytesIO(b"not-a-font-file"), filename="fake.woff2")
    host = SimpleNamespace(files=AsyncMock(return_value={"file": upload}))
    monkeypatch.setattr(web_compat._RequestProxy, "_get_target", lambda _self: host)
    response = await WordCloudRoutes(
        SimpleNamespace(data_dir=tmp_path)
    ).api_upload_font()
    assert response["status_code"] == 400
    assert not (tmp_path / "wordcloud_fonts").exists()


@pytest.mark.asyncio
async def test_config_save_preserves_free_form_group_overrides(
    monkeypatch: pytest.MonkeyPatch,
):
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    # AstrBot 将 object 下的未知键当成过期配置删除；动态会话映射必须声明为 dict。
    assert schema["wordcloud"]["items"]["group_overrides"]["type"] == "dict"
    manager = object.__new__(ConfigManager)
    manager.config = {}
    monkeypatch.setattr(manager, "save_config", MagicMock())
    overrides = {
        "bot-one:GroupMessage:123": {"word_spacing": 0, "keep_words": ["高性能萝卜子"]},
        "bot-two:GroupMessage:123": {"font": "serif", "send_with_report": False},
    }
    body = {"config": {"wordcloud": {"word_spacing": 10, "group_overrides": overrides}}}
    monkeypatch.setattr(
        config_routes, "request", SimpleNamespace(json=AsyncMock(return_value=body))
    )
    routes = ConfigRoutes(SimpleNamespace(config_manager=manager))
    response = await routes.api_save_config()
    assert response["status_code"] == 200
    assert manager.config["wordcloud"]["group_overrides"] == overrides
    assert manager.get_wordcloud_options("bot-one:GroupMessage:123").word_spacing == 0
    assert manager.get_wordcloud_options("bot-two:GroupMessage:123").font == "serif"
    assert not manager.get_wordcloud_options(
        "bot-two:GroupMessage:123"
    ).send_with_report
    manager.save_config.assert_called_once()


def html_handler(
    tmp_path: Path, *, url_only: bool, send_ok: bool, fallback_error: bool = False
):
    calls: list[str] = []

    async def send_url(*_args):
        calls.append("report")
        return send_ok

    async def send_fallback(*_args):
        calls.append("report")
        if fallback_error:
            raise RuntimeError("文件发送失败")

    async def send_cloud(*_args):
        calls.append("wordcloud")
        return True

    config = MagicMock()
    config.get_output_format.return_value = ["html"]
    config.get_report_template.return_value = "ATRI"
    config.get_html_only_url.return_value = url_only
    config.get_html_base_url.return_value = "https://example.com/reports"
    config.get_html_output_dir.return_value = str(tmp_path)
    renderer = MagicMock()
    renderer.generate_html_report = AsyncMock(
        return_value=(str(tmp_path / "report.html"), None)
    )
    renderer.build_html_caption.return_value = ""
    adapter = MagicMock()
    adapter.platform_id = "bot"
    adapter.get_platform_name.return_value = "onebot"
    adapter.send_text = AsyncMock(side_effect=send_url)
    sender = SimpleNamespace(send_file=AsyncMock(return_value=False))
    delivery = SimpleNamespace(send_with_report=AsyncMock(side_effect=send_cloud))
    handler = AnalysisCommandHandler(
        config,
        MagicMock(),
        MagicMock(),
        renderer,
        AsyncMock(),
        message_sender=sender,
        plugin_data_dir=tmp_path,
        wordcloud_delivery=delivery,
    )
    event = MagicMock()
    event.send = AsyncMock(side_effect=send_fallback)
    event.plain_result.side_effect = lambda text: text
    cloud = WordCloudData((WordFrequency("高性能", 3, 2),))
    result = {
        "group_id": "123",
        "platform_id": "bot",
        "adapter": adapter,
        "analysis_result": {"wordcloud": cloud},
    }
    return handler, event, result, calls, delivery


@pytest.mark.asyncio
@pytest.mark.parametrize("send_ok", [True, False])
async def test_manual_html_url_attaches_wordcloud_only_after_success(
    tmp_path: Path, send_ok: bool
):
    handler, event, result, calls, delivery = html_handler(
        tmp_path, url_only=True, send_ok=send_ok
    )
    outputs = [output async for output in handler.send_analysis_report(event, result)]
    assert calls == (["report", "wordcloud"] if send_ok else ["report"])
    if send_ok:
        delivery.send_with_report.assert_awaited_once_with(
            result["analysis_result"]["wordcloud"], "123", "bot"
        )
        assert not outputs
    else:
        assert outputs == ["报告外链发送失败，请稍后重试。"]


@pytest.mark.asyncio
async def test_manual_html_event_file_fallback_attaches_wordcloud(tmp_path: Path):
    handler, event, result, calls, delivery = html_handler(
        tmp_path, url_only=False, send_ok=True
    )
    assert [
        output async for output in handler.send_analysis_report(event, result)
    ] == []
    assert calls == ["report", "wordcloud"]
    event.send.assert_awaited_once()
    delivery.send_with_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_html_failed_event_file_fallback_does_not_attach_wordcloud(
    tmp_path: Path,
):
    handler, event, result, calls, delivery = html_handler(
        tmp_path, url_only=False, send_ok=False, fallback_error=True
    )
    with pytest.raises(RuntimeError, match="文件发送失败"):
        _ = [output async for output in handler.send_analysis_report(event, result)]
    assert calls == ["report"]
    delivery.send_with_report.assert_not_awaited()
