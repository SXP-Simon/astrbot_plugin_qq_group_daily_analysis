"""手动 HTML 报告外链与文件交付的回归。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.application.handlers.analysis_command_handler import AnalysisCommandHandler


def delivery_handler(tmp_path, *, only_url, base_url="", sent=True):
    handler = object.__new__(AnalysisCommandHandler)
    handler.config_manager = SimpleNamespace(
        get_html_only_url=lambda: only_url,
        get_html_base_url=lambda: base_url,
        get_html_output_dir=lambda: str(tmp_path),
    )
    handler.plugin_data_dir = tmp_path
    handler.report_generator = SimpleNamespace(build_html_caption=lambda _: "报告说明")
    handler.message_sender = SimpleNamespace(send_file=AsyncMock(return_value=sent))
    event = SimpleNamespace(
        plain_result=lambda text: ("text", text),
        chain_result=lambda chain: ("file", chain),
    )
    return handler, event


@pytest.mark.asyncio
async def test_html_delivery_encodes_external_url_and_skips_file(tmp_path):
    handler, event = delivery_handler(tmp_path, only_url=True, base_url="https://reports.example/base/")
    result = [message async for message in handler._send_html_report(
        event, str(tmp_path / "中文 #.html"), "123", "platform", Mock()
    )]
    assert len(result) == 1
    assert result[0][1].endswith("https://reports.example/base/%E4%B8%AD%E6%96%87%20%23.html")
    handler.message_sender.send_file.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("sent", [True, False])
async def test_html_delivery_without_base_url_falls_back_to_file(tmp_path, sent):
    handler, event = delivery_handler(tmp_path, only_url=True, sent=sent)
    path = str(tmp_path / "report.html")
    result = [message async for message in handler._send_html_report(
        event, path, "123", "platform", Mock()
    )]
    handler.message_sender.send_file.assert_awaited_once_with(
        "123", path, caption="报告说明", platform_id="platform"
    )
    assert [message[0] for message in result] == ([] if sent else ["file", "text"])
