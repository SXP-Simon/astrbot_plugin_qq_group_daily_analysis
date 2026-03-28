import asyncio
import os
import sys
import types
from pathlib import Path

# ==========================================
# 1. Environment Setup
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
plugin_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, plugin_root)

# Mock astrbot.api
astrbot_api = types.ModuleType("astrbot.api")


class MockLogger:
    def info(self, msg, *args, **kwargs):
        print(f"[INFO] {msg}")

    def error(self, msg, *args, **kwargs):
        print(f"[ERROR] {msg}")

    def warning(self, msg, *args, **kwargs):
        print(f"[WARN] {msg}")

    def debug(self, msg, *args, **kwargs):
        print(f"[DEBUG] {msg}")

    def log(self, level, msg, *args, **kwargs):
        print(f"[LOG {level}] {msg}")

    def isEnabledFor(self, level):
        return True


astrbot_api.logger = MockLogger()
astrbot_api.AstrBotConfig = dict
sys.modules["astrbot.api"] = astrbot_api

# Mock astrbot.core.utils.astrbot_path
astrbot_core_utils = types.ModuleType("astrbot.core.utils")
astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")
astrbot_path.get_astrbot_data_path = lambda: Path(".")
sys.modules["astrbot.core.utils"] = astrbot_core_utils
sys.modules["astrbot.core.utils.astrbot_path"] = astrbot_path

# Now import plugin modules
from src.domain.entities.analysis_result import (  # noqa: E402
    ActivityVisualization,
    EmojiStatistics,
    GoldenQuote,
    GroupStatistics,
    SummaryTopic,
    TokenUsage,
    UserTitle,
)
from src.infrastructure.reporting.generators import ReportGenerator  # noqa: E402


# ==========================================
# 2. Mocks
# ==========================================
class MockConfigManager:
    def __init__(self, theme="scrapbook"):
        self.theme = theme

    def get_pdf_output_dir(self):
        return os.path.join(current_dir, "output_all")

    def get_pdf_filename_format(self):
        return f"debug_{self.theme}_{{group_id}}_{{date}}.pdf"

    def get_max_topics(self):
        return 5

    def get_max_user_titles(self):
        return 8

    def get_max_golden_quotes(self):
        return 5

    def get_report_template(self):
        return self.theme

    def get_enable_user_card(self):
        return True

    def get_t2i_max_concurrent(self):
        return 2

    @property
    def playwright_available(self):
        return True

    def get_browser_path(self):
        return ""


async def mock_get_user_avatar(avatar_id: str, avatar_url_getter=None) -> str:
    return f"https://q4.qlogo.cn/headimg_dl?dst_uin={avatar_id}&spec=640"


# ==========================================
# 3. Main Execution
# ==========================================
async def generate_theme(theme_name):
    print(f"\n>>> Generating PDF for theme: {theme_name}")
    config_manager = MockConfigManager(theme_name)
    data_dir = Path(current_dir) / "data"
    generator = ReportGenerator(config_manager, data_dir)
    generator._get_user_avatar = mock_get_user_avatar

    stats = GroupStatistics(
        message_count=1280,
        total_characters=8500,
        participant_count=42,
        most_active_period="20:00-22:00",
        emoji_count=156,
        emoji_statistics=EmojiStatistics(face_count=100, mface_count=56),
        activity_visualization=ActivityVisualization(
            hourly_activity={i: (i * 5) % 65 for i in range(24)},
            daily_activity={"2026-03-25": 1280},
        ),
    )

    topics = [
        SummaryTopic(
            topic="AstrBot新功能",
            detail="大家对PDF生成功能的讨论非常热烈。",
            contributors=["开发者", "测试员"],
        ),
        SummaryTopic(
            topic="代码调试",
            detail="关于Python异步编程的深入探讨。",
            contributors=["大神"],
        ),
        SummaryTopic(
            topic="周三摸鱼",
            detail="今天群里大家都在发表情包。",
            contributors=["全体群友"],
        ),
    ]

    user_titles = [
        UserTitle(
            name="Simon",
            user_id="10001",
            title="极客之魂",
            mbti="INTJ",
            reason="完成了所有PDF模板的优化。",
        ),
        UserTitle(
            name="Bot",
            user_id="10002",
            title="全能助手",
            mbti="ENFJ",
            reason="一直在努力工作。",
        ),
    ]

    stats.golden_quotes = [
        GoldenQuote(
            sender="Simon",
            content="这PDF现在看起来高端多了！",
            reason="这是真的。",
            user_id="10001",
        ),
        GoldenQuote(
            sender="User",
            content="能不能不分页？",
            reason="用户反馈。",
            user_id="10002",
        ),
    ]
    stats.token_usage = TokenUsage(
        prompt_tokens=2500, completion_tokens=1500, total_tokens=4000
    )

    class MockDimension:
        def __init__(self, name, percentage, comment, color):
            self.name, self.percentage, self.comment, self.color = (
                name,
                percentage,
                comment,
                color,
            )

    class MockChatQualityReview:
        def __init__(self):
            self.title = "今日群聊质量分析"
            self.subtitle = "基于AI的深度神经网络评估"
            self.dimensions = [
                MockDimension("讨论活跃度", 95, "大家讨论非常热烈", "#FF5722"),
                MockDimension("情感温度", 88, "群内氛围融洽", "#E91E63"),
            ]
            self.summary = "整体聊天的质量很高，技术讨论和日常闲聊达到了完美的平衡。"

    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles,
        "chat_quality_review": MockChatQualityReview(),
        "user_analysis": {"10001": {"nickname": "Simon"}, "10002": {"nickname": "Bot"}},
        "token_usage": stats.token_usage,
    }

    try:
        pdf_path = await generator.generate_pdf_report(
            analysis_result, group_id="test_group"
        )
        if pdf_path and os.path.exists(pdf_path):
            print(f"[SUCCESS] {theme_name} PDF generated: {pdf_path}")
        else:
            print(f"[FAILURE] {theme_name} PDF generation failed or file not found.")
    except Exception as e:
        print(f"[ERROR] Failed to generate {theme_name}: {e}")


async def main():
    themes = [
        "scrapbook",
        "hack",
        "retro_futurism",
        "simple",
        "spring_festival",
        "format",
        "HatsuneMiku",
    ]
    for theme in themes:
        await generate_theme(theme)


if __name__ == "__main__":
    asyncio.run(main())
