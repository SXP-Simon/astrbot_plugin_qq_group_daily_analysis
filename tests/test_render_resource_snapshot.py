"""主模板与子组件的资源快照应保持独立稳定。"""

import pytest
from test_rendering_strategies import rendering as rendering


@pytest.mark.parametrize("environment", ["Mainland", "Overseas"])
def test_explicit_resources_are_copied_into_stable_template_context(rendering, environment):
    _manager, generator, _png = rendering
    resources = {
        "cdn_base_url": "https://cdn.example",
        "google_fonts": "https://fonts.example",
        "gstatic": "https://static.example",
    }
    context, cdn = generator._preparer_service._build_resource_context(
        environment, resources, "network", True
    )
    resources.update(cdn_base_url="https://changed.example", google_fonts="https://changed-fonts.example")
    assert cdn == "https://cdn.example"
    assert context["t2i_npm_mirror"] == "https://cdn.example/npm"
    assert context["t2i_google_fonts_mirror"] == "https://fonts.example"
    assert context["t2i_gstatic_mirror"] == "https://static.example"
    assert context["t2i_font_source"] == environment
    assert context["hide_user_names"] is True
