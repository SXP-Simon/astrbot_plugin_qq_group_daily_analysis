"""质量评价组件应兼容领域对象及旧字典，并保留匿名与资源选项。"""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from test_rendering_strategies import rendering as rendering
from test_template_section_conditional_rendering import create_analysis_result

from src.domain.value_objects import QualityDimension, QualityReview


@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize("anonymous", [True, False])
def test_quality_component_preserves_inputs_and_anonymizes_all_text(rendering, legacy, anonymous):
    _manager, generator, _png = rendering
    preparer = generator._preparer_service
    analysis = create_analysis_result()
    analysis["user_analysis"] = {"user-id": {"nickname": "成员甲"}}
    review = QualityReview("成员甲评价", "user-id副标题", [QualityDimension("成员甲维度", 100, "user-id评论")], "成员甲总结")
    analysis["chat_quality_review"] = review.to_dict() if legacy else review
    before = deepcopy(analysis["chat_quality_review"])
    context, _ = preparer._build_resource_context("Mainland", None, "network", anonymous)
    preparer.html_templates = Mock()
    preparer.html_templates.render_template.return_value = "quality HTML"
    assert preparer._render_chat_quality(analysis["chat_quality_review"], analysis, "HatsuneMiku", context) == "quality HTML"
    rendered = preparer.html_templates.render_template.call_args.kwargs
    assert rendered["hide_user_names"] is anonymous
    assert rendered["t2i_font_source"] == "Mainland"
    assert ("成员甲" in rendered["title"]) is not anonymous
    assert ("user-id" in rendered["subtitle"]) is not anonymous
    assert ("成员甲" in rendered["summary"]) is not anonymous
    assert ("成员甲" in rendered["dimensions"][0]["name"]) is not anonymous
    assert ("user-id" in rendered["dimensions"][0]["comment"]) is not anonymous
    assert analysis["chat_quality_review"] == before
