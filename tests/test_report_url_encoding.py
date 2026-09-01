import asyncio
from pathlib import Path

from src.infrastructure.reporting.dispatcher import ReportDispatcher


class FakeConfigManager:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def get_html_only_url(self):
        return True

    def get_html_base_url(self):
        return "https://example.top/123"

    def get_html_output_dir(self):
        return str(self.output_dir)


class FakeReportGenerator:
    def __init__(self, html_path: Path):
        self.html_path = html_path

    async def generate_html_report(self, *args, **kwargs):
        return str(self.html_path), None

    def build_html_caption(self, html_path):
        return "caption"


class FakeBotManager:
    def get_adapter(self, platform_id):
        return None


class FakeMessageSender:
    def __init__(self):
        self.bot_manager = FakeBotManager()
        self.sent_text = None

    async def send_text(self, group_id, text, platform_id):
        self.sent_text = text
        return True

    async def send_file(self, *args, **kwargs):
        raise AssertionError("URL-only dispatch should not send the HTML file")


def test_html_only_url_encodes_non_ascii_path(tmp_path):
    html_path = tmp_path / "如果2333.html"
    sender = FakeMessageSender()
    dispatcher = ReportDispatcher(
        FakeConfigManager(tmp_path),
        FakeReportGenerator(html_path),
        sender,
    )

    sent = asyncio.run(dispatcher._dispatch_html("group", {}, "onebot"))

    assert sent is True
    assert sender.sent_text == (
        "📊 今日群聊分析报告已生成：\n"
        "https://example.top/123/%E5%A6%82%E6%9E%9C2333.html"
    )
