import os
import sys
import asyncio
import argparse
from datetime import datetime
from pathlib import Path

# Add src to path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__)))

# Mock astrbot.api before importing our modules
import types
astrbot_api = types.ModuleType("astrbot.api")
astrbot_api.logger = types.ModuleType("logger")
astrbot_api.logger.info = lambda x, *args, **kwargs: print(f"[INFO] {x}")
astrbot_api.logger.error = lambda x, *args, **kwargs: print(f"[ERROR] {x}")
astrbot_api.logger.warning = lambda x, *args, **kwargs: print(f"[WARN] {x}")
astrbot_api.AstrBotConfig = dict
sys.modules["astrbot.api"] = astrbot_api

from src.reports.templates import HTMLTemplates
from src.reports.generators import ReportGenerator
from src.models.data_models import (
    GroupStatistics, SummaryTopic, UserTitle, GoldenQuote, 
    TokenUsage, EmojiStatistics, ActivityVisualization
)

class MockConfigManager:
    def __init__(self, template_name="format"):
        self.template_name = template_name
    
    def get_report_template(self):
        return self.template_name
    
    def get_max_topics(self):
        return 5
    
    def get_max_user_titles(self):
        return 8
    
    def get_max_golden_quotes(self):
        return 5
    
    def get_pdf_output_dir(self):
        return "data/pdf"
    
    def get_pdf_filename_format(self):
        return "report_{group_id}_{date}.pdf"

async def mock_get_user_avatar(user_id):
    # Return a placeholder or a real base64 if needed
    # For debugging, a simple colored square or a known avatar is fine
    return "https://q4.qlogo.cn/headimg_dl?dst_uin=123456789&spec=640"

async def debug_render(template_name: str, output_file: str = "debug_output.html"):
    # 1. Setup Mock Data
    config_manager = MockConfigManager(template_name)
    
    # Mock Analysis Result
    stats = GroupStatistics(
        message_count=1250,
        total_characters=45000,
        participant_count=42,
        most_active_period="20:00 - 22:00",
        golden_quotes=[
            GoldenQuote(content="代码写得好，下班走得早。", sender="张三", reason="深刻揭示了程序员的生存法则"),
            GoldenQuote(content="这个Bug我不修，它就是个Feature。", sender="李四", reason="经典的开发辩解"),
            GoldenQuote(content="PHP是世界上最好的语言！", sender="王五", reason="引发了长达3小时的群聊大讨论")
        ],
        emoji_count=156,
        emoji_statistics=EmojiStatistics(face_count=100, mface_count=56),
        activity_visualization=ActivityVisualization(
            hourly_activity={i: (10 + i*5 if i < 12 else 100 - i*2) for i in range(24)}
        ),
        token_usage=TokenUsage(prompt_tokens=1500, completion_tokens=800, total_tokens=2300)
    )
    
    topics = [
        SummaryTopic(topic="关于AstrBot插件开发的讨论", contributors=["张三", "李四", "王五"], detail="大家深入探讨了如何利用Jinja2模板渲染出精美的分析报告，并分享了调试技巧。"),
        SummaryTopic(topic="午餐吃什么的终极哲学问题", contributors=["赵六", "孙七"], detail="群友们就黄焖鸡米饭和螺蛳粉的优劣进行了长达一小时的辩论，最终未能达成共识。"),
        SummaryTopic(topic="新出的3A大作测评", contributors=["周八", "吴九"], detail="分享了最新游戏的通关体验，讨论了画面表现和剧情走向。")
    ]
    
    user_titles = [
        UserTitle(name="张三", qq=123456789, title="代码收割机", mbti="INTJ", reason="在短短一小时内提交了10个PR，效率惊人。"),
        UserTitle(name="李四", qq=987654321, title="群聊气氛组", mbti="ENFP", reason="总能精准接住每一个冷笑话，让群里充满快活的气息。"),
        UserTitle(name="王五", qq=112233445, title="深夜潜水员", mbti="INFP", reason="总是在凌晨三点出没，留下几句深奥的话语后消失。")
    ]
    
    analysis_result = {
        "statistics": stats,
        "topics": topics,
        "user_titles": user_titles
    }
    
    # 2. Initialize Generator
    generator = ReportGenerator(config_manager)
    
    # Override _get_user_avatar to avoid real network calls if desired, 
    # but here we'll just let it use the mock URL
    generator._get_user_avatar = mock_get_user_avatar
    
    # 3. Render Data
    render_payload = await generator._prepare_render_data(analysis_result)
    
    # 4. Render Main Template
    # We'll test the image template
    html_templates = HTMLTemplates(config_manager)
    raw_template = html_templates.get_image_template()
    
    final_html = generator._render_html_template(raw_template, render_payload)
    
    # 5. Save to file
    output_path = Path(output_file)
    output_path.write_text(final_html, encoding="utf-8")

    print(f"Successfully rendered template '{template_name}' to {output_path.absolute()}")
    print("You can now open this file with VS Code Live Server to debug your HTML/CSS.")

def main():
    parser = argparse.ArgumentParser(
        description="Debug render tool for astrbot-qq-group-daily-analysis report templates."
    )
    parser.add_argument(
        "-t", "--template",
        type=str,
        default="retro_futurism",
        help="Template name to render (default: retro_futurism)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="debug_output.html",
        help="Output HTML file path (default: debug_output.html)"
    )
    args = parser.parse_args()

    asyncio.run(debug_render(args.template, args.output))

if __name__ == "__main__":
    main()
