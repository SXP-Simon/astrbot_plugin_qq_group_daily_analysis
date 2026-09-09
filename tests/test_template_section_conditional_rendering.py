import asyncio
from types import SimpleNamespace
import pytest
from src.domain.models.data_models import (
    SummaryTopic,
    UserTitle,
    GoldenQuote,
    GroupStatistics,
    ActivityVisualization,
)
from src.infrastructure.reporting.generators import ReportGenerator


class MockConfigManager:
    def __init__(self, template_name='scrapbook'):
        self.template_name = template_name

    def get_report_template(self):
        return self.template_name

    def get_max_topics(self):
        return 10

    def get_max_user_titles(self):
        return 10

    def get_max_golden_quotes(self):
        return 10

    def get_profile_display_mode(self):
        return 'mbti'

    def get_profile_mapping_config(self):
        return {}

    def get_profile_image_opacity(self):
        return 0.12

    def get_profile_image_size_mode(self):
        return 'contain'

    def get_t2i_font_source(self):
        return 'local'

    def get_t2i_google_fonts_mirror(self):
        return ''

    def get_t2i_gstatic_mirror(self):
        return ''

    def get_t2i_atri_font_mirror(self):
        return 'https://mirror.example.com'

    def get_t2i_max_concurrent(self):
        return 2


async def fake_avatar(uid, ns=None):
    return None


def create_analysis_result(empty=False):
    if empty:
        topics = []
        user_titles = []
        golden_quotes = []
    else:
        topics = [
            SummaryTopic(topic='测试话题1', contributors=['张三', '李四'], detail='这是测试话题详情')
        ]
        user_titles = [
            UserTitle(user_id='123456', name='张三', title='水群之王', mbti='ENTP', reason='天天在水群')
        ]
        golden_quotes = [
            GoldenQuote(user_id='123456', sender='张三', content='名言名句', reason='锐评测试')
        ]

    statistics = GroupStatistics(
        message_count=100,
        participant_count=10,
        total_characters=5000,
        emoji_count=20,
        most_active_period='14:00-15:00',
        token_usage=SimpleNamespace(total_tokens=100, prompt_tokens=50, completion_tokens=50),
        golden_quotes=golden_quotes,
    )

    return {
        'statistics': statistics,
        'topics': topics,
        'user_titles': user_titles,
        'user_analysis': {},
        'activity_visualization': ActivityVisualization(hourly_activity={i: 5 for i in range(24)}),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('template_theme', ['scrapbook', 'HatsuneMiku', 'ATRI', 'art_nouveau'])
@pytest.mark.parametrize('template_file', ['image_template.html', 'html_template.html'])
async def test_template_hides_empty_sections_when_no_content(tmp_path, template_theme, template_file):
    config = MockConfigManager(template_theme)
    generator = ReportGenerator(config, tmp_path)
    try:
        analysis_result = create_analysis_result(empty=True)

        render_data = await generator._prepare_render_data(
            analysis_result,
            avatar_url_getter=fake_avatar,
            nickname_getter=lambda uid: 'Nick',
            chart_template='activity_chart.html',
        )
        rendered_html = generator.html_templates.render_template(
            template_file,
            template_theme=template_theme,
            **render_data,
        )

        if template_theme == 'HatsuneMiku':
            assert '话题总结' not in rendered_html
            assert '群友画像' not in rendered_html
            assert '今日圣经' not in rendered_html
            assert '群聊锐评' not in rendered_html
        elif template_theme == 'ATRI':
            assert '高亮记忆碎片' not in rendered_html
            assert '神人名片颁发' not in rendered_html
            assert '亚托莉的宝藏瓶' not in rendered_html
            assert '亚托莉观测报告' not in rendered_html
        elif template_theme == 'scrapbook':
            assert '今日话题 Topics' not in rendered_html
            assert '群友画像 Portraits' not in rendered_html
            assert '群贤毕至 Bible Quotes' not in rendered_html
            assert '群聊质量锐评' not in rendered_html
        elif template_theme == 'art_nouveau':
            assert '核心热议话题' not in rendered_html
            assert '群友特质画像' not in rendered_html
            assert '精选金句回响' not in rendered_html
            assert '群聊氛围洞察' not in rendered_html
    finally:
        await generator.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('template_theme', ['scrapbook', 'HatsuneMiku', 'ATRI', 'art_nouveau'])
@pytest.mark.parametrize('template_file', ['image_template.html', 'html_template.html'])
async def test_template_shows_sections_when_content_present(tmp_path, template_theme, template_file):
    config = MockConfigManager(template_theme)
    generator = ReportGenerator(config, tmp_path)
    try:
        analysis_result = create_analysis_result(empty=False)

        render_data = await generator._prepare_render_data(
            analysis_result,
            avatar_url_getter=fake_avatar,
            nickname_getter=lambda uid: 'Nick',
            chart_template='activity_chart.html',
        )
        rendered_html = generator.html_templates.render_template(
            template_file,
            template_theme=template_theme,
            **render_data,
        )

        if template_theme == 'HatsuneMiku':
            assert '话题总结' in rendered_html
            assert '群友画像' in rendered_html
            assert '今日圣经' in rendered_html
            assert '测试话题1' in rendered_html
            assert '水群之王' in rendered_html
            assert '名言名句' in rendered_html
        elif template_theme == 'ATRI':
            assert '高亮记忆碎片' in rendered_html
            assert '神人名片颁发' in rendered_html
            assert '亚托莉的宝藏瓶' in rendered_html
            assert '测试话题1' in rendered_html
            assert '水群之王' in rendered_html
            assert '名言名句' in rendered_html
        elif template_theme == 'scrapbook':
            assert '今日话题 Topics' in rendered_html
            assert '群友画像 Portraits' in rendered_html
            assert '群贤毕至 Bible Quotes' in rendered_html
            assert '测试话题1' in rendered_html
            assert '水群之王' in rendered_html
            assert '名言名句' in rendered_html
        elif template_theme == 'art_nouveau':
            assert '核心热议话题' in rendered_html
            assert '群芳雅鉴' in rendered_html
            assert '精选金句回响' in rendered_html
            assert '测试话题1' in rendered_html
            assert '水群之王' in rendered_html
            assert '名言名句' in rendered_html
    finally:
        await generator.close()
