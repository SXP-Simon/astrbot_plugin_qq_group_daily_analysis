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
        pass

    def log(self, level, msg, *args, **kwargs):
        pass

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

from src.domain.models.data_models import (  # noqa: E402
    ActivityVisualization,
    EmojiStatistics,
    GroupStatistics,
    QualityReview,
    TokenUsage,
)
from src.infrastructure.reporting.generators import ReportGenerator  # noqa: E402


class MockConfigManager:
    def __init__(self, source: str) -> None:
        self.source = source

    def get_report_template(self) -> str:
        return "simple"

    def get_max_topics(self) -> int:
        return 5

    def get_max_user_titles(self) -> int:
        return 5

    def get_max_golden_quotes(self) -> int:
        return 5

    def get_html_output_dir(self) -> str:
        return "data/html"

    def get_html_filename_format(self) -> str:
        return "report.html"

    def get_enable_user_card(self) -> bool:
        return True

    def get_t2i_font_source(self) -> str:
        return self.source

    def get_t2i_google_fonts_mirror(self) -> str:
        return (
            "https://fonts.loli.net"
            if self.source == "Mainland"
            else "https://fonts.googleapis.com"
        )

    def get_t2i_gstatic_mirror(self) -> str:
        return (
            "https://gstatic.loli.net"
            if self.source == "Mainland"
            else "https://fonts.gstatic.com"
        )

    def get_t2i_atri_font_mirror(self) -> str:
        return "https://tc.ciallo.ccwu.cc"

    def get_profile_display_mode(self) -> str:
        return "mbti"

    def get_profile_image_opacity(self) -> float:
        return 0.2

    def get_profile_image_size_mode(self) -> str:
        return "contain"

    def get_profile_mapping_config(self) -> str:
        return ""

    def get_t2i_max_concurrent(self) -> int:
        return 4

    def get_llm_max_concurrent(self) -> int:
        return 2

    def get_t2i_rendering_strategies(self) -> list:
        return []

    def get_html_base_url(self) -> str:
        return ""


async def mock_get_user_avatar(user_id: str) -> str:
    return f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"


async def verify_rendering(source: str):
    print(f"\n--- Verifying {source} Rendering ---")
    config = MockConfigManager(source)
    data_dir = Path("data/test")
    data_dir.mkdir(parents=True, exist_ok=True)
    generator = ReportGenerator(config, data_dir)

    # Mock avatar cache
    class MockCache(dict):
        def __getitem__(self, key):
            return self.get(key, "")

        def set(self, key, value, expire=None):
            self[key] = value

    generator._avatar_cache = MockCache()

    stats = GroupStatistics(
        message_count=100,
        total_characters=1000,
        participant_count=5,
        most_active_period="12:00",
        golden_quotes=[],
        emoji_count=0,
        emoji_statistics=EmojiStatistics(0, 0),
        activity_visualization=ActivityVisualization({}),
        token_usage=TokenUsage(0, 0, 0),
        chat_quality_review=QualityReview("Test", "Test", [], "Summary"),
    )
    analysis_result = {
        "statistics": stats,
        "topics": [],
        "user_titles": [],
        "user_analysis": {},
        "chat_quality_review": stats.chat_quality_review,
        "analysis_date": "2026-04-25",
        "group_id": "123",
        "group_name": "Test Group",
    }

    render_payload = await generator._prepare_render_data(
        analysis_result, mock_get_user_avatar
    )
    html = generator.html_templates.render_template(
        "image_template.html", **render_payload
    )

    filename = f"test_{source.lower()}.html"
    Path(filename).write_text(html, encoding="utf-8")

    # Verification
    expected_lang = "zh-CN" if source == "Mainland" else "zh-Hant"
    expected_font = (
        "https://fonts.loli.net"
        if source == "Mainland"
        else "https://fonts.googleapis.com"
    )
    expected_gstatic = (
        "https://gstatic.loli.net"
        if source == "Mainland"
        else "https://fonts.gstatic.com"
    )

    success = True
    if f'lang="{expected_lang}"' not in html:
        print(f'[FAIL] Expected lang="{expected_lang}" not found.')
        success = False
    if expected_font not in html:
        print(f'[FAIL] Expected font mirror "{expected_font}" not found.')
        success = False
    if expected_gstatic not in html:
        print(f'[FAIL] Expected gstatic mirror "{expected_gstatic}" not found.')
        success = False

    if success:
        print(f"[PASS] {source} rendering verified. Output saved to {filename}")

    await generator.close()


async def main():
    await verify_rendering("Mainland")
    await verify_rendering("Overseas")


if __name__ == "__main__":
    asyncio.run(main())
