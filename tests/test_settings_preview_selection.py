"""设置处理器保留预览选择参数，不触发模板修改。"""

from types import SimpleNamespace
import logging
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.handlers.settings_command_handler import SettingsCommandHandler


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["", "2", "ATRI"])
async def test_preview_selection_is_forwarded_without_config_changes(selection):
    config, service = Mock(), Mock()
    service.list_available_templates.return_value = ["scrapbook", "ATRI"]
    router = SimpleNamespace(
        ensure_handlers_registered=AsyncMock(),
        handle_view_templates=AsyncMock(return_value=(True, ["preview"])),
    )
    context = Mock()
    handler = SettingsCommandHandler(config, service, router, Mock(), context=context)
    event = SimpleNamespace(should_call_llm=Mock())
    results = [
        result async for result in handler.handle_view_templates(event, "qq", selection)
    ]
    assert results == ["preview"]
    router.ensure_handlers_registered.assert_awaited_once_with(context)
    router.handle_view_templates.assert_awaited_once_with(
        event=event,
        platform_id="qq",
        available_templates=["scrapbook", "ATRI"],
        template_input=selection,
    )
    config.set_report_template.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["context", "router", "declined"])
async def test_qq_fallback_is_visible_and_does_not_return_nodes(caplog, missing):
    caplog.set_level(logging.DEBUG, logger="astrbot-test")
    service = Mock()
    service.list_available_templates.return_value = ["scrapbook"]
    router = SimpleNamespace(
        ensure_handlers_registered=AsyncMock(),
        handle_view_templates=AsyncMock(return_value=(False, [])),
    )
    result = Mock()
    result.use_markdown.return_value = result
    result.use_t2i.return_value = result
    event = SimpleNamespace(
        should_call_llm=Mock(),
        get_platform_name=lambda: "qq_official",
        plain_result=Mock(return_value=result),
    )
    handler = SettingsCommandHandler(
        Mock(),
        service,
        None if missing == "router" else router,
        Mock(),
        context=None if missing == "context" else Mock(),
    )
    assert [reply async for reply in handler.handle_view_templates(event, "qq")] == [
        result
    ]
    service.build_template_preview_nodes.assert_not_called()
    assert any(
        record.levelno == logging.WARNING and "阻止 Nodes" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prefixes, prefix", [(["!", "/"], "!"), (["", "/"], ""), (["/", "!"], "/")]
)
async def test_settings_usage_and_preview_fallback_use_bound_prefix(prefixes, prefix):
    config, service = Mock(), Mock()
    config.get_output_format.return_value = ["image"]
    config.get_auto_analysis_time.return_value = ["12:00"]
    config.get_group_list.return_value = []
    service.list_available_templates.return_value = ["scrapbook", "ATRI"]
    context = SimpleNamespace(get_config=Mock(return_value={"wake_prefix": prefixes}))
    handler = SettingsCommandHandler(config, service, None, None, context=context)
    event = SimpleNamespace(
        unified_msg_origin="qq:GroupMessage:bound",
        should_call_llm=Mock(),
        get_platform_name=lambda: "aiocqhttp",
        get_self_id=lambda: "bot",
        plain_result=lambda text: text,
        chain_result=lambda nodes: nodes,
    )
    formats = [r async for r in handler.handle_set_output_format(event)]
    assert f"用法: {prefix}设置格式" in formats[0]
    templates = [r async for r in handler.handle_set_report_template(event)]
    assert f"用法: {prefix}设置模板" in templates[0]
    assert f"使用 {prefix}查看模板" in templates[0]
    status = [
        r
        async for r in handler.handle_analysis_settings(event, "status", "bound", "qq")
    ]
    assert f"其他命令: {prefix}设置格式, {prefix}增量状态" in status[0]
    await anext(handler.handle_view_templates(event, "qq"))
    assert (
        service.build_template_preview_nodes.call_args.kwargs["command_prefix"]
        == prefix
    )
    assert all(
        call.kwargs == {"umo": event.unified_msg_origin}
        for call in context.get_config.call_args_list
    )
    config.set_report_template.assert_not_called()
