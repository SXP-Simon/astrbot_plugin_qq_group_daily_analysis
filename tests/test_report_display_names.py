"""HTML/T2I 昵称展示与特殊 Unicode 字符的回归测试。"""

import html
from unittest.mock import AsyncMock

import pytest
from test_template_section_conditional_rendering import (
    MockConfigManager,
    create_analysis_result,
)

from src.infrastructure.reporting.display_names import normalize_display_name
from src.infrastructure.reporting.generators import ReportGenerator


@pytest.mark.parametrize("name,expected", [
    ("\n\x0e\x12本间心铃\n\t\n\x07纱A\x1a\x11\x10\x00", "本间心铃 纱A"),
    ("𒀱𒂝𒈔𒅒𒈔𒅒𒇫𒄆𒇫", "𒀱𒂝𒈔𒅒𒈔𒅒𒇫𒄆𒇫"),
    ("👩‍💻 ❤️ 𠮷 é", "👩‍💻 ❤️ 𠮷 é"),
    ('\x00<script>alert("hi")</script>\n甲 & 乙', '<script>alert("hi")</script> 甲 & 乙'),
])
@pytest.mark.parametrize("template_file", ["image_template.html", "html_template.html"])
@pytest.mark.asyncio
async def test_html_names_are_clean_but_not_treated_as_markup(tmp_path, name, expected, template_file):
    generator = ReportGenerator(MockConfigManager("HatsuneMiku"), tmp_path)
    generator._avatar_service.get_user_avatar = AsyncMock(
        return_value=generator._avatar_service.get_default_avatar_base64()
    )
    data = create_analysis_result()
    data["user_analysis"] = {"123456": {"nickname": name}}
    data["topics"][0].contributors = [name]
    data["topics"][0].detail = "第一行\n[123456] 的回应"
    data["user_titles"][0].name = name
    data["statistics"].golden_quotes[0].sender = name
    data["statistics"].golden_quotes[0].reason = "第一行\n[123456] 的回应"
    try:
        prepared = await generator.prepare_render_data(data)
        for section in ("topics_html", "titles_html", "quotes_html"):
            assert expected in html.unescape(prepared[section])
            assert not any(char in prepared[section] for char in ("\x00", "\x07", "\x0e", "\x12"))
            assert '<script>alert(' not in prepared[section]
        assert "第一行<br>" in prepared["topics_html"]
        assert "第一行<br>" in prepared["quotes_html"]
        rendered = generator.html_templates.render_template(
            template_file, template_theme="HatsuneMiku", **prepared
        )
        assert rendered
        assert expected in html.unescape(rendered)
        assert '<script>alert(' not in rendered
        assert data["user_analysis"]["123456"]["nickname"] == name
        assert data["statistics"].golden_quotes[0].sender == name
        assert data["topics"][0].contributors == [name]
    finally:
        await generator.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("name,expected", [("\x07铃\n音👩‍💻\x00", "铃 音👩‍💻"), ("\x00\x07", "123456")])
async def test_html_callback_names_share_normalization_and_empty_fallback(tmp_path, name, expected):
    generator = ReportGenerator(MockConfigManager("HatsuneMiku"), tmp_path)
    generator._avatar_service.get_user_avatar = AsyncMock(return_value="")
    nickname = AsyncMock(return_value=name)
    try:
        rendered = str(await generator._render_mentions("[123456]", None, nickname_getter=nickname))
        assert expected in html.unescape(rendered)
        assert "\x07" not in rendered and "\x00" not in rendered
        nickname.assert_awaited_once_with("123456")
    finally:
        await generator.close()


def test_cuneiform_is_preserved():
    name = "𒀱𒂝𒈔𒅒𒈔𒅒𒇫𒄆𒇫"
    assert normalize_display_name(name) == name
