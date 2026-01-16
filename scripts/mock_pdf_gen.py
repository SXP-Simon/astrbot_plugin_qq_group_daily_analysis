import asyncio
import os
import sys
from datetime import datetime

# ==========================================
# 1. Environment Setup (Critical for Imports)
# ==========================================
# Add project root to sys.path so we can import 'astrbot' and plugin modules
current_dir = os.path.dirname(os.path.abspath(__file__))
# Assuming structure: .../data/plugins/astrbot_plugin_qq_group_daily_analysis/scripts/mock_pdf_gen.py
# We need to go up 4 levels to reach 'AstrBot-master' root which contains the 'astrbot' package
# data/plugins/astrbot_plugin_qq_group_daily_analysis/scripts -> ... -> AstrBot-master
project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
sys.path.insert(0, project_root)

print(f"Project Root: {project_root}")

# Mock logger before importing anything that uses it
from astrbot.api import logger  # noqa: E402

logger.info = lambda msg, *args, **kwargs: print(f"[INFO] {msg}")
logger.error = lambda msg, *args, **kwargs: print(f"[ERROR] {msg}")
logger.warning = lambda msg, *args, **kwargs: print(f"[WARN] {msg}")

# Now import plugin modules
try:
    from data.plugins.astrbot_plugin_qq_group_daily_analysis.src.core.config import (
        ConfigManager,
    )
    from data.plugins.astrbot_plugin_qq_group_daily_analysis.src.reports.generators import (
        ReportGenerator,
    )
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)


# ==========================================
# 2. Mocks
# ==========================================
class MockConfig:
    def get(self, key, default=None):
        return default

    def get_pdf_output_dir(self):
        # Output to the scripts directory for easy access
        return os.path.join(current_dir, "output")

    def get_pdf_filename_format(self):
        return "mock_report_{group_id}_{date}.pdf"

    def get_max_topics(self):
        return 5

    def get_max_user_titles(self):
        return 5

    def get_max_golden_quotes(self):
        return 5

    @property
    def pyppeteer_available(self):
        return True


# ==========================================
# 3. Main Execution
# ==========================================
async def main():
    print("Initializing ReportGenerator...")
    config_manager = ConfigManager(MockConfig())
    generator = ReportGenerator(config_manager)

    # Mock Data (Rich data to test layout)
    analysis_result = {
        "date": datetime.now().strftime("%Y年%m月%d日"),
        "statistics": {
            "total_messages": 1280,
            "active_users": 42,
            "emoji_count": 156,
            "total_chars": 8500,
            "message_count": 1280,
            "participant_count": 42,
            "total_characters": 8500,
            "most_active_period": "20:00-22:00",
            "token_usage": type(
                "obj",
                (object,),
                {"total_tokens": 500, "prompt_tokens": 200, "completion_tokens": 300},
            ),
            "activity_visualization": type(
                "obj",
                (object,),
                {
                    "hourly_activity": {
                        i: (i * 5) % 60 for i in range(24)
                    },  # Fake activity data
                    "heatmap_data": [],
                },
            ),
        },
        "highlight_time": {
            "period": "21:00-22:00",
            "reason": "夜深人静，群里却热闹非凡，大家都在讨论新的游戏活动。",
        },
        "topics": [
            {
                "topic": "AstrBot新功能",
                "detail": "大家对PDF生成功能的讨论非常热烈，提出了很多优化建议。",
                "contributors": ["开发者", "测试员"],
            },
            {
                "topic": "周末计划",
                "detail": "有人提议去爬山，也有人想在家打游戏。",
                "contributors": ["旅行家", "宅男"],
            },
            {
                "topic": "代码调试",
                "detail": "关于Python异步编程的深入探讨。",
                "contributors": ["小白", "大神"],
            },
            {
                "topic": "美食分享",
                "detail": "深夜放毒，发了很多火锅和烧烤的照片。",
                "contributors": ["吃货A", "吃货B"],
            },
            {
                "topic": "模组推荐",
                "detail": "推荐了一些好用的Minecraft模组。",
                "contributors": ["MC玩家"],
            },
        ],
        "user_titles": [
            {
                "name": "极客",
                "title": "代码魔术师",
                "mbti": "INTJ",
                "reason": "总是能用一行代码解决复杂问题。",
                "qq": "10001",
            },
            {
                "name": "社牛",
                "title": "气氛组组长",
                "mbti": "ENFP",
                "reason": "群里冷场时总能第一时间活跃气氛。",
                "qq": "10002",
            },
            {
                "name": "百科",
                "title": "移动维基",
                "mbti": "ISTJ",
                "reason": "不管问什么问题，他都知道答案。",
                "qq": "10003",
            },
            {
                "name": "潜水",
                "title": "深海幽灵",
                "mbti": "INTP",
                "reason": "虽然很少说话，但每次发言都直击要害。",
                "qq": "10004",
            },
            {
                "name": "欧皇",
                "title": "天选之子",
                "mbti": "ESFJ",
                "reason": "抽卡次次出金，让人羡慕嫉妒恨。",
                "qq": "10005",
            },
        ],
    }

    analysis_result["statistics"]["golden_quotes"] = [
        {
            "sender": "大佬",
            "content": "这代码能跑就行，别动它！",
            "reason": "至理名言，动了就崩。",
            "qq": "20001",
        },
        {
            "sender": "萌新",
            "content": "为什么我的报错和你不一？",
            "reason": "经典的灵魂发问。",
            "qq": "20002",
        },
        {
            "sender": "群主",
            "content": "再发黄色图全部禁言！",
            "reason": "来自管理层的威慑。",
            "qq": "888888",
        },
    ]

    # Helper wrapper for dot notation access needed by template
    class DictWrapper:
        def __init__(self, data):
            self._data = data
            for k, v in data.items():
                if isinstance(v, list):
                    setattr(
                        self,
                        k,
                        [DictWrapper(i) if isinstance(i, dict) else i for i in v],
                    )
                elif isinstance(v, dict):
                    setattr(self, k, DictWrapper(v))
                else:
                    setattr(self, k, v)

        def __getitem__(self, key):
            return self._data[key]

        def get(self, key, default=None):
            return self._data.get(key, default)

    # Wrap sections that need dot access
    analysis_result["statistics"] = DictWrapper(analysis_result["statistics"])
    analysis_result["topics"] = [DictWrapper(t) for t in analysis_result["topics"]]
    analysis_result["user_titles"] = [
        DictWrapper(t) for t in analysis_result["user_titles"]
    ]

    print("Generating PDF Report...")
    group_id = "test_group_mock"

    # Direct generation
    pdf_path = await generator.generate_pdf_report(analysis_result, group_id=group_id)

    if pdf_path:
        print(f"\n[SUCCESS] PDF Generated Successfully: {pdf_path}")
        print(f"File Size: {os.path.getsize(pdf_path) / 1024:.2f} KB")
    else:
        print("\n[FAILURE] PDF Generation Failed.")


if __name__ == "__main__":
    asyncio.run(main())
