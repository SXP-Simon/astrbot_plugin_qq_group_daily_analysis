"""各平台共用的模板预览来源选择。"""

from unittest.mock import Mock

import pytest

from src.application.services.template_command_service import TemplateCommandService


def test_local_preview_takes_precedence_over_cdn(tmp_path, monkeypatch):
    config = Mock()
    service = TemplateCommandService(str(tmp_path), config)
    monkeypatch.setattr(
        service, "resolve_template_preview_path", lambda _: "local/preview.png"
    )
    assert service.resolve_template_preview_source("scrapbook") == "local/preview.png"
    config.get_template_assets_base_url.assert_not_called()


def test_builtin_fallback_uses_configured_cdn_but_custom_does_not(
    tmp_path, monkeypatch
):
    config = Mock()
    config.get_template_assets_base_url.return_value = (
        "https://example.test/gh/repo/assets"
    )
    service = TemplateCommandService(str(tmp_path), config)
    monkeypatch.setattr(service, "resolve_template_preview_path", lambda _: None)
    assert (
        service.resolve_template_preview_source("scrapbook")
        == "https://example.test/gh/repo/assets/scrapbook-demo.webp"
    )
    assert service.resolve_template_preview_source("my_custom_theme") is None
    config.get_template_assets_base_url.assert_called_once()


@pytest.mark.parametrize("prefix", ["", "!", "/", "分析 "])
def test_preview_list_uses_supplied_prefix(tmp_path, prefix):
    service = TemplateCommandService(str(tmp_path))
    nodes = service.build_template_preview_nodes(
        [], "scrapbook", "bot", command_prefix=prefix
    )
    assert f"使用 {prefix}设置模板 [序号] 切换" in nodes.nodes[0].content[0].text
