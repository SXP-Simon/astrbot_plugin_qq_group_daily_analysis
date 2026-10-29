"""头像预取应区分常规身份与匿名身份引用，并忽略未知括号文本。"""

import pytest

from src.domain.value_objects import GoldenQuote, SummaryTopic, UserTitle
from src.infrastructure.reporting.render_data_preparer import RenderDataPreparer


@pytest.mark.parametrize("anonymous", [True, False])
def test_avatar_selection_collects_only_relevant_identity_sources(anonymous):
    topics = [SummaryTopic("话题", [], "[topic-mention] [unknown]", [" contributor "])]
    titles = [UserTitle("成员", "title-user", "称号", "INTJ", "[title-mention]")]
    quotes = [GoldenQuote("内容", "成员", "[quote-mention] [unknown]", "title-user")]
    known = {key: {} for key in ("topic-mention", "quote-mention", "title-mention")}
    expected = {"title-user", "topic-mention", "quote-mention"}
    if anonymous:
        expected.update({"contributor", "title-mention"})
    assert RenderDataPreparer._collect_avatar_user_ids(topics, titles, quotes, known, anonymous) == expected


def test_empty_sections_do_not_require_any_avatar():
    assert RenderDataPreparer._collect_avatar_user_ids([], [], [], {"known": {}}, True) == set()
