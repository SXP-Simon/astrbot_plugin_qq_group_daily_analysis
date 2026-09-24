"""
领域模型 (Domain Models) 单元测试
覆盖充血模型的自校验、不变性维护与业务行为。
"""

import pytest

from src.domain.models.data_models import (
    GoldenQuote,
    QualityDimension,
    QualityReview,
    SummaryTopic,
    UserTitle,
)


def test_summary_topic_enrichment():
    """测试 SummaryTopic 领域模型的校验与贡献者去重维护"""
    # 1. 验证有效性检查
    valid_topic = SummaryTopic(
        topic="二次元讨论",
        contributors=["用户A"],
        detail="详细讨论了某动画剧情",
        contributor_ids=["10001"],
    )
    assert valid_topic.is_valid() is True

    invalid_topic = SummaryTopic(
        topic="   ",
        contributors=[],
        detail="",
    )
    assert invalid_topic.is_valid() is False

    # 2. 验证贡献者安全添加与去重行为
    valid_topic.add_contributor("用户B", "10002")
    assert "用户B" in valid_topic.contributors
    assert "10002" in valid_topic.contributor_ids

    # 重复添加不会导致列表膨胀
    valid_topic.add_contributor("用户B", "10002")
    assert valid_topic.contributors.count("用户B") == 1
    assert valid_topic.contributor_ids.count("10002") == 1


def test_user_title_and_golden_quote_validation():
    """测试 UserTitle 与 GoldenQuote 领域实体的自校验规则"""
    valid_title = UserTitle(
        name="Simon",
        user_id="123456",
        title="水群之王",
        mbti="INTJ",
        reason="今天发送了 999 条消息",
    )
    assert valid_title.is_valid() is True

    invalid_title = UserTitle(
        name="",
        user_id="123456",
        title="",
        mbti="",
        reason="",
    )
    assert invalid_title.is_valid() is False

    valid_quote = GoldenQuote(
        content="代码如诗，bug如风",
        sender="Developer",
        reason="意境深远",
        user_id="888888",
    )
    assert valid_quote.is_valid() is True

    invalid_quote = GoldenQuote(
        content="   ",
        sender="",
        reason="",
    )
    assert invalid_quote.is_valid() is False


def test_quality_review_normalization():
    """测试 QualityReview 维度归一化与有效性校验业务规则"""
    dim1 = QualityDimension(name="干货分享", percentage=40.0, comment="很有收获")
    dim2 = QualityDimension(name="日常闲聊", percentage=30.0, comment="轻松愉快")
    dim3 = QualityDimension(name="表情包大战", percentage=10.0, comment="图力拉满")

    assert dim1.is_valid() is True
    invalid_dim = QualityDimension(name="", percentage=-5.0, comment="")
    assert invalid_dim.is_valid() is False

    review = QualityReview(
        title="今日聊天锐评",
        subtitle="质量极高的一天",
        dimensions=[dim1, dim2, dim3],
        summary="大家交流非常活跃",
    )
    assert review.is_valid() is True

    # 初始总和为 80%，执行归一化后总和应逼近 100%
    review.normalize()
    total_percentage = sum(d.percentage for d in review.dimensions)
    assert abs(total_percentage - 100.0) < 0.5
