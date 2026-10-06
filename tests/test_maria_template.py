import json
from pathlib import Path

import pytest

from src.infrastructure.reporting.templates import HTMLTemplates
from test_template_section_conditional_rendering import MockConfigManager


def test_maria_theme_registered_in_all_selection_entry_points():
    """检查内置名称、配置选择器和前端画廊采用同一主题标识。"""
    root = Path(__file__).resolve().parents[1]
    templates = HTMLTemplates(MockConfigManager("maria"))
    item = next(t for t in templates.get_available_templates() if t["id"] == "maria")
    assert item["has_image"] and item["has_html"]
    assert not item["is_custom"]
    schema = json.loads((root / "_conf_schema.json").read_text(encoding="utf-8"))
    assert "maria" in schema["basic"]["items"]["report_template"]["options"]
    frontend = (root / "dashboard/src/entities/report/model/templates.ts").read_text(encoding="utf-8")
    assert 'key: "maria"' in frontend
    assert 'id: "maria"' in frontend


@pytest.mark.parametrize("hide_names", [False, True])
def test_maria_identity_visibility_and_plain_text_escaping(hide_names):
    """隐私模式不泄露姓名，昵称和金句中的 HTML 保持普通文本。"""
    templates = HTMLTemplates(MockConfigManager("maria"))
    marker = "红蔷薇花蕾"
    portraits = templates.render_template(
        "user_title_item.html",
        template_theme="maria",
        hide_user_names=hide_names,
        titles=[{"name": marker + "<script>x</script>", "title": "淑女风采", "mbti": "INFJ", "reason": "优雅品茗"}],
    )
    quotes = templates.render_template(
        "quote_item.html",
        template_theme="maria",
        hide_user_names=hide_names,
        quotes=[{"sender": marker, "content": "<script>alert(1)</script> & 今日学园茶会私语", "reason": ""}],
    )
    assert portraits and quotes
    assert "<script>" not in portraits + quotes
    assert "&lt;script&gt;" in quotes
    if hide_names:
        assert marker not in portraits + quotes
        assert "匿名群友" in portraits + quotes
    else:
        assert marker in portraits + quotes


def test_maria_assets_exist_and_cdn_mirror_fallback():
    """测试素材文件存在且支持 CDN 镜像变量。"""
    root = Path(__file__).resolve().parents[1]
    assets_dir = root / "assets/maria"
    expected_assets = [
        "rosa_chinensis_sachiko_yumi.png",
        "rosa_foetida_yoshino_rei.png",
        "rosa_gigantea_sei_shimako.png",
        "rose_red.png",
        "rose_white.png",
        "rose_yellow.png",
        "sachiko_yumi_wind_ribbon.png",
        "sei_window_observation.png",
        "statue_virgin_mary.png",
        "yumi_and_sei.png",
    ]
    for asset in expected_assets:
        asset_file = assets_dir / asset
        assert asset_file.exists()
        assert asset_file.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

    templates = HTMLTemplates(MockConfigManager("maria"))
    rendered = templates.render_template(
        "image_template.html",
        template_theme="maria",
        t2i_maria_assets_mirror="https://cdn.example.com/assets/maria",
        current_date="2026年10月6日",
        current_datetime="2026-10-06 16:00:00",
        message_count=100,
        participant_count=5,
        total_characters=2000,
        emoji_count=12,
        most_active_period="14:00 - 16:00",
        total_tokens=0,
        prompt_tokens=0,
        completion_tokens=0,
    )
    assert rendered.startswith("<!DOCTYPE html>")
    assert "https://cdn.example.com/assets/maria/statue_virgin_mary.png" in rendered


@pytest.mark.asyncio
async def test_maria_render_data_preparer_injects_maria_cdn_mirror():
    """验证 RenderDataPreparer 正确向主渲染字典注入 t2i_maria_assets_mirror。"""
    from types import SimpleNamespace
    from src.domain.value_objects import GroupStatistics, TokenUsage
    from src.infrastructure.reporting.render_data_preparer import RenderDataPreparer
    from src.shared.constants import DEFAULT_MARIA_ASSETS_CDN_URL

    from unittest.mock import MagicMock
    cfg = MockConfigManager("maria")
    templates = HTMLTemplates(cfg)
    avatar_service = MagicMock()
    visualizer = MagicMock()
    visualizer.render_hourly_chart = MagicMock(return_value="<svg></svg>")
    preparer = RenderDataPreparer(cfg, avatar_service, templates, visualizer)

    stats = GroupStatistics(
        message_count=10,
        total_characters=100,
        participant_count=2,
        most_active_period="12:00 - 13:00",
        golden_quotes=[],
        emoji_count=1,
        token_usage=TokenUsage(total_tokens=100, prompt_tokens=50, completion_tokens=50),
    )
    analysis_result = {
        "statistics": stats,
        "topics": [],
        "user_titles": [],
    }

    render_data = await preparer.prepare_render_data(
        analysis_result=analysis_result,
        template_theme="maria",
    )
    assert "t2i_maria_assets_mirror" in render_data
    assert render_data["t2i_maria_assets_mirror"] == DEFAULT_MARIA_ASSETS_CDN_URL
