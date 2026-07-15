import asyncio
import json
from types import SimpleNamespace

from src.domain.models.data_models import (
    ActivityVisualization,
    GoldenQuote,
    GroupStatistics,
    QualityDimension,
    QualityReview,
)
from src.infrastructure.reporting.generators import ReportGenerator


class FakeConfig:
    def get_max_topics(self):
        return 10

    def get_max_user_titles(self):
        return 10

    def get_max_golden_quotes(self):
        return 10


def build_generator_without_io():
    generator = object.__new__(ReportGenerator)
    generator.config_manager = FakeConfig()
    return generator


def test_text_report_removes_official_identity_values():
    generator = build_generator_without_io()
    openid = "A1B2C3D4_OPENID"
    statistics = SimpleNamespace(
        message_count=2,
        participant_count=1,
        total_characters=10,
        emoji_count=0,
        most_active_period="12:00-13:00",
        golden_quotes=[
            SimpleNamespace(
                content="测试内容",
                sender=openid,
                reason=f"由 {openid} 发出",
            )
        ],
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [
            SimpleNamespace(
                topic="测试话题",
                contributors=[openid],
                detail=f"{openid} 参与讨论",
            )
        ],
        "user_titles": [
            SimpleNamespace(
                name=openid,
                title="龙王",
                mbti="ENTP",
                reason=f"{openid} 发言最多",
            )
        ],
        "user_analysis": {openid: {"nickname": openid}},
    }

    report = generator.generate_text_report(analysis_result, hide_user_names=True)

    assert openid not in report
    assert "测试内容" in report
    assert "龙王" in report
    assert "参与者:" not in report


def test_mentions_support_alphanumeric_openid_and_hide_text():
    generator = build_generator_without_io()
    openid = "A1B2C3D4_OPENID"

    async def fake_avatar(*args, **kwargs):
        return "data:image/png;base64,AAAA"

    generator._get_user_avatar = fake_avatar
    rendered = asyncio.run(
        generator._render_mentions(
            f"成员 [{openid}] 发言",
            avatar_url_getter=None,
            user_analysis={openid: {"nickname": openid}},
            avatar_cache_namespace="official-main",
            avatar_reuse_registry={},
            avatar_reuse_aliases={},
            hide_user_names=True,
        )
    )

    rendered_text = str(rendered)
    assert openid not in rendered_text
    assert "user-capsule-avatar" in rendered_text
    assert "成员" in rendered_text


def test_html_sidecar_export_removes_nested_identity_values():
    generator = build_generator_without_io()
    openid = "A1B2C3D4_OPENID"
    statistics = GroupStatistics(
        message_count=2,
        participant_count=1,
        total_characters=10,
        emoji_count=0,
        most_active_period="12:00-13:00",
        golden_quotes=[
            GoldenQuote(
                content="测试内容",
                sender=openid,
                reason=f"由 {openid} 发出",
                user_id=openid,
            )
        ],
        activity_visualization=ActivityVisualization(
            user_activity_ranking=[
                {
                    "user_id": openid,
                    "name": openid,
                    "message_count": 2,
                }
            ]
        ),
        chat_quality_review=QualityReview(
            title=f"{openid} 的聊天质量",
            subtitle="测试",
            dimensions=[
                QualityDimension(
                    name="活跃度",
                    percentage=100,
                    comment=f"{openid} 最活跃",
                )
            ],
            summary=f"总结 {openid}",
        ),
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [],
        "user_titles": [],
        "user_analysis": {openid: {"nickname": openid}},
        "chat_quality_review": statistics.chat_quality_review,
    }

    sanitized = generator._sanitize_analysis_result_for_export(analysis_result)
    exported = json.dumps(sanitized, ensure_ascii=False)

    assert openid not in exported
    assert sanitized["user_analysis"] == {}
    assert (
        sanitized["statistics"]["activity_visualization"]["user_activity_ranking"] == []
    )
