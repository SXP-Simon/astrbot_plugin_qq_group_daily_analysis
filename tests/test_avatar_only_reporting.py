import asyncio
import inspect
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
from src.infrastructure.reporting.qq_official_markdown import (
    QQOfficialMarkdownReportGenerator,
)
from src.infrastructure.reporting.templates import HTMLTemplates


class FakeConfig:
    def get_max_topics(self):
        return 10

    def get_max_user_titles(self):
        return 10

    def get_max_golden_quotes(self):
        return 10

    def get_qq_official_t2i_summary_dashboard_enabled(self):
        return True


def build_generator_without_io():
    generator = object.__new__(ReportGenerator)
    generator.config_manager = FakeConfig()
    return generator


def generate_qq_markdown(generator, analysis_result):
    markdown_report, _ = asyncio.run(
        generator.generate_qq_official_markdown_report(analysis_result)
    )
    return markdown_report


def test_standard_text_report_keeps_existing_identity_format():
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

    report = generator.generate_text_report(analysis_result)

    assert openid in report
    assert "测试内容" in report
    assert "龙王" in report
    assert f"参与者: {openid}" in report
    assert f"• {openid} - 龙王 (ENTP)" in report
    assert f'1. "测试内容" —— {openid}' in report


def test_standard_text_report_api_has_no_qq_platform_switches():
    parameters = inspect.signature(ReportGenerator.generate_text_report).parameters

    assert list(parameters) == ["self", "analysis_result"]


def test_non_qq_text_report_does_not_use_qq_histogram_path():
    generator = build_generator_without_io()
    statistics = SimpleNamespace(
        message_count=3,
        participant_count=1,
        total_characters=12,
        emoji_count=0,
        most_active_period="03:00-04:00",
        golden_quotes=[],
        activity_visualization=SimpleNamespace(hourly_activity={3: 3}),
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [],
        "user_titles": [],
        "user_analysis": {},
    }

    report = generator.generate_text_report(analysis_result)

    assert "🎯 群聊日常分析报告" in report
    assert "## ⏰ 活跃时间分布" not in report
    assert "████" not in report
    assert "![24小时活跃分布" not in report


def test_qq_official_markdown_uses_mentions_for_all_identity_sections():
    generator = build_generator_without_io()
    openid = "A1B2C3D4_OPENID"
    nickname = "测试群友"
    statistics = SimpleNamespace(
        message_count=2,
        participant_count=1,
        total_characters=10,
        emoji_count=0,
        most_active_period="12:00-13:00",
        golden_quotes=[
            SimpleNamespace(
                content=f"[{openid}] 说了一句话",
                sender=nickname,
                reason=f"{nickname} 的发言很精彩",
                user_id=openid,
            )
        ],
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [
            SimpleNamespace(
                topic="测试话题",
                contributors=[nickname],
                contributor_ids=[openid],
                detail=f"{nickname} 和 {openid} 参与讨论",
            )
        ],
        "user_titles": [
            SimpleNamespace(
                name=nickname,
                user_id=openid,
                title="龙王",
                mbti="ENTP",
                reason=f"[{openid}] 发言最多",
            )
        ],
        "user_analysis": {openid: {"nickname": nickname}},
    }

    report = generate_qq_markdown(generator, analysis_result)

    assert report.count(f"<@{openid}>") >= 6
    without_mentions = report.replace(f"<@{openid}>", "")
    assert openid not in without_mentions
    assert nickname not in without_mentions
    assert "## 💬 热门话题" in report
    assert "**参与者**" in report
    assert "**龙王**" in report
    assert f"- **1. <@{openid}> 说了一句话** — <@{openid}>" in report
    assert f"  > <@{openid}> 的发言很精彩" in report
    assert f"> 1. <@{openid}> 说了一句话" not in report


def test_qq_official_markdown_keeps_content_when_identity_id_is_missing():
    generator = build_generator_without_io()
    statistics = SimpleNamespace(
        message_count=1,
        participant_count=1,
        total_characters=4,
        emoji_count=0,
        most_active_period="12:00-13:00",
        golden_quotes=[
            SimpleNamespace(
                content="测试内容",
                sender="无法映射的用户",
                reason="理由保留",
                user_id="",
            )
        ],
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [],
        "user_titles": [
            SimpleNamespace(
                name="无法映射的用户",
                user_id="",
                title="龙王",
                mbti="",
                reason="称号理由",
            )
        ],
        "user_analysis": {},
    }

    report = generate_qq_markdown(generator, analysis_result)

    assert "<@" not in report
    assert "龙王" in report
    assert "称号理由" in report
    assert "测试内容" in report
    assert "理由保留" in report
    assert "无法映射的用户" not in report
    assert "- **1. 测试内容**" in report
    assert "  > 理由保留" in report
    assert "> 1. 测试内容" not in report


def test_qq_official_scripture_spacing_and_optional_reason():
    generator = build_generator_without_io()
    statistics = SimpleNamespace(
        message_count=2,
        participant_count=2,
        total_characters=8,
        emoji_count=0,
        most_active_period="12:00-13:00",
        golden_quotes=[
            SimpleNamespace(
                content="第一条",
                sender="甲",
                reason="第一条理由",
                user_id="A_OPENID",
            ),
            SimpleNamespace(
                content="第二条",
                sender="乙",
                reason="",
                user_id="",
            ),
        ],
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [],
        "user_titles": [],
        "user_analysis": {
            "A_OPENID": {"nickname": "甲"},
        },
    }

    report = generate_qq_markdown(generator, analysis_result)

    assert "- **1. 第一条** — <@A_OPENID>\n  > 第一条理由\n\n- **2. 第二条**" in report
    assert "- **2. 第二条** —" not in report


def test_qq_official_markdown_renders_simple_hourly_bar_chart():
    generator = build_generator_without_io()
    statistics = SimpleNamespace(
        message_count=17,
        participant_count=3,
        total_characters=80,
        emoji_count=1,
        most_active_period="03:00-04:00",
        golden_quotes=[],
        activity_visualization=SimpleNamespace(
            hourly_activity={0: 0, "1": 2, 2: 5, "3": 10}
        ),
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [],
        "user_titles": [],
        "user_analysis": {},
    }

    report = generate_qq_markdown(generator, analysis_result)

    assert "## ⏰ 活跃时间分布" in report
    assert "- 00:00　—　0" in report
    assert "- 01:00　███　2" in report
    assert "- 02:00　██████　5" in report
    assert "- 03:00　████████████　10" in report
    chart_section = report.split("## ⏰ 活跃时间分布", 1)[1].split("## 💬 热门话题", 1)[
        0
    ]
    assert sum(1 for line in chart_section.splitlines() if line.startswith("- ")) == 24


def test_qq_official_markdown_omits_empty_hourly_bar_chart():
    generator = build_generator_without_io()
    statistics = SimpleNamespace(
        message_count=0,
        participant_count=0,
        total_characters=0,
        emoji_count=0,
        most_active_period="",
        golden_quotes=[],
        activity_visualization=SimpleNamespace(hourly_activity={}),
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [],
        "user_titles": [],
        "user_analysis": {},
    }

    report = generate_qq_markdown(generator, analysis_result)

    assert "## ⏰ 活跃时间分布" not in report


def test_qq_official_t2i_summary_dashboard_replaces_text_summary():
    generator = build_generator_without_io()
    generator.html_templates = HTMLTemplates(generator.config_manager)
    generator._render_semaphore = asyncio.Semaphore(1)
    statistics = SimpleNamespace(
        message_count=10,
        participant_count=2,
        total_characters=50,
        emoji_count=4,
        most_active_period="03:00-04:00",
        golden_quotes=[],
        activity_visualization=SimpleNamespace(hourly_activity={1: 2, 3: 10}),
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [],
        "user_titles": [],
        "user_analysis": {},
    }
    render_calls = []

    async def fake_html_render(template, data, return_url, options):
        render_calls.append((template, data, return_url, options))
        return "https://t2i.example/chart.png"

    markdown_report, fallback_report = asyncio.run(
        generator.generate_qq_official_markdown_report(
            analysis_result, fake_html_render
        )
    )

    assert len(render_calls) == 1
    template, data, return_url, options = render_calls[0]
    assert "群聊日常分析" in template
    assert "消息" in template
    assert "参与" in template
    assert "字符" in template
    assert "表情" in template
    assert "高峰" in template
    assert ">10<" in template
    assert ">2<" in template
    assert ">50<" in template
    assert ">4<" in template
    assert ">03–04<" in template
    assert 'class="histogram"' in template
    assert template.count('class="hour"') == 24
    assert template.count('class="metric"') == 5
    assert ">00<" in template
    assert ">23<" in template
    assert "background: transparent !important" in template
    assert "background: #000000" in template
    assert "font-size: 25px" in template
    assert "font-size: 28px" in template
    assert "font-size: 14px" in template
    assert "#1d1d1f" not in template
    assert "#6e6e73" not in template
    assert "#86868b" not in template
    assert "rgba(0, 0, 0" not in template
    assert "text-shadow" not in template
    assert "linear-gradient" not in template
    assert "#5b8ff9" not in template
    assert data == {}
    assert return_url is True
    assert options["type"] == "png"
    assert options["omit_background"] is True
    assert options["clip"] == {"x": 0, "y": 0, "width": 800, "height": 360}
    assert "https://t2i.example/chart.png" in markdown_report
    assert "# 🎯 群聊日常分析报告" not in markdown_report
    assert "📅" not in markdown_report
    assert "## 📊 基础统计" not in markdown_report
    assert "消息总数" not in markdown_report
    assert "## ⏰ 活跃时间分布" not in markdown_report
    assert "████" not in markdown_report
    assert "https://t2i.example/chart.png" not in fallback_report
    assert "# 🎯 群聊日常分析报告" in fallback_report
    assert "📅" in fallback_report
    assert "## 📊 基础统计" in fallback_report
    assert "消息总数" in fallback_report
    assert "## ⏰ 活跃时间分布" in fallback_report
    assert "████" in fallback_report


def test_qq_official_t2i_summary_dashboard_switch_disables_rendering():
    class DisabledConfig(FakeConfig):
        def get_qq_official_t2i_summary_dashboard_enabled(self):
            return False

    generator = object.__new__(ReportGenerator)
    generator.config_manager = DisabledConfig()
    statistics = SimpleNamespace(
        message_count=10,
        participant_count=2,
        total_characters=50,
        emoji_count=0,
        most_active_period="03:00-04:00",
        golden_quotes=[],
        activity_visualization=SimpleNamespace(hourly_activity={3: 10}),
    )
    analysis_result = {
        "statistics": statistics,
        "topics": [],
        "user_titles": [],
        "user_analysis": {},
    }

    async def unexpected_render(*args, **kwargs):
        raise AssertionError("T2I should not run when disabled")

    markdown_report, fallback_report = asyncio.run(
        generator.generate_qq_official_markdown_report(
            analysis_result, unexpected_render
        )
    )

    assert markdown_report == fallback_report
    assert "████████████" in markdown_report


def test_qq_official_summary_dashboard_compacts_large_metrics():
    assert QQOfficialMarkdownReportGenerator.format_metric(10_000) == "10K"
    assert QQOfficialMarkdownReportGenerator.format_metric(12_500) == "12.5K"
    assert QQOfficialMarkdownReportGenerator.format_metric(1_000_000) == "1M"
    assert QQOfficialMarkdownReportGenerator.format_metric(1_250_000) == "1.2M"


def test_non_qq_avatar_mentions_ignore_alphanumeric_bracket_text():
    generator = build_generator_without_io()

    async def unexpected_avatar(*args, **kwargs):
        raise AssertionError("non-QQ bracket text must not trigger avatar lookup")

    generator._get_user_avatar = unexpected_avatar
    rendered = asyncio.run(
        generator._render_mentions(
            "保留 [TODO]、[GPT-4] 和 [A_OPENID]",
            avatar_url_getter=None,
            user_analysis={"A_OPENID": {"nickname": "测试用户"}},
            hide_user_names=False,
        )
    )

    rendered_text = str(rendered)
    assert "[TODO]" in rendered_text
    assert "[GPT-4]" in rendered_text
    assert "[A_OPENID]" in rendered_text
    assert "user-capsule" not in rendered_text


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
