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
