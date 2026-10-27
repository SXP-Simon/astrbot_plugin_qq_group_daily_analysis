"""设置处理器保留预览选择参数，不触发模板修改。"""

from types import SimpleNamespace
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
