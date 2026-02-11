import argparse
import asyncio
import os
import sys
import types
from pathlib import Path

# ==========================================
# 1. Environment Setup
# ==========================================
# Add src to path so we can import our modules
# Assuming we are in scripts/
current_dir = os.path.dirname(os.path.abspath(__file__))
plugin_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.insert(0, plugin_root)

# Mock astrbot.api before importing our modules
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
from src.infrastructure.reporting.templates import HTMLTemplates  # noqa: E402


class MockConfigManager:
    def __init__(self, template_name: str = "scrapbook") -> None:
        self.template_name = template_name

    def get_report_template(self) -> str:
        return self.template_name

    def get_max_topics(self) -> int:
        return 5

    def get_max_user_titles(self) -> int:
        return 8

    def get_max_golden_quotes(self) -> int:
        return 5

    def get_pdf_output_dir(self) -> str:
        return "data/pdf"

    def get_pdf_filename_format(self) -> str:
        return "report_{group_id}_{date}.pdf"

    def get_enable_user_card(self) -> bool:
        return True

    @property
    def playwright_available(self) -> bool:
        return True

    def get_browser_path(self) -> str:
        return ""


async def mock_get_user_avatar(user_id: str) -> str:
    # Return a known avatar URL for testing
    return f"https://q4.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"


async def debug_render(
    template_name: str, output_file: str = "debug_output.html"
) -> None:
    # 1. Setup Mock Data
    config_manager = MockConfigManager(template_name)

    # 2. Mock Analysis Result using Entities
    stats = GroupStatistics(
        message_count=1250,
        total_characters=45000,
        participant_count=42,
        most_active_period="20:00 - 22:00",
        emoji_count=156,
        emoji_statistics=EmojiStatistics(face_count=100, mface_count=56),
        activity_visualization=ActivityVisualization(
            hourly_activity={
                i: (10 + i * 5 if i < 12 else 100 - i * 2) for i in range(24)
            }
        ),
    )

    topics = [
        SummaryTopic(
            topic="关于AstrBot插件开发的讨论",
            contributors=["张三", "李四", "王五"],
            detail="大家深入探讨了如何利用Jinja2模板渲染出精美的分析报告，并分享了调试技巧。",
        ),
        SummaryTopic(
            topic="午餐吃什么的终极哲学问题",
            contributors=["赵六", "孙七"],
            detail="群友们就黄焖鸡米饭和螺蛳粉的优劣进行了长达一小时的辩论，最终未能达成共识。",
        ),
        SummaryTopic(
            topic="新出的3A大作测评",
            contributors=["周八", "吴九"],
            detail="分享了最新游戏的通关体验，讨论了画面表现和剧情走向。",
        ),
    ]

    user_titles = [
        UserTitle(
            name="张三",
            user_id="123456789",
            title="代码收割机",
            mbti="INTJ",
            reason="在短短一小时内提交了10个PR，效率惊人。",
        ),
        UserTitle(
            name="李四",
            user_id="987654321",
            title="群聊气氛组",
            mbti="ENFP",
            reason="总能精准接住每一个冷笑话，让群里充满快活的气息。",
        ),
        UserTitle(
            name="潜水员",
            user_id="112233445",
            title="深夜潜水员",
            mbti="INFP",
            reason="总是在凌晨三点出没，留下几句深奥的话语后消失。",
        ),
    ]

    golden_quotes = [
        GoldenQuote(
            content="代码写得好，下班走得早。",
            sender="张三",
            reason="深刻揭示了程序员的生存法则",
            user_id="123456789",
        ),
        GoldenQuote(
            content="这个Bug我不修，它就是个Feature。",
            sender="李四",
            reason="经典的开发辩解",
            user_id="987654321",
        ),
        GoldenQuote(
            content="PHP是世界上最好的语言！",
            sender="王五",
            reason="引发了长达3小时的群聊大讨论",
            user_id="112233445",
        ),
    ]

    stats.golden_quotes = golden_quotes
    stats.token_usage = TokenUsage(
        prompt_tokens=1500, completion_tokens=800, total_tokens=2300
    )

    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles,
        "analysis_date": "2026年02月11日",
        "group_id": "123456",
        "group_name": "测试群组",
    }

    # 3. Initialize Generator
    generator = ReportGenerator(config_manager)

    # Override internal methods to facilitate debugging without real dependencies
    generator._get_user_avatar_data = mock_get_user_avatar

    # 4. Prepare Render Data
    # Note: _prepare_render_data handles converting Entities to template-friendly dicts
    render_payload = await generator._prepare_render_data(analysis_result)

    # 5. Render Main Template
    html_templates = HTMLTemplates(config_manager)
    # Get image template string
    raw_template = html_templates.get_image_template()

    if not raw_template:
        print(f"[ERROR] Failed to load template for '{template_name}'")
        return

    # Use generator's internal renderer
    final_html = generator._render_html_template(raw_template, render_payload)

    # 6. Save to file
    output_path = Path(output_file)
    output_path.write_text(final_html, encoding="utf-8")

    print(
        f"Successfully rendered template '{template_name}' to {output_path.absolute()}"
    )
    print("You can now open this file with your browser to debug your HTML/CSS.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug render tool for astrbot_plugin_qq_group_daily_analysis report templates."
    )
    parser.add_argument(
        "-t",
        "--template",
        type=str,
        default="scrapbook",
        help="Template name to render (default: scrapbook)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="debug_output.html",
        help="Output HTML file path (default: debug_output.html)",
    )
    args = parser.parse_args()

    asyncio.run(debug_render(args.template, args.output))


if __name__ == "__main__":
    main()
