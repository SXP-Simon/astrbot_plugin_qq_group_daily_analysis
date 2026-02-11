import asyncio
import os
import sys
import types
from pathlib import Path

# ==========================================
# 1. Environment Setup
# ==========================================
# Add project root to sys.path so we can import 'astrbot' and plugin modules
# In docker environment:
# /AstrBot
# /AstrBot/data/plugins/astrbot_plugin_qq_group_daily_analysis
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
    def __init__(self):
        pass

    def get_pdf_output_dir(self):
        # Output to the scripts directory for easy access
        return os.path.join(current_dir, "output")

    def get_pdf_filename_format(self):
        return "mock_report_{group_id}_{date}.pdf"

    def get_max_topics(self):
        return 5

    def get_max_user_titles(self):
        return 8

    def get_max_golden_quotes(self):
        return 5

    def get_report_template(self):
        return "scrapbook"

    def get_enable_user_card(self):
        return True

    @property
    def playwright_available(self):
        return True

    def get_browser_path(self):
        return ""


async def mock_get_user_avatar(user_id: str) -> str:
    # Return a known avatar URL for testing
    return f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"


# ==========================================
# 3. Main Execution
# ==========================================
async def main():
    print("Initializing ReportGenerator...")
    config_manager = MockConfigManager()
    generator = ReportGenerator(config_manager)

    # Override avatar fetching to avoid real network calls during testing
    generator._get_user_avatar_data = mock_get_user_avatar

    # 1. Mock Analysis Result using Entities
    stats = GroupStatistics(
        message_count=1280,
        total_characters=8500,
        participant_count=42,
        most_active_period="20:00-22:00",
        emoji_count=156,
        emoji_statistics=EmojiStatistics(face_count=100, mface_count=56),
        activity_visualization=ActivityVisualization(
            hourly_activity={i: (i * 5) % 65 for i in range(24)},
            daily_activity={"2026-02-11": 1280},
        ),
    )

    topics = [
        SummaryTopic(
            topic="AstrBot新功能",
            detail="大家对PDF生成功能的讨论非常热烈，提出了很多优化建议。",
            contributors=["开发者", "测试员"],
        ),
        SummaryTopic(
            topic="周末计划",
            detail="有人提议去爬山，也有人想在家打游戏。",
            contributors=["旅行家", "宅男"],
        ),
        SummaryTopic(
            topic="代码调试",
            detail="关于Python异步编程的深入探讨。",
            contributors=["小白", "大神"],
        ),
        SummaryTopic(
            topic="美食分享",
            detail="深夜放毒，发了很多火锅和烧烤的照片。",
            contributors=["吃货A", "吃货B"],
        ),
        SummaryTopic(
            topic="模组推荐",
            detail="推荐了一些好用的Minecraft模组。",
            contributors=["MC玩家"],
        ),
    ]

    user_titles = [
        UserTitle(
            name="极客",
            user_id="10001",
            title="代码魔术师",
            mbti="INTJ",
            reason="总是能用一行代码解决复杂问题。",
        ),
        UserTitle(
            name="社牛",
            user_id="10002",
            title="气氛组组长",
            mbti="ENFP",
            reason="群里冷场时总能第一时间活跃气氛。",
        ),
        UserTitle(
            name="百科",
            user_id="10003",
            title="移动维基",
            mbti="ISTJ",
            reason="不管问什么问题，他都知道答案。",
        ),
        UserTitle(
            name="潜水",
            user_id="10004",
            title="深海幽灵",
            mbti="INTP",
            reason="虽然很少说话，但每次发言都直击要害。",
        ),
        UserTitle(
            name="欧皇",
            user_id="10005",
            title="天选之子",
            mbti="ESFJ",
            reason="抽卡次次出金，让人羡慕嫉妒恨。",
        ),
    ]

    stats.golden_quotes = [
        GoldenQuote(
            sender="大佬",
            content="这代码能跑就行，别动它！",
            reason="至理名言，动了就崩。",
            user_id="20001",
        ),
        GoldenQuote(
            sender="萌新",
            content="为什么我的报错和你不一？",
            reason="经典的灵魂发问。",
            user_id="20002",
        ),
        GoldenQuote(
            sender="群主",
            content="再发涩图全部禁言！",
            reason="来自管理层的威慑。",
            user_id="888888",
        ),
    ]
    stats.token_usage = TokenUsage(
        prompt_tokens=2000, completion_tokens=1000, total_tokens=3000
    )

    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles,
    }

    print("Generating PDF Report...")
    group_id = "test_group_mock"

    # Direct generation
    pdf_path = await generator.generate_pdf_report(analysis_result, group_id=group_id)

    if pdf_path:
        print(f"\n[SUCCESS] PDF Generated Successfully: {pdf_path}")
        if os.path.exists(pdf_path):
            print(f"File Size: {os.path.getsize(pdf_path) / 1024:.2f} KB")
        else:
            print(
                "[WARN] Generated path returned but file not found on local disk (might be in container)."
            )
    else:
        print("\n[FAILURE] PDF Generation Failed.")


if __name__ == "__main__":
    asyncio.run(main())
