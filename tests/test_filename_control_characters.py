"""群名中的控制字符不能进入追踪号、历史图片或群文件上传名。"""

import asyncio
import re
from contextvars import ContextVar
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from src.application.handlers.analysis_command_handler import AnalysisCommandHandler
from src.application.handlers.comic_command_handler import ComicCommandHandler
from src.infrastructure.reporting.dispatcher import ReportDispatcher
from src.shared import trace_context as trace_module
from src.shared.trace_context import TraceContext, strip_control_characters


CONTROL_CHARACTERS = [
    pytest.param(chr(code), id=f"U+{code:04X}") for code in [*range(0x20), 0x7F]
]


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_trace_id_removes_every_c0_control_and_del(control):
    trace_id = TraceContext.generate("manual", f"日常{control}交流🔥")
    assert re.fullmatch(r"manual_日常交流🔥_\d{8}_\d{6}_[0-9a-f]{12}", trace_id)


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_legacy_component_sanitizer_removes_all_controls_without_changing_display_rules(
    control,
):
    assert strip_control_characters(f" 日常{control} [交流]🔥 ") == " 日常 [交流]🔥 "


@pytest.mark.parametrize(
    "value,expected",
    [
        ("a\x00b\x11c\x1fd\x7fe", "abcde"),
        ("正常群名", "正常群名"),
    ],
)
def test_control_stripping_handles_mixed_controls_and_unchanged_plain_text(
    value, expected
):
    assert strip_control_characters(value) == expected


@pytest.mark.parametrize(
    "group_name,expected",
    [
        ("", ""),
        ("A\x11B\x7fC", "ABC"),
        ("\x00\x10\x11\x1f\x7f", ""),
        (' \t\n/\\:*?"<>|[]{}\r', ""),
        (" 日常 [交流]{摄影}🔥 ", "日常交流摄影🔥"),
        ("\x11一二三四五六七八九十十一\x10", "一二三四五六七八九十"),
    ],
)
def test_trace_id_preserves_empty_fallback_unicode_and_length_limit(
    group_name, expected
):
    trace_id = TraceContext.generate("comic", group_name)
    name_part = f"{expected}_" if expected else ""
    assert re.fullmatch(
        rf"comic_{re.escape(name_part)}\d{{8}}_\d{{6}}_[0-9a-f]{{12}}", trace_id
    )


@pytest.fixture
def png_file(tmp_path):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    image = tmp_path / "source.png"
    image.write_bytes(buffer.getvalue())
    return image


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["report", "comic", "dispatcher"])
@pytest.mark.parametrize("legacy", [False, True])
async def test_control_character_group_names_allow_real_history_images(
    tmp_path, monkeypatch, png_file, kind, legacy
):
    # 隔离追踪上下文，避免测试向宿主仓储写入或留下绑定。
    monkeypatch.setattr(
        trace_module, "_current_trace", ContextVar("filename-test", default=None)
    )
    monkeypatch.setattr(trace_module, "_global_trace_store", None)
    original_trace_id = (
        "legacy_\x11日常\x10交流群\x7f_20261107"
        if legacy
        else TraceContext.generate(kind, "\x11日常\x10交流群\x7f")
    )
    trace = TraceContext(
        trace_id=original_trace_id,
        group_id="123456",
    )
    TraceContext.bind_current(trace)

    if kind == "report":
        handler = AnalysisCommandHandler(
            None, None, None, None, None, plugin_data_dir=tmp_path
        )
        saved = handler.save_report_to_history(str(png_file), "123456")
        assert saved is not None
    elif kind == "comic":
        adapter = SimpleNamespace(send_image=AsyncMock(return_value=True))
        handler = ComicCommandHandler(
            SimpleNamespace(
                get_t2i_max_concurrent=lambda: 1, get_show_report_caption=lambda: False
            ),
            SimpleNamespace(get_adapter=lambda _: adapter, resolve_platform_id=lambda *args: "platform"),
            SimpleNamespace(
                generate_comic=AsyncMock(return_value=(png_file.read_bytes(), None))
            ),
            None,
            plugin_data_dir=tmp_path,
        )
        handler.try_upload_image = AsyncMock()
        # 漫画入口属于后台协程，使用单独 Task 避免临时绑定影响调用方。
        await asyncio.create_task(
            handler.trigger_comic_generation([], "123456", "onebot", "umo")
        )
        adapter.send_image.assert_awaited_once()
        saved = Path(adapter.send_image.await_args.args[1])
    else:
        config = SimpleNamespace(
            get_t2i_rendering_strategy_config=lambda: [{"render_service": "typst"}],
            get_report_template=lambda: "miku",
            get_show_report_caption=lambda: False,
        )
        sender = SimpleNamespace(
            send_image_smart=AsyncMock(return_value=True),
            bot_manager=SimpleNamespace(get_adapter=lambda _: None),
        )
        dispatcher = ReportDispatcher(
            config,
            SimpleNamespace(
                data_dir=tmp_path,
                generate_image_report=AsyncMock(return_value=(str(png_file), None)),
            ),
            sender,
        )
        dispatcher.try_upload_image = AsyncMock()
        assert await dispatcher._dispatch_image("123456", {}, "onebot")
        sender.send_image_smart.assert_awaited_once()
        saved = next((tmp_path / "reports").iterdir())

    assert saved.parent == tmp_path / "reports"
    assert "日常交流群" in saved.name
    assert all(
        ord(character) >= 0x20 and ord(character) != 0x7F for character in saved.name
    )
    assert saved.read_bytes() == png_file.read_bytes()
    with Image.open(saved) as image:
        assert image.format == "PNG"
    assert trace.metadata["report_files"][0]["filename"] == saved.name
    # 文件名可清洗，但数据库关联的旧追踪号必须保持原样。
    assert trace.trace_id == original_trace_id


def test_history_copy_sanitizes_explicit_legacy_id_instead_of_changing_current_trace(
    tmp_path, monkeypatch, png_file
):
    trace = TraceContext(trace_id="current-id", group_id="123456")
    monkeypatch.setattr(TraceContext, "current", staticmethod(lambda: trace))
    monkeypatch.setattr(trace, "persist_snapshot", lambda: None)
    handler = AnalysisCommandHandler(
        None, None, None, None, None, plugin_data_dir=tmp_path
    )
    saved = handler.save_report_to_history(
        str(png_file), "123456", trace_id="legacy_\x11日常\x10交流群\x7f"
    )
    assert saved is not None and "legacy_日常交流群" in saved.name
    assert "current-id" not in saved.name
    assert saved.read_bytes() == png_file.read_bytes()
    assert trace.trace_id == "current-id"


@pytest.mark.asyncio
@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
async def test_upload_filename_removes_every_c0_control_and_del(png_file, control):
    adapter = SimpleNamespace(
        get_group_info=AsyncMock(
            return_value=SimpleNamespace(group_name=f"日常{control}交流🔥")
        ),
        find_or_create_folder=AsyncMock(return_value="folder-id"),
        create_group_file_folder=AsyncMock(),
        get_group_file_root_folders=AsyncMock(return_value=[]),
        upload_group_file_to_folder=AsyncMock(return_value=True),
    )
    handler = AnalysisCommandHandler(
        SimpleNamespace(
            get_enable_group_file_upload=lambda: True,
            get_enable_group_album_upload=lambda: False,
            get_group_file_folder=lambda: "群报告",
        ),
        SimpleNamespace(get_adapter=lambda _: adapter),
        None,
        None,
        None,
    )
    await handler.try_upload_image("123456", str(png_file), "onebot")
    adapter.upload_group_file_to_folder.assert_awaited_once()
    call = adapter.upload_group_file_to_folder.await_args.kwargs
    assert re.fullmatch(
        r"群分析报告_日常交流🔥_\d{4}-\d{2}-\d{2}_\d{4}\.png", call["filename"]
    )
    assert call["file_path"] == str(png_file.resolve())
    assert call["group_id"] == "123456" and call["folder_id"] == "folder-id"
    assert png_file.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "group_name,expected",
    [
        ("\x00\x10\x11\x1f\x7f", "123456"),
        (' /\\:*?"<>|\r\n', "123456"),
        ("  日常 [交流]{摄影}🔥  ", "日常 [交流]{摄影}🔥"),
    ],
)
async def test_upload_name_keeps_display_spacing_and_falls_back_when_empty(
    png_file, group_name, expected
):
    adapter = SimpleNamespace(
        get_group_info=AsyncMock(return_value=SimpleNamespace(group_name=group_name)),
        find_or_create_folder=AsyncMock(),
        create_group_file_folder=AsyncMock(),
        get_group_file_root_folders=AsyncMock(return_value=[]),
        upload_group_file_to_folder=AsyncMock(return_value=True),
    )
    handler = AnalysisCommandHandler(
        SimpleNamespace(
            get_enable_group_file_upload=lambda: True,
            get_enable_group_album_upload=lambda: False,
            get_group_file_folder=lambda: "",
        ),
        SimpleNamespace(get_adapter=lambda _: adapter),
        None,
        None,
        None,
    )
    await handler.try_upload_image("123456", str(png_file), "onebot")
    adapter.upload_group_file_to_folder.assert_awaited_once()
    filename = adapter.upload_group_file_to_folder.await_args.kwargs["filename"]
    assert re.fullmatch(
        rf"群分析报告_{re.escape(expected)}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{4}}\.png",
        filename,
    )
    adapter.find_or_create_folder.assert_not_awaited()
